from abc import ABC, abstractmethod
from opensearch import Mapping, FileMetadata

class Parser(ABC):
    supported: list[str] = []

    @abstractmethod
    def extract_metadata(self, path: str) -> FileMetadata:
        pass

    @abstractmethod
    def read_content(self, path: str) -> str:
        pass

    @abstractmethod
    def parse(self, path: str) -> Mapping:
        pass
