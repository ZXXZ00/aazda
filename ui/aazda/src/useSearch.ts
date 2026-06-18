import { useState, useEffect } from 'react';
import axios from 'axios';

export const SEARCH_ENDPOINT = 'http://localhost:8000';
const URL = `${SEARCH_ENDPOINT}/search`;

export interface SearchResult {
  id: string;
  score: number;
  path: string;
  name: string;
  file_type: string;
  size: number;
  created_at: string;
  updated_at: string;
  open_count: number;
  last_opened_at: string | null;
  metadata?: Record<string, any>;
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

      const response = await axios.post(URL, { query });
      setResults(response.data.results || []);

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