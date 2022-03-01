import win32serviceutil
import win32service
import win32event
import servicemanager

import win32gui
import win32gui_struct
import sys
struct = win32gui_struct.struct
pywintypes = win32gui_struct.pywintypes
import win32con

# https://docs.microsoft.com/en-us/windows/win32/devio/device-management-events
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
# https://docs.microsoft.com/en-us/windows-hardware/drivers/install/guid-devinterface-mouse
GUID_DEVINTERFACE_REGISTER = "{378DE44C-56EF-11D1-BC8C-00A0C91405DD}"

class DeviceEventService (win32serviceutil.ServiceFramework):
  _svc_name_ = "MonitorInputChangerOnUsbToggleSvc"
  _svc_display_name_ = "Monitor Input Changer Service"
  _svc_description_ = "Handle USB notifications to change monitor input"

  def __init__(self, args):
    win32serviceutil.ServiceFramework.__init__(self, args)
    self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
    filter = win32gui_struct.PackDEV_BROADCAST_DEVICEINTERFACE(
      GUID_DEVINTERFACE_REGISTER
    )
    
    if self.ssh is not None:
      self.hDevNotify = win32gui.RegisterDeviceNotification(
        self.ssh,
        filter,
        win32con.DEVICE_NOTIFY_SERVICE_HANDLE
      )

  #
  # Add to the list of controls already handled by the underlying
  # ServiceFramework class. We're only interested in device events
  #
  def GetAcceptedControls(self):
    rc = win32serviceutil.ServiceFramework.GetAcceptedControls (self)
    rc |= win32service.SERVICE_CONTROL_DEVICEEVENT
    return rc

  #
  # Handle non-standard service events (including our device broadcasts)
  # by logging to the Application event log
  #
  def SvcOtherEx(self, control, event_type, data):
    if control == win32service.SERVICE_CONTROL_DEVICEEVENT:
      if event_type == DBT_DEVICEARRIVAL:
        servicemanager.LogMsg(
          servicemanager.EVENTLOG_INFORMATION_TYPE,
          0xF000,
          ("Device %s arrived" % data, '')
        )
      elif event_type == DBT_DEVICEREMOVECOMPLETE:
        servicemanager.LogMsg(
          servicemanager.EVENTLOG_INFORMATION_TYPE,
          0xF000,
          ("Device %s removed" % data, '')
        )

  def SvcStop(self):
    servicemanager.LogMsg(
      servicemanager.EVENTLOG_INFORMATION_TYPE,
      servicemanager.PYS_SERVICE_STOPPING,
      (self._svc_name_, ''))

    self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
    win32event.SetEvent(self.hWaitStop)

  def SvcDoRun(self):
    servicemanager.LogMsg(
      servicemanager.EVENTLOG_INFORMATION_TYPE,
      servicemanager.PYS_SERVICE_STARTED,
      (self._svc_name_, ''))

    win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
    servicemanager.LogMsg(
      servicemanager.EVENTLOG_INFORMATION_TYPE,
      servicemanager.PYS_SERVICE_STOPPED,
      (self._svc_name_, ''))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DeviceEventService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(DeviceEventService)