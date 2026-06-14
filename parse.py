import os

from DirParser import DirParser
from Parser import Parser
from PlainTextParser import PlainTextParser
from TikaParser import TikaParser

dir_parser = DirParser()
plain_text_parser = PlainTextParser()
tika_parser = TikaParser()

parsers: dict[str, Parser] = {
    ".txt": plain_text_parser,
    "text": plain_text_parser,
}


def transform(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"The path {path} does not exist.")
    if os.path.isdir(path):
        return dir_parser.parse(path)
    [_, ext] = os.path.splitext(path)
    parser = parsers.get(ext)
    if parser is None:
        parser = tika_parser
    mapping = parser.parse(path)
    return mapping
