import asyncio
from asyncio.tasks import Task
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
    elapsed : float = 0.0
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
        self.__current_library : list[TrackInfo] | None = None
        self.__current_playlist_queue : list[TrackInfo] | None = None
        self.__current_track_index : int = 0
        self.__playback_stoped : bool = True
        self.__playback_paused : bool = True
        self.__repeat_playlist : bool = False
        self.__is_shuffle_enabled : bool = False
        self.__play_next_task : Task | None = None

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
        return self.__current_playlist_queue
    
    @property
    def current_track_index(self) -> int :
        return self.__current_track_index

    async def play(self, index : int | None = None) -> None:
        if self.__play_next_task:
            self.__play_next_task.cancel()

        if self.__output_device and self.__current_playlist_queue:
            if index != None:
                self.__current_track_index = index

            track = self.__current_playlist_queue[self.__current_track_index]
            playback_info = self.__output_device.play(track.path)

            self.__playback_stoped = False
            track.channels = playback_info.channels
            track.bitdepth = playback_info.bitdepth
            track.filetype = playback_info.filetype
            track.elapsed = 0.0
            self.__current_track_info = track
            for event in self.on_track_changed:
                event(self.__current_track_info, self.__current_device_info)
            self.__play_next_task = asyncio.create_task(self.__wait_and_play_next())
            self.__playback_stoped = False
            self.__playback_paused = False

    async def __wait_and_play_next(self):
        while self.is_playing == True:
            await asyncio.sleep(1)
            if self.__current_track_info and self.__playback_paused == False:
                self.__current_track_info.elapsed += 1
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

    @property
    def is_repeat_enabled(self) -> bool:
        return self.__repeat_playlist

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
        if self.__current_playlist_queue:
            if self.__current_track_index == len(self.__current_playlist_queue)-1:
                if self.__repeat_playlist == True:
                    self.__current_track_index=0
            else:
                self.__current_track_index+= 1
    
    async def next(self) -> None:
        self.__increase_current_index()
        await self.play()

    def __decrease_current_index(self):
        if self.__current_playlist_queue:
            if self.__current_track_index == 0:
                if self.__repeat_playlist == True:
                    self.__current_track_index = len(self.__current_playlist_queue)-1
            else:
                self.__current_track_index -= 1

    async def previous(self):
        self.__decrease_current_index()
        await self.play()

    def shuffle(self):
        self.__is_shuffle_enabled = not self.__is_shuffle_enabled
        if self.__current_playlist_queue and self.__current_library:
            current_file = self.__current_playlist_queue[self.__current_track_index]
            self.__current_playlist_queue = self.__current_library.copy()
            if self.__is_shuffle_enabled == True:
                random.shuffle(self.__current_playlist_queue)
            index = 0
            for track in self.__current_playlist_queue:
                if track.path == current_file.path:
                    break
                index += 1
            self.__current_track_index = index
            for event in self.__on_playlist_changed:
                event()

    def repeat(self):
        self.__repeat_playlist = not self.__repeat_playlist

    def load_library(self, path : str):
        if not self.__current_library:
            self.__current_library = list[TrackInfo]()
        self.__current_library.clear()
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".flac"):
                    filepath = os.path.join(root, file)
                    tags = TinyTag.get(filepath)
                    track_info = TrackInfo()
                    track_info.path = filepath
                    track_info.title = tags.title
                    track_info.album = tags.album
                    track_info.artist = tags.artist
                    track_info.albumartist = tags.albumartist
                    track_info.samplerate = tags.samplerate
                    track_info.duration = tags.duration
                    self.__current_library.append(track_info)
        self.__current_playlist_queue = self.__current_library.copy()
        for event in self.__on_playlist_changed:
            event()
