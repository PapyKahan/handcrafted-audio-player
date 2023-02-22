#!/usr/bin/env python3
import argparse
import os
import sounddevice
from tinytag import TinyTag
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

if __name__ == "__main__":
    try:
        app = HandcraftedAudioPlayerApp()
        app.player.load_library(args.path)
        app.run()
    except KeyboardInterrupt:
        parser.exit(1, '\nInterrupted by user')
    except Exception as e:
        parser.exit(1, type(e).__name__ + ': ' + str(e))

