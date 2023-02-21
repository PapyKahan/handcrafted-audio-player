import asyncio
import sounddevice
import os
from tinytag import TinyTag
from core.device import OutputDevice, DeviceInfo, HostApiInfo
from numpy import random

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
    filetype: str

class HandcraftedAudioPlayer():
    def __init__(self):
        self.__current_device_info : DeviceInfo | None = None
        self.__current_track_info : TrackInfo | None = None
        self.__output_device : OutputDevice | None = None
        self.__on_track_changed : list = list()
        self.__on_track_ended : list = list()
        self.__on_playlist_changed : list = list()
        self.__current_playlist : list[TrackInfo] | None = None
        self.__current_track_index : int = 0
        self.__playback_stoped : bool = True
        self.__playback_paused : bool = True
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
        self.__output_device = OutputDevice(self.__current_device_info)

    @property
    def is_playing(self) -> bool:
        if self.__output_device:
            return self.__output_device.is_playing
        return False
    
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
            if index != None:
                self.__current_track_index = index

            track = self.__current_playlist[self.__current_track_index]

            playback_info = self.__output_device.play(track.path)

            self.__playback_stoped = False
            track.channels = playback_info.channels
            track.bitdepth = playback_info.bitdepth
            track.filetype = playback_info.filetype
            self.__current_track_info = track
            for event in self.on_track_changed:
                event(self.__current_track_info, self.__current_device_info)
            asyncio.create_task(self.__wait_and_play_next())
            self.__playback_stoped = False
            self.__playback_paused = False

    async def __wait_and_play_next(self):
        while self.is_playing == True:
            await asyncio.sleep(1)
        if self.__playback_stoped == False:
            await self.next()

    @property
    def on_track_changed(self) -> list:
        return self.__on_track_changed

    @property
    def on_track_ended(self) -> list:
        return self.__on_track_ended

    @property
    def on_playlist_changed(self) -> list:
        return self.__on_playlist_changed

    @property
    def is_paused(self) -> bool :
        return self.__playback_paused

    @property
    def is_stoped(self) -> bool:
        return self.__playback_stoped

    def resume(self):
        if self.__output_device:
            self.__output_device.resume()
            self.__playback_paused = False

    def pause(self):
        if self.__output_device:
            self.__output_device.pause()
            self.__playback_paused = True

    def stop(self):
        if self.__output_device:
            self.__output_device.stop()
            self.__playback_stoped = True

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

    def randomize(self):
        if self.__current_playlist:
            current_file = self.__current_playlist[self.__current_track_index]
            random.shuffle(self.__current_playlist)
            index = 0
            for track in self.__current_playlist:
                if track.path == current_file.path:
                    break
                index += 1
            self.__current_track_index = index
            for event in self.__on_playlist_changed:
                event()


