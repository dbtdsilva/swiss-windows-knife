# Monitor Input Changer on USB toggle
### What is it?
A service that will automatically swap between monitors inputs (eg. from HDMI to DP) when a new mouse / keyboard is connected or disconnected. When the mouse / keyboard is disconnected, it changes to HDMI, when the mouse / keyboard is connected, it changes back to DP.
This is quite useful when you have a USB switch that has a button to switch the USBs between two systems, because it will also allow to change the monitor input source when the button is pressed as long as the keyboard or the mouse is on that USB switch. 
This service respects Win32 API (https://docs.microsoft.com/en-us/windows/win32/api/) and therefore it uses its tools, like Services or Event Viewer to control the service or logging events.

### How does it work?
It listens for USB notifications (Windows specific) and when there is a new keyboard or mouse, it changes the input source of all monitors using DDC/CI interface to communicate.

### Generate the executable
```sh
pyinstaller.exe --hidden-import win32timezone main.py -F
```

### Installing the service
```sh
main.exe install
```

### Manipulating the service
Controlling the service can be done through CLI or in Services panel from Windows
```sh
main.exe start|stop
```
It is also possible to debug from the Event Viewer from Windows