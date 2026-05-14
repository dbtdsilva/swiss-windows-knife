from collections import namedtuple

__version__ = "1.19.0"

_AppInfo = namedtuple("AppInfo", [
    'APP_NAME',
    'APP_TAGLINE',
    'APP_AUTHOR',
    'APP_PUBLISHER',
    'APP_URL',
    'APP_VERSION',
    'APP_LICENSE',
])

APP_INFO = _AppInfo(
    APP_NAME="Swiss Windows Knife",
    APP_TAGLINE="A personal tray-app toolkit for taming Windows monitors, displays, and home-automation bridges.",
    APP_AUTHOR="Diogo Silva",
    APP_PUBLISHER="Diogo Silva",
    APP_URL="https://github.com/dbtdsilva/swiss-windows-knife",
    APP_VERSION=__version__,
    APP_LICENSE="MIT",
)
