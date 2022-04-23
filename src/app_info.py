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
    APP_NAME="Some App",
    APP_AUTHOR="Some Author",
    APP_PUBLISHER="Some Publisher",
    APP_URL="http://",
    APP_VERSION=_VerInfo(
        Major=1,
        Minor=2,
        Revision=3
    )
)