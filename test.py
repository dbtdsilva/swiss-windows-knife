# Demo RegisterDeviceNotification etc.  Creates a hidden window to receive
# notifications.  See serviceEvents.py for an example of a service doing
# that.
import sys, time
import win32gui, win32con, win32api, win32file
import win32gui_struct, winnt

# These device GUIDs are from Ioevent.h in the Windows SDK.  Ideally they
# could be collected somewhere for pywin32...
GUID_DEVINTERFACE_USB_DEVICE = "{884b96c3-56ef-11d1-bc8c-00a0c91405dd}"

# WM_DEVICECHANGE message handler.
def OnDeviceChange(hwnd, msg, wp, lp):
    # Unpack the 'lp' into the appropriate DEV_BROADCAST_* structure,
    # using the self-identifying data inside the DEV_BROADCAST_HDR.
    info = win32gui_struct.UnpackDEV_BROADCAST(lp)
    print("Device change notification:", wp, str(info))
    if wp==win32con.DBT_DEVICEREMOVECOMPLETE:
        pass
    if wp==win32con.DBT_DEVICEARRIVAL:
        pass
        
    return True


def TestDeviceNotifications(dir_names):
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = 'test_devicenotify'
    wc.style =  win32con.CS_GLOBALCLASS|win32con.CS_VREDRAW | win32con.CS_HREDRAW
    wc.hbrBackground = win32con.COLOR_WINDOW+1
    wc.lpfnWndProc={win32con.WM_DEVICECHANGE:OnDeviceChange}
    class_atom=win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(wc.lpszClassName,
        'Testing some devices',
        # no need for it to be visible.
        win32con.WS_CAPTION,
        100,100,900,900, 0, 0, 0, None)

    hdevs = []
    # Watch for all USB device notifications
    filter = win32gui_struct.PackDEV_BROADCAST_DEVICEINTERFACE(
                                        GUID_DEVINTERFACE_USB_DEVICE)
    hdev = win32gui.RegisterDeviceNotification(hwnd, filter,
                                               win32con.DEVICE_NOTIFY_WINDOW_HANDLE)

    # now start a message pump and wait for messages to be delivered.
    print("Watching", len(hdevs), "handles - press Ctrl+C to terminate, or")
    print("add and remove some USB devices...")
    win32gui.PumpMessages()
    win32gui.DestroyWindow(hwnd)
    win32gui.UnregisterClass(wc.lpszClassName, None)
    hdev.close()

if __name__=='__main__':
    # optionally pass device/directory names to watch for notifications.
    # Eg, plug in a USB device - assume it connects as E: - then execute:
    # % win32gui_devicenotify.py E:
    # Then remove and insert the device.
    TestDeviceNotifications(sys.argv[1:])