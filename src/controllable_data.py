import monitorcontrol

class ControllableData:

    def __init__(self) -> None:
        self.input_on_disconnect = monitorcontrol.InputSource.HDMI1
        self.input_on_connect = monitorcontrol.InputSource.DP1

        self.brightness = None
        self.contrast = 90