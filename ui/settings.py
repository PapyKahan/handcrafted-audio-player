from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Header, Markdown, RadioButton, RadioSet, Static
from textual.screen import Screen
from core.device import DeviceInfo, HostApiInfo
from core.player import HandcraftedAudioPlayer

class ApiRadioButton(RadioButton):
    hostapi : HostApiInfo
    def __init__(self, api : HostApiInfo, *args, **kwargs) -> None:
        self.hostapi = api
        return super().__init__(id=api.index, label=api.name, button_first=True, *args, **kwargs)

class DeviceRadioButton(RadioButton):
    device : DeviceInfo
    def __init__(self, device : DeviceInfo, *args, **kwargs) -> None:
        self.device = device
        if device.is_default_output_device:
            return super().__init__(id="device_" + str(device.index), label=device.name + " (default)", button_first=True, *args, **kwargs)
        else:
            return super().__init__(id="device_" + str(device.index), label=device.name, button_first=True, *args, **kwargs)

class DeviceSettingsPage(Static):
    DEFAULT_CSS="""
    DeviceSettingsPage {
        content-align: center middle;
        height: 100%;
    }

    #device-selection-group {
        width: 100%;
        height: auto;
    }
    """

    selected_device : DeviceInfo | None = None
    
    def __init__(self, *args, **kwargs):
        __apis = self.app.player.get_outout_device_list_by_api()
        api_buttons : list[ApiRadioButton] = []
        devices_radiosets : list[RadioSet] = []
        for api in __apis:
            api_buttons.append(ApiRadioButton(api))
            current_api_devices_buttons : list[RadioButton] = []
            for device in api.devices:
                current_api_devices_buttons.append(DeviceRadioButton(device))
            devices_radiosets.append(RadioSet(*current_api_devices_buttons, id="api_" + api.index))
        self.__api_list_radio_set = RadioSet(*api_buttons, id="api-list")
        self.__content_switcher = ContentSwitcher(*devices_radiosets, id="devices-list")
        super().__init__(*args, **kwargs)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="device-selection-group"):
                yield self.__api_list_radio_set
                yield self.__content_switcher
            with Horizontal(id="device-settings-group"):
                with ContentSwitcher(id="api-specific-settings", initial="no-device-selected"):
                    yield Markdown(markdown="No device selected", id="no-device-selected")
    
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "api-list":
            if self.selected_device:
                previous_device = self.query_one("#device_" + str(self.selected_device.index))
                previous_device.toggle()
            self.query_one("#devices-list").current = "api_" + event.pressed.id
        elif event.pressed.id and event.pressed.id.startswith("device_"):
            self.selected_device = event.pressed.device 

    def on_mount(self) -> None:
        player : HandcraftedAudioPlayer = self.app.player
        if player.current_device:
            self.query_one("#" + player.current_device.hostapi.index).toggle()
            self.query_one("#device_" + str(player.current_device.index)).toggle()
    

class SettingsScreen(Screen):
    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
        background: $background 50%;
    }

    #buttons {
        margin-bottom: 1;
        height: auto;
        width: auto;
    }
    
    #content-switcher {
        background: $panel;
        border: round $primary;
        width: 100%;
    }

    #footer-buttons {
        margin-top: 1;
        height: auto;
    }
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="settings-main"):
            with Horizontal(id="buttons"):  
                yield Button("Output device", id="device-settings")  
                yield Button("General", id="markdown")  
            with ContentSwitcher(initial="device-settings", id="content-switcher"):
                yield DeviceSettingsPage(id="device-settings")
                yield Markdown(id="markdown")
            with Horizontal(id="footer-buttons"):
                yield Button("Save", id="save")
                yield Button("Cancel", id="cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            selected_device : DeviceInfo | None = self.query_one(DeviceSettingsPage).selected_device
            if selected_device != None:
                if not self.app.player.current_device or self.app.player.current_device.index != selected_device.index:
                    self.app.player.stop()
                    self.app.player.set_output_device(selected_device)
                self.app.pop_screen()
        elif event.button.id == "cancel":
            self.app.pop_screen()
        else:
            self.query_one("#content-switcher").current = event.button.id
