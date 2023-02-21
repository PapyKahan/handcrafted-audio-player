#!/usr/bin/env python3
import argparse
import os
from numpy import random
import sounddevice
import asyncio
from core import OutputDevice
from tinytag import TinyTag
from core.device import DeviceInfo, HostApiInfo
from core.player import TrackInfo
from ui import HandcraftedAudioPlayerApp

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    '-l', '--list-devices', action='store_true',
    help='show list of audio devices and exit')
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sounddevice.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    'path', metavar='PATH',
    help='audio library path')
args = parser.parse_args(remaining)

def find_output_device(hostapi: str, devicename: str) -> DeviceInfo | None:
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
    hostapi_info : HostApiInfo = None
    for api in sounddevice.query_hostapis():
        if api['name'].find(hostapi) >= 0:
            hostapi_info = HostApiInfo(api)
            break;
        hostapi_index+=1
    for device in sounddevice.query_devices():
        if device['max_input_channels'] == 0 and device['name'].find(devicename) >= 0 and device['hostapi'] == hostapi_index:
            return DeviceInfo(device, hostapi_info)
    return None

def get_files_into_directory(path: str) -> list:
    filelist = list()
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
                filelist.append(track_info)
    return filelist


if __name__ == "__main__":
    #device = find_output_device('WASAPI', 'Cayin RU6')
    #device = find_output_device('DirectSound', 'Cayin RU6')
    #device = find_output_device('WASAPI', 'DETHONRAY Honey H1')
    #device = find_output_device('DirectSound', 'Qudelix-5K USB DAC')
    #deviceid = find_output_device('WASAPI', 'Realtek High Definition Audio(SST)')
    #if not device:
    #    parser.exit(1, 'Device not found')
    #device = OutputDevice(device)

    try:
        playlist = get_files_into_directory(args.path)
        random.shuffle(playlist)
        #for file in playlist:
        #    device.play(file.path)
        #    while device.is_playing == True:
        #        asyncio.run(asyncio.sleep(1))

        app = HandcraftedAudioPlayerApp(playlist)
        app.run()
    
    except KeyboardInterrupt:
        parser.exit(1, '\nInterrupted by user')
    except Exception as e:
        parser.exit(1, type(e).__name__ + ': ' + str(e))

