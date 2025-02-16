import base64
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional
from opensearchpy import OpenSearch
from stop_words import english

host = "localhost"
port = 9200

client = OpenSearch(hosts=[{"host": host, "port": port}])

index_name = "test"

# filter: stop word
stop_words = {"custom_stop": {"type": "stop", "stopwords": english.stop_words}}

# char filter: underscore
remove_underscore = {
    "remove_underscore": {"type": "pattern_replace", "pattern": "_", "replacement": " "}
}

# analyzer: stemmed
stemmed_analyzer = {
    "stemmed_analyzer": {
        "tokenizer": "standard",
        "char_filter": ["html_strip", "remove_underscore"],
        "filter": [
            "lowercase",
            "custom_stop",
            "keyword_repeat",  # keep unstemmed
            "snowball",  # stemmer
            "remove_duplicates",
        ],
    }
}

setting = {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "analysis": {
        "analyzer": stemmed_analyzer,
        "filter": stop_words,
        "char_filter": remove_underscore,
    },
}


@dataclass
class FileMetadata:
    name: str
    path: str
    file_type: str
    size: int
    created_at: str
    updated_at: str


@dataclass
class Mapping:
    name: str
    content: str
    path: str
    file_type: str
    size: int
    created_at: str
    updated_at: str
    metadata: Optional[List[Dict[str, Any]]] = None

    def to_json(self):
        return {
            "name": self.name,
            "content": self.content,
            "path": self.path,
            "file_type": self.file_type,
            "size": self.size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


text_fields = list(
    map(
        lambda field: field.name,
        filter(lambda field: type(field) is str, fields(Mapping)),
    )
)

mapping = {
    "properties": {
        "name": {
            "type": "search_as_you_type",
            "fields": {
                "text": {
                    "type": "text",
                    "analyzer": "stemmed_analyzer",
                    "search_analyzer": "stemmed_analyzer",
                }
            },
        },
        "content": {
            "type": "text",
            "analyzer": "stemmed_analyzer",
            "search_analyzer": "stemmed_analyzer",
        },
        "path": {"type": "keyword"},
        "file_type": {"type": "keyword"},
        "size": {"type": "unsigned_long"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
        "metadata": {
            "type": "nested",
            "dynamic": "strict",
            "properties": {
                "key": {"type": "keyword"},
                "val_str": {
                    "type": "text",
                    "analyzer": "stemmed_analyzer",
                    "search_analyzer": "stemmed_analyzer",
                },
                "val_datetime": {"type": "date"},
                "val_int": {"type": "integer"},
                "val_float": {"type": "float"},
            },
        },
    }
}


def get_id(mapping: Mapping) -> str:
    encoded_id = base64.urlsafe_b64encode(mapping.path.encode()).decode()
    return encoded_id[:512]


def create_index():
    res = client.indices.create(
        index_name, body={"settings": setting, "mappings": mapping}
    )
    print(res)
    return res


def delete_index():
    res = client.indices.delete(index_name)
    print(res)
    return res


# return success or not
def bulk(docs: List[Mapping]) -> bool:
    if len(docs) == 0:
        return True

    operations = []
    for doc in docs:
        operations.append({"index": {"_index": index_name, "_id": get_id(doc)}})
        operations.append(doc.to_json())

    res = client.bulk(operations)
    print(res)
    return not res["errors"]


# return the number of deleted documents
def delete_by_path_query(paths: list[str]) -> int:
    if len(paths) == 0:
        return 0
    res = client.delete_by_query(
        index=index_name,
        body={
            "query": {
                "terms": {
                    "path": paths,
                }
            }
        },
    )
    print(res)
    return res["deleted"]


def search(query):
    return client.search(body=query)
