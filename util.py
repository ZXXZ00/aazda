import os
import sys

PRUNE_DIR_NAMES = {
    # Dependency & Compiler Build Folders
    "node_modules",
    "bower_components",
    "target",
    "build",
    "dist",
    "out",
    "venv",
    "env",
    "__pycache__",
    
    # System AppData/Caches
    "Library",
    "AppData",
    "Local Settings",
    "Caches",
    ".Trash",
    "$RECYCLE.BIN",
    "System Volume Information",
    
    # App Folders
    "Applications",
}

def is_app_package(dirname: str) -> bool:
    """Return True if *dirname* looks like an app package (has an alphabetic extension)."""
    if dirname.startswith("."):
        return False
    _, ext = os.path.splitext(dirname)
    return bool(ext) and ext[1:].isalpha()

def is_ignored_or_hidden(filepath: str, ignore_dir: tuple[str, ...] = ()) -> bool:
    # Retain for backward compatibility with external files importing this helper
    abs_path = os.path.abspath(filepath)
    if ignore_dir and abs_path.startswith(ignore_dir):
        return True

    # Windows hidden file check
    if sys.platform.startswith("win"):
        try:
            attribute = os.stat(abs_path).st_file_attributes
            if attribute & 0x2 != 0:
                return True
        except Exception:
            pass

    # Check path segments
    parts = [p for p in abs_path.split(os.sep) if p]
    if not parts:
        return False

    # Check parent segments
    for part in parts[:-1]:
        if part.startswith("."):
            return True
        if part in PRUNE_DIR_NAMES:
            return True
        if is_app_package(part):
            return True

    # Check leaf segment
    leaf = parts[-1]
    if leaf.startswith("."):
        return True
    if leaf in PRUNE_DIR_NAMES:
        return True

    return False

def is_hidden(filepath) -> bool:
    return is_ignored_or_hidden(filepath)

def walk(root: str, ignore_dir: tuple[str, ...]) -> list[str]:
    children = []
    # Resolve ignore directories once to speed up prefix checks
    abs_ignore_dirs = tuple(os.path.abspath(d) for d in ignore_dir)
    
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        abs_dirpath = os.path.abspath(dirpath)
        
        # If current directory itself is ignored, prune its subfolders and skip
        if abs_ignore_dirs and abs_dirpath.startswith(abs_ignore_dirs):
            dirnames[:] = []
            continue
            
        # Prune hidden and known-skip directories
        dirnames[:] = [
            d for d in dirnames
            if not (d.startswith(".") or d in PRUNE_DIR_NAMES)
        ]
        
        # Separate app packages from walkable directories
        walkable = []
        for d in dirnames:
            full_path = os.path.join(dirpath, d)
            children.append(full_path)  # Always collect the directory itself
            if not is_app_package(d):
                walkable.append(d)
            # else: collected but NOT walked into
        
        dirnames[:] = walkable
            
        # Collect file paths (ignore hidden dotfiles)
        for filename in filenames:
            if filename.startswith("."):
                continue
            children.append(os.path.join(dirpath, filename))
            
    return children
