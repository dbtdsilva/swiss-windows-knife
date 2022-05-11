# Monitor Controller KVM
### What is it?
A tray application that will automatically swap between monitors inputs (eg. from HDMI to DP) when a new mouse / keyboard is connected or disconnected. When the mouse / keyboard is disconnected, it changes to HDMI, when the mouse / keyboard is connected, it changes back to DP.
This is quite useful when you have a USB switch that has a button to switch the USBs between two systems, because it will also allow to change the monitor input source when the button is pressed as long as the keyboard or the mouse is on that USB switch.

### How does it work?
It listens for USB notifications (Windows specific) and when there is a new keyboard or mouse, it changes the input source of all monitors using DDC/CI interface to communicate.

### Generate the installer
The installer will be located under build/installer/MonitorControllerKVM-<version>.exe by using:
```sh
python setup installer
```
Alternatively, you can also check the releases on GitHub.
