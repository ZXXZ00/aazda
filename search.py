from opensearch import search, text_fields

def search_word(input: str):
    query = build_query(input)
    return search(query)

def build_query(query: str):
    return {
        'query': {
            'multi_match': {
                'query': query,
                'fields': text_fields
            }
        }
    }