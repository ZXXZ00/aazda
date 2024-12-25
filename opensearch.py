from dataclasses import dataclass, fields
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
        "char_filter": ["remove_underscore"],
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
    "index": {"number_of_shards": 2},
    "analysis": {
        "analyzer": stemmed_analyzer,
        "filter": stop_words,
        "char_filter": remove_underscore,
    },
}


@dataclass
class FileMetadata:
    path: str
    size: int
    created_at: int
    updated_at: int


@dataclass
class Mapping:
    name: str
    content: str
    path: str
    size: int
    created_at: int
    updated_at: int

    def to_json(self):
        return {
            "name": self.name,
            "content": self.content,
            "path": self.path,
            "size": self.size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
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
        "size": {"type": "unsigned_long"},
        "created_at": {"type": "date"},
        "updated_at": {"type": "date"},
    }
}


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
def bulk(docs: list[Mapping]) -> bool:
    if len(docs) == 0:
        return True
    json_array = map(lambda x: x.to_json(), docs)
    operations = [{"index": {"_index": index_name}}] * (2 * len(docs))
    operations[1::2] = json_array

    res = client.bulk(operations)
    print(res)
    return not res["errors"]


def search(query):
    return client.search(body=query)
