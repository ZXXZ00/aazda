import os
import sys
from parse import transform
from opensearch import bulk


# recursive ingest the file / folder
def ingest(path: str, ignore_dir: set[str] = set()):
    for root, dirs, files in os.walk(path, True):
        # ignore hidden file and path
        files = [f for f in files if not f[0] == "."]
        dirs[:] = [d for d in dirs if not d[0] == "." and d not in ignore_dir]

        bulk([transform(os.path.join(root, name)) for name in files])


def ingest_file(path: str):
    bulk([transform(path)])


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path>")
        return
    path = sys.argv[1]

    if os.path.isdir(path):
        return ingest(path)

    return ingest_file(path)


if __name__ == "__main__":
    main()
