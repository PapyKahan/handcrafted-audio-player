import time
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header
from core.player import HandcraftedAudioPlayer
from ui.controls import CurrentTrackWidget
from ui.selectoutputdevicescreen import SelectOutputDeviceScreen
from ui.settings import SettingsScreen


class HandcraftedAudioPlayerApp(App):
    SCREENS = {
        "select_output_device": SelectOutputDeviceScreen(),
        "settings": SettingsScreen(),
    }
    DEFAULT_CSS = """
    #current_track_controls {
        dock: bottom;
        margin: 0 0 2 0
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "select_output_device", "Select Output"),
        ("s", "settings", "Settings"),
    ]

    def __init__(self, *args, **kwargs):
        self.__player = HandcraftedAudioPlayer()
        self.__current_playlist_data_table: DataTable = DataTable(zebra_stripes=True)
        self.__current_playlist_data_table.cursor_type = "row" 
        self.__current_track_controls = CurrentTrackWidget(id="current_track_controls")
        self.__previous_track_index : int = 0
        return super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            self.__current_playlist_data_table,
            self.__current_track_controls
        )
        yield Footer()

    @property
    def player(self) -> HandcraftedAudioPlayer:
        return self.__player
    
    def action_select_output_device(self):
        if len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(SelectOutputDeviceScreen(id="select_output_device_screen"))

    def action_settings(self):
        if len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(SettingsScreen(id="settings"))

    async def on_data_table_row_selected(self, selected_row : DataTable.RowSelected) -> None:
        if not self.__player.current_device:
            self.action_select_output_device()
        else:
            await self.__player.play(selected_row.cursor_row)

    def __on_track_changed(self, *_):
        self.__current_playlist_data_table.update_cell_at(Coordinate(self.__previous_track_index, 0), " ", update_width=True)
        self.__current_playlist_data_table.update_cell_at(Coordinate(self.__player.current_track_index, 0), "", update_width=True)
        self.__current_playlist_data_table._highlight_row(self.__player.current_track_index)
        self.__previous_track_index = self.__player.current_track_index

    def __on_playlist_changed(self, *_):
        self.__current_playlist_data_table.clear()
        self.__fill_playlist_widget()

    def __fill_playlist_widget(self):
        if self.__player.current_playlist:
            index = 0
            for file in self.__player.current_playlist:
                t = time.gmtime(file.duration)
                if self.__player.current_track_index == index:
                    self.__current_playlist_data_table.add_row("", file.title, file.artist, time.strftime("%M:%S", t))
                    self.__previous_track_index = index
                else:
                    self.__current_playlist_data_table.add_row(" ", file.title, file.artist, time.strftime("%M:%S", t))
                index += 1
            self.__current_playlist_data_table._highlight_row(self.__player.current_track_index)

    def on_mount(self) -> None:
        self.__player.on_track_changed.append(self.__on_track_changed)
        self.__player.on_playlist_changed.append(self.__on_playlist_changed)
        self.__current_playlist_data_table.add_columns(" ", "Title", "Artist", "Duration")
        self.__fill_playlist_widget()
