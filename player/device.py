import asyncio
from time import sleep
import numpy
import soxr
import soundfile
import threading
import sounddevice
import sys
from os import error
from typing import Any
from sounddeviceextensions import ExWasapiSettings

def find_output_device(hostapi: str, devicename: str) -> int:
    """Returns found device index

    Parameters
    ----------
    hostapi : str
        Name or partial name of host api
    devicename : str
        Name or partial name of device

    Returns
    -------
    int
        device id or -1 if device hasn't been found
    """
    hostapi_index = 0
    for api in sounddevice.query_hostapis():
        if api['name'].find(hostapi) >= 0:
            break;
        hostapi_index+=1
    for device in sounddevice.query_devices():
        if device['max_input_channels'] == 0 and device['name'].find(devicename) >= 0 and device['hostapi'] == hostapi_index:
            return device['index']
    return -1

class OutputDeviceConfiguration:
    samplerate: int
    blocksize: int
    prefill_buffersize: int
    channels: int
    current_position: int
    file: soundfile._SoundFileInfo

    def __init__(self, filename: str, device, max_sample_rate : int):
        self.file = soundfile.info(filename)
        self.channels = device.channels
        self.samplerate = self.file.samplerate
        self.prefill_buffersize = 20
        if int(self.file.samplerate) > max_sample_rate:
            self.samplerate = max_sample_rate
        self.blocksize = int(self.samplerate/8)

class OutputDevice:
    context: OutputDeviceConfiguration
    buffer: numpy.ndarray

    def __init__(self, device_id : int):
        self.__id = device_id
        self.__dtype: Any = numpy.float32
        self.__channels : int = 2
        self.__extra_settings : Any = ExWasapiSettings(exclusive=True, polling=True, thread_priority=True) # WASAPI polling mode
        self.__device_max_samplerate : int = self.__get_max_samplerate()
        self.__start_streaming_event: threading.Event = threading.Event()
        self.__currently_playing = False
        self.__output_stream : sounddevice.OutputStream | None = None
        self.__buffer_worker: threading.Thread | None = None
    
    @property
    def channels(self):
        return self.__channels

    def initialize_playback(self, filepath: str):
        if not filepath:
            raise error("filepath parameter is mandatory")

        self.context = OutputDeviceConfiguration(filename=filepath, device=self, max_sample_rate=self.__device_max_samplerate)

        if self.context.file.subtype == 'PCM_16':
            self.__dtype = numpy.int16
        elif self.context.file.subtype == 'PCM_24':
            self.__dtype = numpy.int32
        else:
            self.__dtype = numpy.float32

        self.buffer = numpy.ndarray(shape=(self.context.file.frames, self.__channels), dtype=self.__dtype)
        self.resampler = soxr.ResampleStream(
                in_rate=self.context.file.samplerate,
                out_rate=self.context.samplerate,
                num_channels=self.__channels,
                dtype=self.__dtype,
                quality=soxr.VHQ
            )

    def __get_max_samplerate(self) -> int:
        sample_rates = [384000, 352800, 192000, 176400, 96000, 88200, 48000, 44100, 22050]
        for rate in sample_rates:
            try:
                sounddevice.check_output_settings(
                    samplerate=rate,
                    device=self.__id,
                    channels=self.__channels,
                    extra_settings=self.__extra_settings,
                )
                return rate
            except Exception:
                rate = 0
        return 0

    def __fill_buffer_worker(self) -> None:
        with soundfile.SoundFile(file=self.context.file.name) as f:
            position = 0
            frames = self.context.blocksize
            prefill_buffer_count = self.context.prefill_buffersize
    
            # Fill the buffer
            while f.tell() < f.frames:
                if not prefill_buffer_count:
                    self.__start_streaming_event.set()
                # Compute last frame size
                if f.tell() + frames > f.frames:
                    frames = f.frames - f.tell()
                data = f.read(frames=frames, dtype=self.buffer.dtype, always_2d=True, fill_value=0)
                if self.context.samplerate != f.samplerate:
                    data = self.resampler.resample_chunk(data)
                if len(data):
                    self.buffer[position:position+len(data)] = data
                position += len(data)
                prefill_buffer_count -= 1
    
            # Resize the buffer to it's actual length
            if position < f.frames:
                self.buffer.resize((position, self.context.channels), refcheck=False)

    def play(self, filepath : str | None = None) -> None:
        """Plays a sound file on ouput device

        Returns
        -------
        None
        """

        if self.__start_streaming_event.is_set():
            self.stop()

        if filepath:
            self.initialize_playback(filepath)

        # intitialize buffer_worker
        self.__buffer_worker = threading.Thread(target=self.__fill_buffer_worker)
        self.__start_streaming_event.clear()
        self.__buffer_worker.start()

        # defines streaming callback
        self.context.current_position = 0
        def callback(outdata, frames, time, status) -> None:
            if status.output_underflow:
                print('Output underflow: increase blocksize?', file=sys.stderr)
                raise sounddevice.CallbackAbort()
            assert not status
        
            data = self.buffer[self.context.current_position:self.context.current_position+frames]
            outdata[:len(data)] = data
            self.context.current_position+=frames

            if self.context.current_position >= len(self.buffer):
                self.__currently_playing = False
                raise sounddevice.CallbackStop()



        self.__output_stream = sounddevice.OutputStream(
                device=self.__id,
                dtype=self.buffer.dtype,
                extra_settings=self.__extra_settings,
                samplerate=self.context.samplerate,
                blocksize=self.context.blocksize,
                channels=self.context.channels,
                dither_off=True,
                clip_off=True,
                callback=callback,
            )
        self.__start_streaming_event.wait()
        self.__currently_playing = True
        self.__output_stream.start()

    @property
    def is_playing(self) -> bool:
        return self.__currently_playing

    def stop(self) -> None:
        self.__currently_playing = False
        if self.__output_stream:
            self.__output_stream.stop(ignore_errors=True)
            self.__output_stream.close(ignore_errors=True)
            self.__output_stream = None

    def pause(self):
        if self.__output_stream:
            self.__output_stream.stop()

    def resume(self):
        if self.__output_stream:
            self.__output_stream.start()
