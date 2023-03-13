import asyncio
import time
from rich.progress import BarColumn, Progress, Task, TextColumn
from rich.text import Text
from textual.app import ComposeResult
from textual.events import Timer
from textual.widgets import Label, Static, Button
from core.player import DeviceInfo, TrackInfo


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

    .toggled {
        background: grey;
    }
    """

    #BINDINGS = [
    #    ("h", "previous_track", "Previous"),
    #    ("l", "previous_track", "Next"),
    #    ("p", "play_track", "Play"),
    #    ("p", "pause_track", "Pause"),
    #    ("t", "stop_track", "Stop"),
    #    ("s", "shuffle_playlist", "Shuffle"),
    #    ("r", "repeat_playlist", "Repeat"),
    #]

    def __init__(self, *args, **kwargs):
        return super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Button("", id="repeat_queue")
        yield Button("玲", id="previous_track")
        yield Button("", id="play_track")
        yield Button("", id="pause_track", classes="hidden")
        yield Button("", id="stop_track", disabled=True)
        yield Button("怜", id="next_track")
        yield Button("", id="shuffle_queue")

    def __on_track_changed(self, *_):
        self.query_one("#stop_track").disabled = False
        self.query_one("#pause_track").remove_class("hidden")
        play_button = self.query_one("#play_track")
        if play_button.has_class("hidden"):
            play_button.remove_class("hidden")
        play_button.add_class("hidden")

    def on_mount(self) -> None:
        self.app.player.on_track_changed.append(self.__on_track_changed)

    def action_previous_track(self):
        asyncio.create_task(self.app.player.previous())

    def action_next_track(self):
        asyncio.create_task(self.app.player.next())

    async def action_play_track(self):
        if self.app.player.is_playing == False:
            if not self.app.player.current_device:
                self.app.action_select_output_device()
            else:
                await self.app.player.play()
        else:
            self.app.player.resume()
            self.query_one("#pause_track").toggle_class("hidden")
            self.query_one("#play_track").toggle_class("hidden")

    def action_pause_track(self):
        self.app.player.pause()
        self.query_one("#pause_track").toggle_class("hidden")
        self.query_one("#play_track").toggle_class("hidden")

    def action_stop_track(self):
        self.app.player.stop()
        self.query_one("#pause_track").toggle_class("hidden")
        self.query_one("#play_track").toggle_class("hidden")
        self.query_one("#stop_track").disabled = True

    def action_shuffle_playlist(self):
        self.app.player.shuffle()
        self.query_one("#shuffle_queue").toggle_class("toggled")

    def action_repeat(self):
        self.app.player.repeat()
        self.query_one("#repeat_queue").toggle_class("toggled")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button = event.button
        if button.id == "play_track":
            await self.action_play_track()
        elif button.id == "pause_track":
            self.action_pause_track()
        elif button.id == "stop_track":
            self.action_stop_track()
        elif button.id == "previous_track":
            self.action_previous_track()
        elif button.id == "next_track":
            self.action_next_track()
        elif button.id == "shuffle_queue":
            self.action_shuffle_playlist()
        elif button.id == "repeat_queue":
            self.action_repeat()

class TrackElapsedTimeColumn(TextColumn):
    def __init__(self, *args, **kwargs):
        return super().__init__("", *args, **kwargs)    

    def render(self, task: Task) -> Text:
        if task.description == "dummy":
            return Text("--:--")
        elif task.description == "elapsed":
            t = time.gmtime(task.completed)
            return Text(time.strftime("%M:%S", t))
        return Text("--:--")

class TrackTotalTimeColumn(TextColumn):
    def __init__(self, *args, **kwargs):
        return super().__init__("", *args, **kwargs)    

    def render(self, task: Task) -> Text:
        if task.description == "dummy":
            return Text("--:--")
        else:
            t = time.gmtime(task.total)
            return Text(time.strftime("%M:%S", t))


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
        super().__init__(*args, **kwargs)
        self.__elapsed_column = TrackElapsedTimeColumn()
        self.__bar = BarColumn()
        self.__total_column = TrackTotalTimeColumn()
        self.__progress_bar = Progress(self.__elapsed_column, self.__bar, self.__total_column)
        self.__task_id = self.__progress_bar.add_task("dummy")
        self.app.player.on_track_changed.append(self.__on_track_changed)
        self.__current_track_timer : Timer | None = None

    def __on_track_changed(self, current_track : TrackInfo, *_):
        self.__current_track = current_track
        if self.__current_track_timer:
            self.__current_track_timer.stop()
        self.__progress_bar.update(self.__task_id, description="play", total=self.__current_track.duration, completed=0)
        self.__current_track_timer = self.set_interval(1/60, self.__update_progress_bar, pause=True)
        self.__current_track_timer.resume()
        self.refresh(repaint=True)

    def __update_progress_bar(self):
        self.__progress_bar.update(task_id=self.__task_id, description="elapsed", total=self.__current_track.duration, completed=self.__current_track.elapsed)
        self.refresh(repaint=True)

    def render(self):
        return self.__progress_bar
    


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
