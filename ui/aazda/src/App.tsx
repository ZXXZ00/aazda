import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import { SearchResult, useSearch, SEARCH_ENDPOINT } from './useSearch';
import axios from 'axios';
import { SearchResultRow } from './SearchResultRow';
import { Preview } from './Preview';
import { SearchIcon } from './SearchIcon';

function App() {
  const [query, setQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [showPreview, setShowPreview] = useState(false);
  const [opacity, setOpacity] = useState(0.72);
  const { results, loading } = useSearch(query);

  const selected = useMemo(() => {
    return focusedIndex > -1 && results.length > 0 ? results[focusedIndex] : null;
  }, [results, focusedIndex]);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const isMouseActive = useRef(false);
  const lastMousePos = useRef({ x: -1, y: -1 });
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastLeftPreviewTime = useRef(0);

  const onClick = useCallback((result: SearchResult) => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    window.ipcRenderer.openFile(result.path);
    axios.post(`${SEARCH_ENDPOINT}/click`, { path: result.path })
      .catch(err => console.error("Failed to log click:", err));
    setFocusedIndex(results.findIndex(r => r.id === result.id));
  }, [results]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault(); // Prevent cursor jumping in input bar
        setFocusedIndex(results.length === 0 ? -1 : (focusedIndex + 1) % results.length);
        break;
      }
      case 'ArrowUp': {
        e.preventDefault(); // Prevent cursor jumping in input bar
        setFocusedIndex(results.length === 0 ? -1 : Math.max(focusedIndex - 1, -1));
        break;
      }
      case 'ArrowRight': {
        if (focusedIndex > -1) {
          e.preventDefault(); // Prevent cursor movement when expanding preview
          setShowPreview(true);
        }
        break;
      }
      case 'ArrowLeft': {
        if (focusedIndex > -1) {
          e.preventDefault(); // Prevent cursor movement when closing preview
          setShowPreview(false);
        }
        break;
      }
      case 'Enter': {
        if (focusedIndex > -1 && results.length > 0) {
          e.preventDefault();
          onClick(results[focusedIndex]);
        }
        break;
      }
      default:
        break;
    }
  }, [focusedIndex, onClick, results]);

  // Handle configuration loading and live updates
  useEffect(() => {
    // 1. Fetch initial configuration
    window.ipcRenderer.getSettings().then((config) => {
      if (config.opacity !== undefined) {
        setOpacity(config.opacity);
      }
    });

    // 2. Subscribe to settings-updated events
    const unsubscribe = window.ipcRenderer.onSettingsUpdated((_event, config) => {
      if (config.opacity !== undefined) {
        setOpacity(config.opacity);
      }
    });

    return unsubscribe;
  }, []);

  // Focus input on initial mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Track mouse movement vs keyboard navigation to prevent stationary hover selection
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (lastMousePos.current.x !== e.clientX || lastMousePos.current.y !== e.clientY) {
        isMouseActive.current = true;
        lastMousePos.current = { x: e.clientX, y: e.clientY };
      }
    };
    const handleKeyDownCapture = () => {
      isMouseActive.current = false;
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('keydown', handleKeyDownCapture, true);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('keydown', handleKeyDownCapture, true);
    };
  }, []);

  useEffect(() => {
    const handleKeyDownEvent = (e: KeyboardEvent) => {
      handleKeyDown(e);
    };

    window.addEventListener('keydown', handleKeyDownEvent);

    return () => {
      window.removeEventListener('keydown', handleKeyDownEvent);
    };
  }, [handleKeyDown]);

  // Global typing listener to automatically focus input when user starts typing
  useEffect(() => {
    const handleGlobalTyping = (e: KeyboardEvent) => {
      // Ignore modifier combinations
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // If already focused on input, do nothing
      if (document.activeElement === inputRef.current) return;

      // Check if it's a character or edit key (Backspace/Delete)
      const isCharacter = e.key.length === 1;
      const isEditKey = e.key === 'Backspace' || e.key === 'Delete';

      if (isCharacter || isEditKey) {
        inputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleGlobalTyping);
    return () => {
      window.removeEventListener('keydown', handleGlobalTyping);
    };
  }, []);

  // Reset selection when search results update
  useEffect(() => {
    setFocusedIndex(-1);
  }, [results]);

  return (
    <div 
      className="app-card" 
      style={{ '--bg-opacity': opacity } as React.CSSProperties}
    >
      <div id="input-box">
        <SearchIcon />
        <input
          ref={inputRef}
          type='text'
          placeholder="Search files, code, docs..."
          onChange={(event) => {
            if (hoverTimeoutRef.current) {
              clearTimeout(hoverTimeoutRef.current);
            }
            setQuery(event.target.value);
            setFocusedIndex(-1); // Reset list selection on typing
            setShowPreview(false);
          }}
        />
        {loading && <div className="loading-spinner"></div>}
      </div>
      
      <div id="result">
        {!query.trim() ? (
          <div className="empty-state-guide">
            <div className="guide-title">Search Shortcuts</div>
            <div className="guide-grid">
              <div className="guide-item">
                <span className="guide-key">↑ ↓</span>
                <span className="guide-desc">Navigate results list</span>
              </div>
              <div className="guide-item">
                <span className="guide-key">→</span>
                <span className="guide-desc">Open document preview pane</span>
              </div>
              <div className="guide-item">
                <span className="guide-key">←</span>
                <span className="guide-desc">Close document preview pane</span>
              </div>
              <div className="guide-item">
                <span className="guide-key">↵</span>
                <span className="guide-desc">Open file in native desktop app</span>
              </div>
              <div className="guide-item">
                <span className="guide-key">⌘ Shift /</span>
                <span className="guide-desc">Show or hide search bar globally</span>
              </div>
            </div>
            <div className="guide-tip">
              Right-click the system tray icon at the top to access <strong>Settings</strong>.
            </div>
          </div>
        ) : (
          <>
            <div 
              id="result-list"
              onMouseLeave={() => {
                if (hoverTimeoutRef.current) {
                  clearTimeout(hoverTimeoutRef.current);
                }
              }}
            >
              <ul>
                {results.map((result, index) => 
                  <SearchResultRow
                    key={result.id}
                    result={result}
                    onClick={() => onClick(result)}
                    onMouseEnter={() => {
                      if (isMouseActive.current) {
                        // Ignore hover selection if we recently left the preview pane (to prevent accidental slips)
                        if (Date.now() - lastLeftPreviewTime.current < 300) {
                          return;
                        }
                        if (hoverTimeoutRef.current) {
                          clearTimeout(hoverTimeoutRef.current);
                        }
                        hoverTimeoutRef.current = setTimeout(() => {
                          setFocusedIndex(index);
                        }, 120); // 120ms delay to ignore quick glides towards the preview pane
                      }
                    }}
                    selected={selected?.id === result.id}
                    query={query}
                  />
                )}
              </ul>
            </div>
            
            { showPreview && selected && (
              <div 
                id="preview"
                onMouseLeave={() => {
                  lastLeftPreviewTime.current = Date.now();
                }}
              >
                <Preview result={selected} />
              </div>
            ) }
          </>
        )}
      </div>

      <div className="app-footer">
        <div className="footer-shortcuts">
          <div className="shortcut-group">
            <span className="shortcut-key">↑↓</span>
            <span>Navigate</span>
          </div>
          <div className="shortcut-group">
            <span className="shortcut-key">→</span>
            <span>Preview</span>
          </div>
          <div className="shortcut-group">
            <span className="shortcut-key">←</span>
            <span>Close Preview</span>
          </div>
          <div className="shortcut-group">
            <span className="shortcut-key">↵</span>
            <span>Open</span>
          </div>
        </div>
        <div>
          {results.length > 0 ? `${results.length} files found` : ''}
        </div>
      </div>
    </div>
  );
}

export default App;
