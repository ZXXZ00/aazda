import os

from Parser import Parser
from PlainTextParser import PlainTextParser
from TikaParser import TikaParser


plain_text_parser = PlainTextParser()
tika_parser = TikaParser()

parsers: dict[str, Parser] = {
    ".txt": plain_text_parser,
    "text": plain_text_parser,
}


def transform(path: str):
    [_, ext] = os.path.splitext(path)
    parser = parsers.get(ext)
    if parser is None:
        parser = tika_parser
    mapping = parser.parse(path)
    return mapping
