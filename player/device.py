import numpy
import soxr
import soundfile
import threading
import sounddevice
import sys
from os import error
from typing import Any
from sounddeviceextensions import ExWasapiSettings
from typing import Any

class HostApiInfo():
    def __init__(self, hostapi_info: dict[str, Any]):
        self.__name = hostapi_info['name']
        self.__devices = list[DeviceInfo]()
        self.__default_output_device = None
        for device_id in hostapi_info['devices']:
            device = sounddevice.query_devices(device_id)
            if device['max_input_channels'] == 0 and device['name'] != "":
                device_info = DeviceInfo(device_info=device, hostapi_info=self, is_default_device=device_id == hostapi_info['default_output_device'])
                self.devices.append(device_info)
                if device_info.is_default_output_device:
                    self.__default_output_device = device_info

    def __str__(self):
        return f"Host: {self.__name}, default output device: [{self.default_output_device}]"

    @property
    def name(self):
        return self.__name

    @property
    def devices(self):
        return self.__devices

    @property
    def default_output_device(self):
        return self.__default_output_device

class DeviceInfo():
    def __init__(self, device_info : dict[str, Any], hostapi_info : HostApiInfo, is_default_device : bool = False):
        self.__hostapi = hostapi_info
        self.__is_default_output_device = is_default_device
        self.__name = device_info['name']
        self.__index = device_info['index']
        self.__max_output_channels = device_info['max_output_channels']
        self.__default_low_output_latency = device_info['default_low_output_latency']
        self.__default_high_output_latency = device_info['default_high_output_latency']
        self.__default_samplerate = device_info['default_samplerate']

    def __str__(self) -> str:
        return f"Device ({self.__hostapi.name}) - id: {self.__index}, name: {self.__name}, max_output_channels: {self.__max_output_channels}, default_low_output_latency: {self.__default_low_output_latency}, default_high_output_latency: {self.__default_high_output_latency}, default_samplerate: {self.__default_samplerate}"

    @property
    def hostapi(self) -> HostApiInfo:
        return self.__hostapi

    @property
    def is_default_output_device(self) -> bool:
        return self.__is_default_output_device

    @property
    def name(self) -> str:
        return self.__name

    @property
    def index(self) -> int:
        return self.__index

    @property
    def max_output_channels(self) -> int:
        return self.__max_output_channels

    @property
    def default_low_output_latency(self) -> float:
        return self.__default_low_output_latency

    @property
    def default_high_output_latency(self) -> float:
        return self.__default_high_output_latency

    @property
    def default_samplerate(self) -> int:
        return self.__default_samplerate

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
        self.__device_is_streaming = False
    
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
                self.__device_is_streaming = False
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
        self.__device_is_streaming = True

    @property
    def is_playing(self) -> bool:
        if self.__output_stream:
            return self.__device_is_streaming
        return False

    def stop(self) -> None:
        if self.__output_stream:
            self.__output_stream.stop(ignore_errors=True)
            self.__output_stream.close(ignore_errors=True)
            self.__output_stream = None
            self.__device_is_streaming = False

    def pause(self):
        if self.__output_stream:
            self.__output_stream.stop()

    def resume(self):
        if self.__output_stream:
            self.__output_stream.start()
