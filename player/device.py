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
    dtype: Any
    file: soundfile._SoundFileInfo

    def __init__(self, filename: str, device, max_sample_rate : int):
        self.file = soundfile.info(filename)
        self.channels = device._channels
        self.samplerate = self.file.samplerate
        self.prefill_buffersize = 20
        if int(self.file.samplerate) > max_sample_rate:
            self.samplerate = max_sample_rate
        self.blocksize = int(self.samplerate/8)

        if self.file.subtype == 'PCM_16':
            self.dtype = numpy.int16
        elif self.file.subtype == 'PCM_24':
            self.dtype = numpy.int32
        else:
            self.dtype = numpy.float32

class OutputDevice:
    configuration: OutputDeviceConfiguration

    def __init__(self, device_id : int):
        self._channels : int = 2
        self.__id = device_id
        self.__extra_settings : Any = ExWasapiSettings(exclusive=True, polling=True, thread_priority=True) # WASAPI polling mode
        self.__device_max_samplerate : int = self.__get_max_samplerate()
        self.__start_streaming_event: threading.Event = threading.Event()
        self.__output_stream : sounddevice.OutputStream | None = None
        self.__buffer_worker: threading.Thread | None = None
        self.__buffer: numpy.ndarray
        self.__current_buffer_read_position : int = 0
    
    def __initialize_playback(self, filepath: str):
        self.configuration = OutputDeviceConfiguration(filename=filepath, device=self, max_sample_rate=self.__device_max_samplerate)
        self.__buffer = numpy.ndarray(shape=(self.configuration.file.frames, self._channels), dtype=self.configuration.dtype)
        self.resampler = soxr.ResampleStream(
                in_rate=self.configuration.file.samplerate,
                out_rate=self.configuration.samplerate,
                num_channels=self._channels,
                dtype=self.configuration.dtype,
                quality=soxr.VHQ
            )

    def __get_max_samplerate(self) -> int:
        sample_rates = [384000, 352800, 192000, 176400, 96000, 88200, 48000, 44100, 22050]
        for rate in sample_rates:
            try:
                sounddevice.check_output_settings(
                    samplerate=rate,
                    device=self.__id,
                    channels=self._channels,
                    extra_settings=self.__extra_settings,
                )
                return rate
            except Exception:
                rate = 0
        return 0

    def __fill_buffer_worker(self) -> None:
        with soundfile.SoundFile(file=self.configuration.file.name) as f:
            position = 0
            frames = self.configuration.blocksize
            prefill_buffer_count = self.configuration.prefill_buffersize
    
            # Fill the buffer
            while f.tell() < f.frames:
                if not prefill_buffer_count:
                    self.__start_streaming_event.set()
                # Compute last frame size
                if f.tell() + frames > f.frames:
                    frames = f.frames - f.tell()
                data = f.read(frames=frames, dtype=self.__buffer.dtype, always_2d=True, fill_value=0)
                if self.configuration.samplerate != f.samplerate:
                    data = self.resampler.resample_chunk(data)
                if len(data):
                    self.__buffer[position:position+len(data)] = data
                position += len(data)
                prefill_buffer_count -= 1
    
            # Resize the buffer to it's actual length
            if position < f.frames:
                self.__buffer.resize((position, self.configuration.channels), refcheck=False)

    def play(self, filepath : str) -> None:
        """Plays a sound file on ouput device

        Parameters
        -------
        filepath: str
            sound file path to be played

        Returns
        -------
        None
        """

        if not filepath:
            raise error("filepath parameter is mandatory")

        if self.__start_streaming_event.is_set():
            self.stop()

        self.__initialize_playback(filepath)

        # intitialize buffer_worker
        self.__buffer_worker = threading.Thread(target=self.__fill_buffer_worker)
        self.__start_streaming_event.clear()
        self.__buffer_worker.start()

        # defines streaming callback
        self.__current_buffer_read_position = 0
        def callback(outdata, frames, time, status) -> None:
            if status.output_underflow:
                print('Output underflow: increase blocksize?', file=sys.stderr)
                raise sounddevice.CallbackAbort()
            assert not status
        
            data = self.__buffer[self.__current_buffer_read_position:self.__current_buffer_read_position+frames]
            outdata[:len(data)] = data
            self.__current_buffer_read_position+=frames

            if self.__current_buffer_read_position >= len(self.__buffer):
                raise sounddevice.CallbackStop()

        self.__output_stream = sounddevice.OutputStream(
                device=self.__id,
                dtype=self.__buffer.dtype,
                extra_settings=self.__extra_settings,
                samplerate=self.configuration.samplerate,
                blocksize=self.configuration.blocksize,
                channels=self.configuration.channels,
                dither_off=True,
                clip_off=True,
                callback=callback,
            )
        self.__start_streaming_event.wait()
        self.__output_stream.start()
        self.__output_stream.active

    @property
    def is_playing(self) -> bool:
        if self.__output_stream:
            return self.__output_stream.active
        return False

    def stop(self) -> None:
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
