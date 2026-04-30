import pytest

from swiss_windows_knife.plugins.device_display_mapper.device_listener import DeviceListener


@pytest.mark.parametrize("pnp_id,expected", [
    # Real USB device with VID+PID and serial-style suffix
    ("USB\\VID_046D&PID_085B&MI_02\\7&7C1799&0&0002", True),
    # Lowercase VID/PID is accepted (Windows reports both forms)
    ("USB\\vid_046d&pid_085b\\foo", True),
    # ROOT_HUB and similar synthetic entries are excluded
    ("USB\\ROOT_HUB30\\4&12345&0&0", False),
    ("USB\\ROOT\\anything", False),
    # Non-USB prefixes are rejected even when VID/PID looks valid
    ("HID\\VID_046D&PID_085B\\foo", False),
    ("PCI\\VEN_8086&DEV_1234", False),
    # USB prefix but no VID/PID pattern
    ("USB\\NOT_A_VID_PID_DEVICE", False),
    ("USB\\\\", False),
    # Empty / garbage
    ("", False),
])
def test_is_real_usb_device(pnp_id, expected):
    assert DeviceListener.is_real_usb_device(pnp_id) is expected
