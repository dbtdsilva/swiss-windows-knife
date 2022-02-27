
import time
import pyudev

def log_event(action, device):
    print(action, device)

def main():
    context = pyudev.Context()
    i = 0
    for device in context.list_devices(): 
        print(device)
        i += 1
    print(i)
    monitor = pyudev.Monitor.from_netlink(context)
    observer = pyudev.MonitorObserver(monitor, log_event)
    observer.start()
    while True:
        time.sleep(5)

if __name__ == "__main__":
    main()