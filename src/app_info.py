from collections import namedtuple


_AppInfo = namedtuple("AppInfo", [
    'APP_NAME',
    'APP_AUTHOR',
    'APP_PUBLISHER',
    'APP_URL',
    'APP_VERSION'
])

_VerInfo = namedtuple("VerInfo", [
    "Major",
    "Minor",
    "Revision"
])

APP_INFO = _AppInfo(
    APP_NAME="MonitorControllerKVM",
    APP_AUTHOR="Diogo Silva",
    APP_PUBLISHER="Diogo Silva",
    APP_URL="https://dsilva.pt",
    APP_VERSION=_VerInfo(
        Major=1,
        Minor=0,
        Revision=0
    )
)
