import asyncio
import sounddevice
import os
from tinytag import TinyTag
from typing import Any

from player.device import OutputDevice

class HostApiInfo():
    def __init__(self, hostapi_info: dict[str, Any]):
        self._name = hostapi_info['name']
        self._devices = list[DeviceInfo]()
        self._default_output_device = None
        for device_id in hostapi_info['devices']:
            device = sounddevice.query_devices(device_id)
            if device['max_input_channels'] == 0 and device['name'] != "":
                device_info = DeviceInfo(device_info=device, hostapi_info=self, is_default_device=device_id == hostapi_info['default_output_device'])
                self.devices.append(device_info)
                if device_info.is_default_output_device:
                    self._default_output_device = device_info

    def __str__(self):
        return f"Host: {self._name}, default output device: [{self.default_output_device}]"

    @property
    def name(self):
        return self._name

    @property
    def devices(self):
        return self._devices

    @property
    def default_output_device(self):
        return self._default_output_device


class DeviceInfo():
    def __init__(self, device_info : dict[str, Any], hostapi_info : HostApiInfo, is_default_device : bool = False):
        self._hostapi = hostapi_info
        self._is_default_output_device = is_default_device
        self._name = device_info['name']
        self._index = device_info['index']
        self._max_output_channels = device_info['max_output_channels']
        self._default_low_output_latency = device_info['default_low_output_latency']
        self._default_high_output_latency = device_info['default_high_output_latency']
        self._default_samplerate = device_info['default_samplerate']

    def __str__(self) -> str:
        return f"Device ({self._hostapi.name}) - id: {self._index}, name: {self._name}, max_output_channels: {self._max_output_channels}, default_low_output_latency: {self._default_low_output_latency}, default_high_output_latency: {self._default_high_output_latency}, default_samplerate: {self._default_samplerate}"

    @property
    def hostapi(self) -> HostApiInfo:
        return self._hostapi

    @property
    def is_default_output_device(self) -> bool:
        return self._is_default_output_device

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._index

    @property
    def max_output_channels(self) -> int:
        return self._max_output_channels

    @property
    def default_low_output_latency(self) -> float:
        return self._default_low_output_latency

    @property
    def default_high_output_latency(self) -> float:
        return self._default_high_output_latency

    @property
    def default_samplerate(self) -> int:
        return self._default_samplerate

class TrackInfo():
    path : str
    title : str
    album : str
    artist : str
    albumartist : str
    duration : float
    samplerate : int
    channels : int
    bitdepth : str
    format: str
    playback_samplerate : int
    def __init__(self):
        pass

class HandcraftedAudioPlayer():
    def __init__(self):
        self.__current_device_info : DeviceInfo | None = None
        self.__current_track_info : TrackInfo | None = None
        self.__output_device : OutputDevice | None = None
        self.__on_track_changed : list = list()
        self.__on_track_ended : list = list()
        self.__current_playlist : list[TrackInfo] | None = None
        self.__current_track_index : int = 0
        self.__playback_stoped : bool = False
        pass

    def get_outout_device_list_by_api(self) -> list[HostApiInfo]:
        host_apis = list[HostApiInfo]()
        for api in sounddevice.query_hostapis():
            host_apis.append(HostApiInfo(api))
        return host_apis

    def get_files_into_directory(self, path: str) -> list[TinyTag]:
        filelist = list()
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".flac"):
                    filelist.append(TinyTag.get(os.path.join(root, file)))
        return filelist
    
    def set_output_device(self, device : DeviceInfo):
        if self.__output_device:
            self.__output_device.stop()
        self.__current_device_info = device
        self.__output_device = OutputDevice(self.__current_device_info.index)

    @property
    def current_device_info(self) -> DeviceInfo | None:
        if self.__current_device_info:
            return self.__current_device_info
        return None

    @property
    def is_playing(self) -> bool:
        if self.__output_device:
            return self.__output_device.is_playing
        return False
    
    @property
    def on_track_changed(self) -> list:
        return self.__on_track_changed

    @property
    def on_track_ended(self) -> list:
        return self.__on_track_ended

    @property
    def current_device(self) -> DeviceInfo | None:
        return self.__current_device_info

    @property
    def current_track(self) -> TrackInfo | None:
        self.__current_track_info

    @property
    def current_playlist(self) -> list[TrackInfo] | None:
        return self.__current_playlist
    
    @property
    def current_track_index(self) -> int :
        return self.__current_track_index

    def set_playlist(self, playlist : list[TrackInfo] | None):
       self.__current_playlist = playlist 

    async def play(self, index : int | None = None) -> None:
        if self.__output_device and self.__current_playlist:
            track : TrackInfo | None = None
            if index != None:
                self.__current_track_index = index
            track = self.__current_playlist[self.__current_track_index]

            self.__output_device.initialize_playback(track.path)
            track.channels = self.__output_device.context.file.channels
            track.bitdepth = self.__output_device.context.file.subtype_info
            track.playback_samplerate = self.__output_device.context.samplerate
            track.format = self.__output_device.context.file.format

            self.__current_track_info = track
            for event in self.on_track_changed:
                event(self.__current_track_info, self.current_device_info)

            self.__output_device.play()
            self.__playback_stoped = False
            asyncio.create_task(self.wait_and_play_next())


    async def wait_and_play_next(self):
        while self.is_playing == True:
            await asyncio.sleep(1)
        if self.__playback_stoped == False:
            await self.next()

    def resume(self):
        if self.__output_device:
            self.__output_device.resume()

    def pause(self):
        if self.__output_device:
            self.__output_device.pause()

    def stop(self):
        if self.__output_device:
            self.__playback_stoped = True
            self.__output_device.stop()

    def __increase_current_index(self):
        if self.__current_playlist:
            if self.__current_track_index == len(self.__current_playlist)-1:
                self.__current_track_index=0
            else:
                self.__current_track_index+= 1

    
    async def next(self) -> None:
        self.__increase_current_index()
        await self.play()

    def __decrease_current_index(self):
        if self.__current_playlist:
            if self.__current_track_index == 0:
                self.__current_track_index = len(self.__current_playlist)-1
            else:
                self.__current_track_index -= 1

    async def previous(self):
        self.__decrease_current_index()
        await self.play()
