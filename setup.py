from cx_Freeze import setup, Executable
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

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

def build_exe():
    build_options = {'packages': [], 'excludes': [], 'include_files': []}

    executables = [
        Executable(
            os.path.join(os.path.dirname(__file__), "src", "main.py"), 
            targetName="tray.exe",
            base='Win32GUI')
    ]

    setup(name='tray',
        version = '1.0',
        description = '',
        options = {'build_exe': build_options},
        executables = executables)

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
        #build_win_install()
    else:
        usage()
        sys.exit(1)
