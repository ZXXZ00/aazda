import { useState, useEffect } from 'react';
import axios from 'axios';


const URL = 'http://localhost:9200/test/_search';

export function generateQuery(query: string) {
  return {
    query: {
      bool: {
        should: [
          {
            multi_match: {
              query,
              type: 'bool_prefix',
              fields: ['name', 'name._2gram', 'name._3gram', 'name.text']
            }
          },
          {
            nested: {
              path: 'metadata',
              query: {
                match: {
                  'metadata.val_str': query
                }
              },
              inner_hits: {}
            }
          },
          {
            match: {
              content: query
            }
          }
        ]
      }
    },
    highlight: {
      fields: {
        content: {}
      }
    },
    _source: false,
    fields: ['name', 'path', 'created_at', 'updated_at'],
  };
}

interface RawSearchFieldMapping {
  name: string[],
  path: string[],
  created_at: string[],
  updated_at: string[]
}

// assume each field only has one value
type SearchFieldMapping = {
  [K in keyof RawSearchFieldMapping]: RawSearchFieldMapping[K][number];
};

interface Highlight {
  content: string[]
}

type StringValue = {
  key: string,
  val_str: string
}

type DateValue = {
  key: string,
  val_date: string
}

interface InnerHits {
  metadata: {
    hits: {
      hits: {
        _source: StringValue | DateValue
      }[]
    }
  }
}

export interface SearchResult {
  _index: string,
  _id: string,
  _score: number,
  fields: SearchFieldMapping
  highlight?: Highlight,
  inner_hits?: InnerHits
}

type RawSearchResult = Omit<SearchResult, 'fields'> & {
  fields: RawSearchFieldMapping
};

export function useSearch(query: string, debounceTime = 500) {
  const [results, setResults] = useState<SearchResult[]>([]);  // Holds the search results
  const [loading, setLoading] = useState(false);  // Indicates if a search is in progress

  useEffect(() => {
    // If the query is empty, don't trigger search
    if (!query) {
      setResults([]);
      return;
    }

    // Debounce search request
    const debounceTimeout = setTimeout(() => {
      search(query);
    }, debounceTime);

    // Clean up previous debounce timeout if query changes
    return () => clearTimeout(debounceTimeout);
  }, [query, debounceTime]);

  const search = async (query: string) => {
    try {
      setLoading(true);

      const response = await axios.post(URL, generateQuery(query));

      const results = response.data.hits.hits.map((raw: RawSearchResult) => {
        // assume each field only has one value inside the array see RawSearchFieldMapping
        const fields = Object.entries(raw.fields).reduce((acc, [key, value]) => {
          acc[key as keyof RawSearchFieldMapping] = value[0];
          return acc;
        }, {} as SearchFieldMapping);

        return {
          ...raw,
          fields,
        };
      });

      setResults(results);

    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return {
    results,
    loading,
  };
}