import os
from Parser import Parser
from opensearch import FileMetadata, Mapping
from typing import Any, Callable, Dict, List, Tuple, Union
from datetime import datetime
from collections import defaultdict
from dateutil import parser as date_parser  # type: ignore
from tika import parser, detector  # type: ignore

URL = "http://localhost:9998/tika"

CastedValue = Union[int, float, str, bool, datetime, None]


def DEFAULT_FILTER(key: str, value: CastedValue) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        return False
    if isinstance(value, int):
        return False
    return not key.startswith(("X-TIKA", "Content-", "resourceName"))


# parsing using tika default true to get xml content
class TikaParser(Parser):
    metadata_filter: Callable[[str, CastedValue], bool]
    xmlContent: bool

    def __init__(
        self,
        metadata_filter: Callable[[str, CastedValue], bool] = DEFAULT_FILTER,
        xmlContent: bool = True,
    ) -> None:
        super().__init__()
        self.metadata_filter = metadata_filter
        self.xmlContent = xmlContent

    def to_metadata_mapping(
        self,
        key: str,
        values: List[Tuple[str, CastedValue]],
    ) -> Dict[str, Any] | None:
        result: Dict[str, Any] = defaultdict(list)
        for original, casted in values:
            if self.metadata_filter(key, casted):
                result[f"val_{type(casted).__name__.lower()}"].append(original)

        if len(result) > 0:
            # flatten the list if it's only one element
            ret = {
                key: value[0] if len(value) == 1 else value
                for key, value in result.items()
            }
            # transform key from "some:thing" to "thing"
            ret["key"] = key.split(":")[-1]
            return ret
        return None

    # always return UNKNOWN for the type, this doesn't call tika
    def extract_basic_metadata(self, path: str) -> FileMetadata:
        abs_path = os.path.abspath(path)
        stats = os.stat(abs_path)
        return FileMetadata(
            os.path.basename(path),
            abs_path,
            "UNKNOWN",
            stats.st_size,
            datetime.fromtimestamp(stats.st_ctime).isoformat(),
            datetime.fromtimestamp(stats.st_mtime).isoformat(),
        )

    def extract_metadata(self, path: str) -> FileMetadata:
        metadata = self.extract_basic_metadata(path)
        metadata.file_type = detector.from_file(path)  # MIME type
        return metadata

    def read_content(self, path: str) -> str:
        return parser.from_file(path, URL, "text")["content"]

    def parse(self, path: str) -> Mapping:
        # extract basic metadata to avoid two tika calls
        file_meta = self.extract_basic_metadata(path)
        parsed = parser.from_file(path, URL, xmlContent=self.xmlContent)
        metadata: Dict[str, Any] = parsed["metadata"]
        flattened_metadata = flatten_dict(metadata)
        normalized_metadata = normalize_dict(flattened_metadata)
        metadata_mapping = [
            mapping
            for key, values in normalized_metadata.items()
            if (mapping := self.to_metadata_mapping(key, values))
        ]
        file_type = (
            metadata["Content-Type"].split(";")[0]
            if "Content-Type" in metadata
            else detector.from_file(path)
        )
        return Mapping(
            name=file_meta.name,
            content=parsed["content"],
            path=file_meta.path,
            file_type=file_type,
            size=file_meta.size,
            created_at=file_meta.created_at,
            updated_at=file_meta.updated_at,
            metadata=metadata_mapping,
        )


# it's most likely a list of strings or string but use Any just in case
def try_cast(value: Any | List[Any]) -> List[CastedValue | Exception]:
    if isinstance(value, list):
        return [try_cast_str(item) for item in value]
    return [try_cast_str(value)]


# value is most likely a string but use Any just in case
def try_cast_str(value: Any) -> CastedValue | Exception:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if (
        value == ""
        or lowered == "none"
        or lowered == "null"
        or lowered == "nil"
        or lowered == "undefined"
    ):
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            try:
                return date_parser.parse(value)
            except (ValueError, OverflowError):
                try:
                    return str(value)
                except ValueError:
                    return Exception(f"Could not cast {value}")


# normalize a dictionary to have a list of tuples and filter out cast failure
def normalize_dict(
    d: Dict[str, Any],
) -> Dict[str, List[Tuple[str, CastedValue]]]:
    return {
        key: [
            (original, casted)
            for original, casted in zip(
                [value] if not isinstance(value, list) else value, try_cast(value)
            )
            if not isinstance(casted, Exception)
        ]
        for key, value in d.items()
    }


# flatten a dictionary compress key to parent.child
def flatten_dict(d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    items = []  # type: list
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)
