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
            match: {
              content: query
            }
          }
        ]
      }
    }
  };
}

export interface SearchMapping {
  name: string,
  content: string,
  path: string,
  size: number,
  created_at: number,
  updated_at: number
}

export interface SearchResult {
  _index: string,
  _id: string,
  _score: number,
  _source: SearchMapping
}

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

      setResults(response.data.hits.hits as SearchResult[]);
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