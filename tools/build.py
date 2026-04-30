"""Build and run helpers for swiss-windows-knife.

Subcommands:
    resources  Regenerate src/resources.py from resources.qrc via pyside6-rcc.
    dev        Regenerate resources, then run the tray in dev mode.
    exe        Regenerate resources, then build the cx_Freeze frozen exe.
    installer  Regenerate resources, build exe, then build the Inno Setup installer.
"""
import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.app_info import APP_INFO  # noqa: E402

QRC_FILE = "resources.qrc"
PY_OUTPUT = os.path.join("src", "resources.py")
ICON_PATH = os.path.join("icons", "coat-of-arms.ico")


def build_resources() -> None:
    cmd = f"pyside6-rcc {QRC_FILE} -o {PY_OUTPUT}"
    logging.info("Executing %s...", cmd)
    if os.system(cmd) != 0:
        logging.error("Failed to generate %s", PY_OUTPUT)
        sys.exit(1)
    logging.info("Created %s", PY_OUTPUT)
    os.system(f"pyside6-rcc {QRC_FILE} --list-mapping")


def build_exe() -> None:
    import cx_Freeze
    sys.argv = sys.argv[:1] + ["build"]

    executables = [
        cx_Freeze.Executable(
            os.path.join(str(ROOT), "src", "swiss_windows_knife.py"),
            target_name=APP_INFO.APP_NAME.replace(" ", "") + ".exe",
            icon=ICON_PATH,
            base="Win32GUI",
        )
    ]

    build_options = {
        "silent": 2,
        "packages": ["numpy", "pysolar", "wmi", "pytz", "paho.mqtt", "requests"],
        "excludes": ["tkinter", "unittest", "pydoc"],
        "include_files": [ICON_PATH],
        "optimize": 0,
    }

    cx_Freeze.setup(
        name="tray",
        version=APP_INFO.APP_VERSION,
        description="",
        options={"build_exe": build_options},
        executables=executables,
    )


def build_installer() -> None:
    cmd = (
        '"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"'
        f' /DMyAppVersion="{APP_INFO.APP_VERSION}"'
        f' /DMyAppName="{APP_INFO.APP_NAME}"'
        f' /DMyAppNameNoSpaces="{APP_INFO.APP_NAME.replace(" ", "")}"'
        f' /DMyAppPublisher="{APP_INFO.APP_PUBLISHER}"'
        f' /DMyAppURL="{APP_INFO.APP_URL}"'
        f' /DMyAppExeName="{APP_INFO.APP_NAME.replace(" ", "")}.exe"'
        f' /DMyAppIcon={ICON_PATH}'
        ' /DMyAppIconName=coat-of-arms.ico'
        ' /Obuild\\installer'
        ' inno_setup.iss'
    )
    logging.info(cmd)
    subprocess.call(cmd)


def run_dev() -> None:
    from src.swiss_windows_knife import SwissWindowsKnife
    SwissWindowsKnife(True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build helpers for swiss-windows-knife.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("resources", help="Regenerate src/resources.py from resources.qrc.")
    sub.add_parser("dev", help="Build resources and run the tray in dev mode.")
    sub.add_parser("exe", help="Build resources and the cx_Freeze frozen exe.")
    sub.add_parser("installer", help="Build resources, exe, and Inno Setup installer.")
    args = parser.parse_args()

    if args.mode == "resources":
        build_resources()
    elif args.mode == "dev":
        build_resources()
        run_dev()
    elif args.mode == "exe":
        build_resources()
        build_exe()
    elif args.mode == "installer":
        build_resources()
        build_exe()
        build_installer()


if __name__ == "__main__":
    main()
