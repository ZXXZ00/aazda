from os import path
from sys import platform

HOME_DIRECTORY = path.expanduser("~")

# MacOS
MACOS_TRASH_DIR = path.join(HOME_DIRECTORY, ".Trash")
MACOS_LIBRARY_DIR = path.join(HOME_DIRECTORY, "Library")

# Linux
LINUX_TRASH_DIR = path.join(HOME_DIRECTORY, ".local", "share", "Trash")
LINUX_LIBRARY_DIR = path.join(HOME_DIRECTORY, ".local", "share")

# Windows
WINDOWS_TRASH_DIR = path.join(
    HOME_DIRECTORY, "AppData", "Local", "Microsoft", "Windows", "Recycle Bin"
)
WINDOWS_LIBRARY_DIR = path.join(
    HOME_DIRECTORY, "AppData", "Local", "Microsoft", "Windows", "Libraries"
)
WINDOWS_RECYCLE_BIN_DIR = path.join(HOME_DIRECTORY, "$Recycle.Bin")
WINDOWS_SYSTEM_DIR = path.join(HOME_DIRECTORY, "Windows")
WINDOWS_SYSTEM32_DIR = path.join(HOME_DIRECTORY, "Windows", "System32")
WINDOWS_PROGRAM_FILES_DIR = path.join(HOME_DIRECTORY, "Program Files")
WINDOWS_PROGRAM_FILES_X86_DIR = path.join(HOME_DIRECTORY, "Program Files (x86)")
WINDOWS_PROGRAM_FILES_X64_DIR = path.join(HOME_DIRECTORY, "Program Files (x64)")
WINDOWS_PROGRAM_FILES_ARM_DIR = path.join(HOME_DIRECTORY, "Program Files (ARM)")

# TODO: need to verify for non macOS
IGNORE_DIR = (
    tuple([MACOS_LIBRARY_DIR])
    if platform == "darwin"
    else tuple([LINUX_LIBRARY_DIR])
    if platform == "linux"
    else tuple([WINDOWS_LIBRARY_DIR])
)
TRASH_DIR = MACOS_TRASH_DIR if platform == "darwin" else None
