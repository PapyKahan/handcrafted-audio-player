from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Button, Static
from core.player import DeviceInfo, HandcraftedAudioPlayer

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

    def on_mount(self) -> None:
        apis = self.app.player.get_outout_device_list_by_api()
        self.__output_device_list_view.clear()
        for api in apis:
            for device in api.devices:
                item = DeviceItem(device)
                self.__output_device_list_view.append(item)
                player : HandcraftedAudioPlayer = self.app.player
                if player.current_device:
                    if player.current_device.index == device.index:
                        self.__output_device_list_view.index = len(self.__output_device_list_view.children) - 1


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
