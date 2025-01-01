import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import { SearchResult, useSearch } from './useSearch';
import { SearchResultRow } from './SearchResultRow';
import { Preview } from './Preview';

function App() {
  const [query, setQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [showPreview, setShowPreview] = useState(false);
  const {results} = useSearch(query);

  const selected = useMemo(() => {
    return focusedIndex > -1 && results.length > 0 ? results[focusedIndex] : null;
  }, [results, focusedIndex]);

  const inputRef = useRef<HTMLInputElement | null>(null);

  const onClick = (result: SearchResult) => {
    window.ipcRenderer.openFile(result._source.path);
    setFocusedIndex(results.findIndex(r => r._id === result._id));
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown': {
        setFocusedIndex(results.length === 0 ? -1 : (focusedIndex + 1) % results.length);
        break;
      }
      case 'ArrowUp': {
        setFocusedIndex(results.length === 0 ? -1 : (focusedIndex - 1) % results.length);
        break;
      }
      case 'ArrowRight': {
        setShowPreview(true);
        break;
      }
      case 'ArrowLeft': {
        setShowPreview(false);
        break;
      }
      case 'Enter': {
        if (focusedIndex > -1 && results.length > 0) {
          onClick(results[focusedIndex]);
        }
        break;
      }
      default:
        break;
    }
  }, [focusedIndex, results]);

  useEffect(() => {
    const handleKeyDownEvent = (e: KeyboardEvent) => {
      handleKeyDown(e);
    };

    window.addEventListener('keydown', handleKeyDownEvent);

    return () => {
      window.removeEventListener('keydown', handleKeyDownEvent);
    };
  }, [handleKeyDown]);

  useEffect(() => {
    if (focusedIndex > -1 && inputRef.current) {
      inputRef.current.blur();
    } else if (inputRef.current) {
      inputRef.current.focus();
      setTimeout(() => { // time out to finish focus before setting range
        inputRef.current?.setSelectionRange(0, inputRef.current.value.length);
      }, 0);
    }
  }, [focusedIndex]);

  return (
    <>
      <div id="input-box">
        <i className="fas fa-search"></i>
        <input
          ref={inputRef}
          type='text'
          onChange={(event) => {
            setQuery(event.target.value);
            setShowPreview(false);
          }}
        />
      </div>
      <div id="result">
        <div id="result-list">
          <ul>
            {results.map((result) => 
              <SearchResultRow
                key={result._id}
                result={result._source}
                id={result._id}
                onClick={() => onClick(result)}
                selected={selected?._id === result._id}
              />
            )}
          </ul>
        </div>
        { showPreview && selected && <div id="preview">
          <Preview path={selected._source.path} />
        </div> }
      </div>
    </>
  );
}

export default App;
