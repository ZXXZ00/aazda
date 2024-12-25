import os
from opensearch import FileMetadata, Mapping
from Parser import Parser


class PlainTextParser(Parser):
    supported = ['.txt']

    def extract_metadata(self, path: str) -> FileMetadata:
        [_, ext] = os.path.splitext(path)
        if ext not in self.supported:
            raise Exception(ext + ' does not match parser type')
        abs_path = os.path.abspath(path)
        stats = os.stat(abs_path)
        return FileMetadata(abs_path, stats.st_size,
                            int(stats.st_ctime*1000), int(stats.st_mtime*1000))

    def read_content(self, path: str) -> str:
        with open(path) as f:
            return f.read()
    
    def parse(self, path: str) -> Mapping:
        metadata = self.extract_metadata(path)
        content = self.read_content(path)
        return Mapping(name=os.path.basename(path),
                       content=content,
                       path=metadata.path,
                       size=metadata.size,
                       created_at=metadata.created_at,
                       updated_at=metadata.updated_at)