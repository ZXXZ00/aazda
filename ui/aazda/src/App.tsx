import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import { SearchResult, useSearch } from './useSearch';
import { SearchResultRow } from './SearchResultRow';
import { Preview } from './Preview';
import { SearchIcon } from './SearchIcon';

function App() {
  const [query, setQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [showPreview, setShowPreview] = useState(false);
  const {results} = useSearch(query);

  const selected = useMemo(() => {
    return focusedIndex > -1 && results.length > 0 ? results[focusedIndex] : null;
  }, [results, focusedIndex]);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isInputFocused, setIsInputFocused] = useState(false);

  const checkFocus = () => {
    setIsInputFocused(document.activeElement === inputRef.current);
  };

  const onClick = useCallback((result: SearchResult) => {
    window.ipcRenderer.openFile(result._source.path);
    setFocusedIndex(results.findIndex(r => r._id === result._id));
  }, [results]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown': {
        setFocusedIndex(results.length === 0 ? -1 : (focusedIndex + 1) % results.length);
        break;
      }
      case 'ArrowUp': {
        setFocusedIndex(results.length === 0 ? -1 : Math.max(focusedIndex - 1, -1));
        break;
      }
      case 'ArrowRight': {
        setShowPreview(!isInputFocused && true);
        break;
      }
      case 'ArrowLeft': {
        setShowPreview(!isInputFocused && false);
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
  }, [focusedIndex, isInputFocused, onClick, results]);

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
        <SearchIcon />
        <input
          ref={inputRef}
          type='text'
          onChange={(event) => {
            setQuery(event.target.value);
            setShowPreview(false);
          }}
          onBlur={checkFocus}
          onFocus={checkFocus}
        />
      </div>
      <div id="result">
        <div id="result-list">
          <ul>
            {results.map((result) => 
              <SearchResultRow
                key={result._id}
                result={result}
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
