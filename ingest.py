import os
import sys
from PlainTextParser import PlainTextParser
from opensearch import bulk

plain_text_parser = PlainTextParser()

parsers = {".txt": plain_text_parser}
# set of supported extensions
supported = parsers.keys()


def transform(path: str):
    [_, ext] = os.path.splitext(path)
    parser = parsers.get(ext)
    if parser is None:
        raise Exception(ext + " is not supported")
    mapping = parser.parse(path)
    return mapping


# recursive ingest the file / folder
def ingest(path: str):
    for root, dirs, files in os.walk(path, True):
        # ignore hidden file and path
        files = [
            f for f in files if not f[0] == "." and os.path.splitext(f)[1] in supported
        ]
        dirs[:] = [d for d in dirs if not d[0] == "."]

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

    [_, ext] = os.path.splitext(path)
    if ext not in supported:
        print("Unsupported file format\nSupported file formats:", supported)
        return
    return ingest_file(path)


if __name__ == "__main__":
    main()
