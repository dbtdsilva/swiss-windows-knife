import cx_Freeze
import os
import subprocess
from pathlib import Path
from src.app_info import APP_INFO
import logging

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
    sys.argv = sys.argv[:1] + ['build']

    icon_path = os.path.join("icons", 'coat-of-arms.ico')

    executables = [
        cx_Freeze.Executable(
            os.path.join(os.path.dirname(__file__), "src", "swiss_windows_knife.py"),
            target_name=APP_INFO.APP_NAME + ".exe",
            icon=icon_path,
            base='Win32GUI')
    ]

    build_options = {
        'silent': 2,
        'packages': ["numpy", "pysolar"],
        'excludes': ["tkinter", "unittest", "pydoc"],
        'include_files': [icon_path],
        'optimize': 1
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
              ' /DMyAppVersion="{}"'.format(APP_INFO.APP_VERSION) +\
              ' /DMyAppName="{}"'.format(APP_INFO.APP_NAME) +\
              ' /DMyAppPublisher="{}"'.format(APP_INFO.APP_PUBLISHER) +\
              ' /DMyAppURL="{}"'.format(APP_INFO.APP_URL) +\
              ' /DMyAppExeName="{}"'.format(APP_INFO.APP_NAME + ".exe") +\
              ' /Obuild\\installer' +\
              ' inno_setup.iss'
    logging.info(cmd)
    subprocess.call(cmd)


def usage():
    print(
        """
        Usage:
            build resources  -  Build resources.py
            build exe        -  Build executable using cx-Freeze.
            build installer  -  Build windows installer using Inno Setup.
        """)


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]

    if len(args) != 1:
        usage()
        sys.exit(1)

    mode = args[0]
    if mode == "resources":
        build_resources()
    elif mode == "dev":
        build_resources()
        from src.swiss_windows_knife import SwissWindowsKnife
        SwissWindowsKnife()
    elif mode == "exe":
        build_resources()
        build_exe()
    elif mode == "installer":
        build_resources()
        build_exe()
        build_win_install()
    else:
        usage()
        sys.exit(1)
