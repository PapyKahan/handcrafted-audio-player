import asyncio
import time
from rich.progress import BarColumn, Progress, Task, TextColumn, Text
from textual.app import ComposeResult
from textual.widgets import Label, Static, Button
from player.player import DeviceInfo, TrackInfo


class TrackDetails(Static):
    track_name : Label = Label("Track:", id="track_name")
    track_artist : Label = Label("Artist:", id="track_artist")
    track_album : Label = Label("Album:", id="track_album")
    track_info : Label = Label("File info:", id="track_technical_info")
    track_device_info : Label = Label("Device:", id="track_device_info")

    def compose(self) -> ComposeResult:
        yield self.track_name
        yield self.track_artist
        yield self.track_album
        yield self.track_info
        yield self.track_device_info

    def on_mount(self) -> None:
        self.app.player.on_track_changed.append(self.__on_track_changed)
    
    def __on_track_changed(self, track: TrackInfo, device: DeviceInfo) -> None:
        self.track_name.update(f"Track: {track.title}")
        self.track_artist.update(f"Artist: {track.artist}")
        self.track_album.update(f"Album: {track.album}")
        self.track_info.update(f"File info: Samplerate = {track.samplerate}Hz, bitdeph = {track.bitdepth}, type = {track.filetype}")
        self.track_device_info.update(f"Device: Name = {device.name}, Api = {device.hostapi.name}")

class TrackControls(Static):
    DEFAULT_CSS = """
    TrackControls {
        layout: horizontal;
        align: center middle;
    }

    .hidden {
        display: none;
    }
    """

    def __init__(self, *args, **kwargs):
        return super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Button("", id="repeat_queue")
        yield Button("玲", id="previous_track")
        yield Button("", id="play_track")
        yield Button("", id="pause_track", classes="hidden")
        yield Button("", id="stop_track", disabled=True)
        yield Button("怜", id="next_track")
        yield Button("", id="random_queue")

    def __on_track_changed(self, *_):
        self.query_one("#stop_track").disabled = False
        self.query_one("#pause_track").remove_class("hidden")
        play_button = self.query_one("#play_track")
        if play_button.has_class("hidden"):
            play_button.remove_class("hidden")
        play_button.add_class("hidden")

    def on_mount(self) -> None:
        self.app.player.on_track_changed.append(self.__on_track_changed)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button = event.button
        if button.id == "play_track":
            if self.app.player.is_playing == False:
                if not self.app.player.current_device:
                    self.app.action_select_output_device()
                else:
                    await self.app.player.play()
            else:
                self.app.player.resume()
                self.query_one("#pause_track").toggle_class("hidden")
                self.query_one("#play_track").toggle_class("hidden")
        elif button.id == "pause_track":
            self.app.player.pause()
            self.query_one("#pause_track").toggle_class("hidden")
            self.query_one("#play_track").toggle_class("hidden")
        elif button.id == "stop_track":
            self.app.player.stop()
            self.query_one("#pause_track").toggle_class("hidden")
            self.query_one("#play_track").toggle_class("hidden")
            button.disabled = True
        elif button.id == "previous_track":
            asyncio.create_task(self.app.player.previous())
        elif button.id == "next_track":
            asyncio.create_task(self.app.player.next())


class TrackTimeColumn(TextColumn):
    def __init__(self, *args, **kwargs):
        return super().__init__("", *args, **kwargs)    

    def render(self, task: Task) -> Text:
        if task.description == "dummy":
            return Text("--:--")
        elif task.description == "play":
            t = time.gmtime(task.total)
            return Text(time.strftime("%M:%S", t))
        elif task.description == "elapsed":
            return Text("--:--")
        return Text("--:--")


class TrackProgressBar(Static):
    DEFAULT_CSS = """
    TrackProgressBar {
        content-align: center middle;
        text-opacity: 80%;
        width: 100%;
        height: 4;
    }
    """
    def __init__(self, *args, **kwargs):
        self.start_column = TrackTimeColumn()
        self.bar = BarColumn()
        self.end_column = TrackTimeColumn()
        self.progress_bar = Progress(self.start_column, self.bar, self.end_column)
        self.task_id = self.progress_bar.add_task("dummy")
        return super().__init__(*args, **kwargs)

    def on_mount(self):
        self.app.player.on_track_changed.append(self.__on_track_changed)

    def __on_track_changed(self, *_):
        if self.app.player.current_track:
            self.progress_bar.add_task("play", total=self.app.player.current_track.duration)

    def render(self):
        return self.progress_bar

class CurrentTrackWidget(Static):
    DEFAULT_CSS = """
    TrackInfo {
        layout: vertical;
        content-align-horizontal: center;
        height: 6;
    }

    #track_name {
        text-style: bold;
        width: 100%;
        text-align: center;
        color: $text;
        background: $boost;
    }

    #track_artist {
        width: 100%;
        text-align: center;
        color: $text;
        background: $boost;
    }

    #track_album {
        width: 100%;
        text-align: center;
        color: $text;
        background: $boost;
    }

    #track_technical_info {
        text-style: italic;
        width: 100%;
        text-align: center;
        color: grey;
        background: $boost;
    }

    #track_device_info {
        border-top: solid gray;
        text-style: italic;
        width: 100%;
        text-align: center;
        color: gray;
        background: $boost;
    }
    """

    def __init__(self, *args, **kwargs):
        return super().__init__("", *args, **kwargs)

    def compose(self) -> ComposeResult:
        yield TrackDetails()
        yield TrackProgressBar()
        yield TrackControls()
