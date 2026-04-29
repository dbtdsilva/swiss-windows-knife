import logging
import os
import subprocess
from pathlib import Path

from src.app_info import APP_INFO

BASE_DIR = Path(__file__).parent.absolute()


def build_resources():
    QRC_FILE = 'resources.qrc'
    PY_OUTPUT = os.path.join('src', 'resources.py')

    cmd = f"pyside6-rcc {QRC_FILE} -o {PY_OUTPUT}"
    logging.info(f"Executing {cmd}...")

    ret_code = os.system(cmd)
    if ret_code == 0:
        logging.info(f"Created resources under {PY_OUTPUT} with success")
    else:
        logging.error(f"Failed to generate resources under {PY_OUTPUT}")
        exit(1)
    cmd_list = f"pyside6-rcc {QRC_FILE} --list-mapping"
    os.system(cmd_list)


def build_exe():
    import cx_Freeze
    sys.argv = sys.argv[:1] + ['build']

    icon_path = os.path.join("icons", 'coat-of-arms.ico')

    executables = [
        cx_Freeze.Executable(
            os.path.join(os.path.dirname(__file__), "src", "swiss_windows_knife.py"),
            target_name=APP_INFO.APP_NAME.replace(' ', '') + ".exe",
            icon=icon_path,
            base='Win32GUI')
    ]

    build_options = {
        'silent': 2,
        'packages': ["numpy", "pysolar", "wmi", "pytz", "paho.mqtt", "requests"],
        'excludes': ["tkinter", "unittest", "pydoc"],
        'include_files': [icon_path],
        'optimize': 0,
    }

    cx_Freeze.setup(
        name='tray',
        version=APP_INFO.APP_VERSION,
        description='',
        options={'build_exe': build_options},
        executables=executables
        )


def build_win_install():
    cmd = '"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"' +\
        f' /DMyAppVersion="{APP_INFO.APP_VERSION}"' +\
        f' /DMyAppName="{APP_INFO.APP_NAME}"' +\
        ' /DMyAppNameNoSpaces="{}"'.format(APP_INFO.APP_NAME.replace(' ', '')) +\
        f' /DMyAppPublisher="{APP_INFO.APP_PUBLISHER}"' +\
        f' /DMyAppURL="{APP_INFO.APP_URL}"' +\
        ' /DMyAppExeName="{}"'.format(APP_INFO.APP_NAME.replace(' ', '') + ".exe") +\
        ' /DMyAppIcon={}'.format(os.path.join("icons", 'coat-of-arms.ico')) +\
        ' /DMyAppIconName={}'.format('coat-of-arms.ico') +\
        ' /Obuild\\installer' +\
        ' inno_setup.iss'
    logging.info(cmd)
    subprocess.call(cmd)


def usage():
    print(
        """
        Usage:
            resources  - Build resources.py
            dev        - Execute the application without compiling Python code
            exe        - Build executable using cx-Freeze.
            installer  - Build windows installer using Inno Setup.
        """)


CLI_MODES = ("resources", "dev", "exe", "installer")


if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) == 2 and sys.argv[1] in CLI_MODES else None

    if mode == "resources":
        build_resources()
    elif mode == "dev":
        build_resources()
        from src.swiss_windows_knife import SwissWindowsKnife
        SwissWindowsKnife(True)
    elif mode == "exe":
        build_resources()
        build_exe()
    elif mode == "installer":
        build_resources()
        build_exe()
        build_win_install()
    else:
        # pip / setuptools invokes setup.py for back-compat metadata extraction;
        # delegate to setuptools so pyproject.toml's [project] table drives the install.
        from setuptools import setup
        setup()
