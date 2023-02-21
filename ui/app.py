import time
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView, Button, Static
from core.player import DeviceInfo, HandcraftedAudioPlayer
from ui.controls import CurrentTrackWidget

class DeviceItem(ListItem):
    DEFAULT_CSS = """
    ListItem {
        layout: horizontal;
    }

    #device_info_default_device {
        content-align: center middle;
        width: 3;
    }

    #device_info_host_name {
        width: 30;
    }

    #device_info_name {
        width: 100%;
    }

    .selected {
        background: gray;
    }
    """

    device : DeviceInfo
    def __init__(self, device : DeviceInfo, *args, **kwargs):
        self.device = device
        return super().__init__(*args, **kwargs)
    
    def compose(self) -> ComposeResult:
        if self.device.is_default_output_device:
            yield Label("*", id="device_info_default_device")
        else:
            yield Label(" ", id="device_info_default_device")

        yield Label(self.device.hostapi.name, id="device_info_host_name")
        yield Label(self.device.name, id="device_info_name")

class SelectOutputDeviceButtons(Static):
    DEFAULT_CSS = """
    SelectOutputDeviceButtons {
        layout: horizontal;
        align: center middle;
    }

    """
    def compose(self) -> ComposeResult:
        yield Button("Ok", id="select_output_device_ok")
        yield Button("Cancel", id="select_output_device_cancel")

class SelectOutputDeviceDialog(Static):
    DEFAULT_CSS="""
    SelectOutputDeviceDialog {
        border: darkgrey round;
        content-align: center middle;
        width: 80;
        height: 17;
    }

    #select_output_device_title {
        align: center middle;
        width: 100%;
        border-bottom: solid gray;
    }
    """

    def __init__(self, *args, **kwargs):
        self.__selected_device = None
        self.__output_device_list_view : ListView
        self.__previously_selected_item : ListItem | None = None
        return super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.__output_device_list_view = ListView(id="select_output_device_list")
        self.__output_device_list_view.focus()
        yield Vertical(
            Static("Select output device", id="select_output_device_title"),
            self.__output_device_list_view,
            SelectOutputDeviceButtons(id="select_output_device_buttons")
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        if button.id == "select_output_device_ok":
            if self.__selected_device != None:
                self.app.player.stop()
                self.app.player.set_output_device(self.__selected_device)
                self.app.pop_screen()
        elif button.id == "select_output_device_cancel":
            self.app.pop_screen()

    def on_list_view_selected(self, selected: ListView.Selected) -> None:
        self.__selected_device = selected.item.device
        if self.__previously_selected_item:
            self.__previously_selected_item.remove_class("selected")
        selected.item.add_class("selected")
        self.__previously_selected_item = selected.item

    def on_mount(self) -> None:
        apis = self.app.player.get_outout_device_list_by_api()
        list_view = self.query_one("#select_output_device_list")
        for api in apis:
            for device in api.devices:
                item = DeviceItem(device)
                list_view.append(item)
                player : HandcraftedAudioPlayer = self.app.player
                if player.current_device:
                    if player.current_device.index == device.index:
                        item.add_class("selected")
                        item.highlighted = True
                    else:
                        item.highlighted = False
                    self.__previously_selected_item = item


class SelectOutputDeviceScreen(Screen):
    DEFAULT_CSS="""
    SelectOutputDeviceScreen {
        align: center middle;
        background: $background 50%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield SelectOutputDeviceDialog()
        yield Footer()


class HandcraftedAudioPlayerApp(App):
    SCREENS = {"select_output_device": SelectOutputDeviceScreen()}
    DEFAULT_CSS = """
    #current_track_controls {
        dock: bottom;
        margin: 0 0 2 0
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "select_output_device", "Select Output"),
    ]

    def __init__(self, playlist : list, *args, **kwargs):
        self.__player = HandcraftedAudioPlayer()
        self.__player.set_playlist(playlist)
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
        if self.screen.id != "select_output_device_screen":
            self.push_screen(SelectOutputDeviceScreen(id="select_output_device_screen"))

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

    def on_mount(self) -> None:
        self.__player.on_track_changed.append(self.__on_track_changed)
        self.__current_playlist_data_table.add_columns(" ", "Title", "Artist", "Duration")
        if self.__player.current_playlist:
            for file in self.__player.current_playlist:
                t = time.gmtime(file.duration)
                self.__current_playlist_data_table.add_row(" ", file.title, file.artist, time.strftime("%M:%S", t))
