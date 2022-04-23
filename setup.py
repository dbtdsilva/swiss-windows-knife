import cx_Freeze
import os
import sys
import subprocess
import shutil
from distutils.core import Command
from pathlib import Path

# So we can access app_info.py
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
BASE_DIR = Path(__file__).parent.absolute()

TO_DELETE = [
    "lib/PySide6/Qt6DRender.pyd",
    "lib/PySide6/Qt63DRender.dll",
    "lib/PySide6/Qt6Charts.dll",
    "lib/PySide6/Qt6Location.dll",
    "lib/PySide6/Qt6Pdf.dll",
    "lib/PySide6/Qt6Quick.dll",
    "lib/PySide6/Qt6WebEngineCore.dll",
    "lib/PySide6/QtCharts.pyd",
    "lib/PySide6/QtMultimedia.pyd",
    "lib/PySide6/QtOpenGLFunctions.pyd",
    "lib/PySide6/QtOpenGLFunctions.pyi",
    "lib/PySide6/d3dcompiler_47.dll",
    "lib/PySide6/opengl32sw.dll",
    "lib/PySide6/lupdate.exe",
    "lib/PySide6/translations",
    "lib/aiohttp/_find_header.c",
    "lib/aiohttp/_frozenlist.c",
    "lib/aiohttp/_helpers.c",
    "lib/aiohttp/_http_parser.c",
    "lib/aiohttp/_http_writer.c",
    "lib/aiohttp/_websocket.c",
    # Improve this to work with different versions.
    "lib/aiohttp/python39.dll",
    "lib/lazy_object_proxy/python39.dll",
    "lib/lxml/python39.dll",
    "lib/markupsafe/python39.dll",
    "lib/multidict/python39.dll",
    "lib/numpy/core/python39.dll",
    "lib/numpy/fft/python39.dll",
    "lib/numpy/linalg/python39.dll",
    "lib/numpy/random/python39.dll",
    "lib/python39.dll",
    "lib/recordclass/python39.dll",
    "lib/regex/python39.dll",
    "lib/test",
    "lib/yarl/python39.dll",
]

COPY_TO_ZIP = [
    "LICENSE.txt",
    "README.md",
    "NOTICE.md",
    # Must have been generated with pip-licenses before. Many dependencies
    # require their license to be distributed with their binaries.
    "lib_licenses.txt",
]


class FinalizeCXFreezeCommand(Command):
    description = "Prepare cx_Freeze build dirs and create a zip"
    user_options = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self):
        print("what")
        (BASE_DIR / "dist").mkdir(exist_ok=True)
        for path in (BASE_DIR / "build").iterdir():
            if path.name.startswith("exe.") and path.is_dir():
                for cleanse_suffix in TO_DELETE:
                    cleanse_path = path / cleanse_suffix
                    shutil.rmtree(cleanse_path, ignore_errors=True)
                    try:
                        os.unlink(cleanse_path)
                    except:
                        pass
                for to_copy in COPY_TO_ZIP:
                    shutil.copy(BASE_DIR / to_copy, path / to_copy)
                shutil.copytree(BASE_DIR / "addon_examples", path / "addon_examples")
                zip_path = BASE_DIR / "dist" / path.name
                shutil.make_archive(zip_path, "zip", path)


def _get_ver_string():
    from app_info import APP_INFO

    return "{}.{}.{}".format(
        APP_INFO.APP_VERSION.Major,
        APP_INFO.APP_VERSION.Minor,
        APP_INFO.APP_VERSION.Revision,
    )
def build_resources():
    QRC_FILE = 'resources.qrc'
    PY_OUTPUT = os.path.join('src', 'resources.py')

    cmd = f"pyside6-rcc {QRC_FILE} -o {PY_OUTPUT}"
    print(f"Executing {cmd}...")

    ret_code = os.system(cmd)
    if ret_code == 0:
        print(f"Created resources under {PY_OUTPUT} with success")
    else:
        print(f"Failed to generate resources under {PY_OUTPUT}")
        exit(1)
    cmd_list = f"pyside6-rcc {QRC_FILE} --list-mapping"
    os.system(cmd_list)

def build_exe():
    sys.argv = sys.argv[:1] + ['build']

    icon_path = os.path.join("icons", 'eye-fill.ico')

    executables = [
        cx_Freeze.Executable(
            os.path.join(os.path.dirname(__file__), "src", "main.py"), 
            target_name="main.exe",
            icon=icon_path,
            base='Win32GUI')
    ]
    
    build_options = {
        'silent': 2,
        'packages': [], 
        'excludes': ["tkinter", "unittest", "email", "http", "xml", "pydoc"],
        'include_files': [ icon_path ],
        
        'optimize': 2
    }

    cx_Freeze.setup(
        name='tray',
        version = '1.0.0',
        description = '',
        options = {'build_exe': build_options},
        executables = executables,
        #cmdclass={"finalize_cxfreeze": FinalizeCXFreezeCommand}
        )

def build_win_install():
    from app_info import APP_INFO
    cmd = '"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"' +\
              ' /DMyAppVersion="{}"'.format(_get_ver_string()) +\
              ' /DMyAppName="{}"'.format(APP_INFO.APP_NAME) +\
              ' /DMyAppPublisher="{}"'.format(APP_INFO.APP_PUBLISHER) +\
              ' /DMyAppURL="{}"'.format(APP_INFO.APP_URL) +\
              ' /DMyAppExeName="{}"'.format(APP_INFO.APP_NAME + ".exe") +\
              ' inno_setup.iss'
    print(cmd)

    subprocess.call(cmd)

def usage():
    import sys
    sys.stdout.write(
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
