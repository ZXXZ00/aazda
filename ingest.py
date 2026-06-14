import os
import sys
from typing import Iterable, Optional

from parse import transform
from opensearch import bulk, Mapping
from path_env import HOME_DIRECTORY, IGNORE_DIR
from util import walk


# recursive ingest the file / folder
def ingest_recursive(path: str, ignore_dir: tuple[str, ...] = ()):
    children = walk(path, ignore_dir)
    result: list[Mapping] = []
    for child in children:
        try:
            result.append(transform(child))
        except Exception as e:
            print(f"Error parsing {child}: {e}")
    bulk(result)


def ingest_paths(paths: Iterable[str], ignore_path_does_not_exist: bool = False):
    result: list[Mapping] = []
    for path in paths:
        try:
            result.append(transform(path))
        except Exception as e:
            if ignore_path_does_not_exist and isinstance(e, FileNotFoundError):
                continue
            print(f"Error parsing {path}: {e}")
    bulk(result)


def ingest_all(ignore: Optional[tuple[str, ...]] = None):
    if ignore is None:
        ignore = IGNORE_DIR
    return ingest_recursive(HOME_DIRECTORY, ignore)


def main():
    if len(sys.argv) == 1:
        ingest_all()
        return
    if len(sys.argv) != 2:
        print("Usage: python ingest.py <path>")
        return
    path = sys.argv[1]

    if os.path.isdir(path):
        return ingest_recursive(path)

    return ingest_paths([path])


if __name__ == "__main__":
    main()
