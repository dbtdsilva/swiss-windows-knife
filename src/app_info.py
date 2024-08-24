from collections import namedtuple


__version__ = "1.3.2"

_AppInfo = namedtuple("AppInfo", [
    'APP_NAME',
    'APP_AUTHOR',
    'APP_PUBLISHER',
    'APP_URL',
    'APP_VERSION'
])

APP_INFO = _AppInfo(
    APP_NAME="MonitorControllerKVM",
    APP_AUTHOR="Diogo Silva",
    APP_PUBLISHER="Diogo Silva",
    APP_URL="https://github.com/dbtdsilva/monitor-controller-kvm",
    APP_VERSION=__version__
)
