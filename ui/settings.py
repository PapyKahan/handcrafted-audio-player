from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, RadioButton, RadioSet, Static
from textual.screen import Screen
from core.device import HostApiInfo

class ApiRadioButton(RadioButton):
    hostapi : HostApiInfo
    def __init__(self, api : HostApiInfo, *args, **kwargs) -> None:
        self.hostapi = api
        return super().__init__(label=api.name, button_first=True, *args, **kwargs)


class SettingsDialog(Static):
    DEFAULT_CSS="""
    SelectOutputDeviceDialog {
        border: darkgrey round;
        content-align: center middle;
        width: 80;
        height: 17;
    }
    """
    
    def __init__(self, *args, **kwargs):
        __apis = self.app.player.get_outout_device_list_by_api()
        buttons : list[ApiRadioButton] = []
        for api in __apis:
            buttons.append(ApiRadioButton(api))
        self.__api_list_radio_set = RadioSet(*buttons)
        super().__init__(*args, **kwargs)
    
    def compose(self) -> ComposeResult:
        yield Vertical(
            self.__api_list_radio_set,
        )
        with Horizontal():
            yield Label(id="pressed")
        with Horizontal():
            yield Label(id="index")
    
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.query_one("#pressed", Label).update(
            f"Pressed button label: {event.pressed.label}"
        )
    
    def on_mount(self) -> None:
        pass

class SettingsScreen(Screen):
    DEFAULT_CSS = """
    SelectOutputDeviceScreen {
        align: center middle;
        background: $background 50%;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield SettingsDialog()
        yield Footer()
