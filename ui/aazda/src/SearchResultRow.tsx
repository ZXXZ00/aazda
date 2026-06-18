import { useEffect, useRef } from 'react';
import { SearchResult } from './useSearch';
import { FileIcon } from './FileIcon';

interface SearchResultRowProps {
  result: SearchResult;
  onClick: () => void;
  onMouseEnter: () => void;
  selected?: boolean;
  query: string;
}

export function SearchResultRow({ result, selected, onClick, onMouseEnter, query }: SearchResultRowProps) {
  const rowRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    if (selected && rowRef.current) {
      rowRef.current.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    }
  }, [selected]);

  const highlightText = (text: string, search: string) => {
    if (!search.trim()) return <span>{text}</span>;
    
    const escapedQuery = search.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    const parts = text.split(regex);
    
    return (
      <span>
        {parts.map((part, i) => 
          regex.test(part) ? <em key={i}>{part}</em> : <span key={i}>{part}</span>
        )}
      </span>
    );
  };

  return (
    <li 
      ref={rowRef}
      className={`result-row ${selected ? 'selected' : ''}`} 
      onClick={onClick}
      onMouseEnter={onMouseEnter}
    >
      <FileIcon fileType={result.file_type} path={result.path} selected={selected} />
      <div className="result-row-details">
        <div className="result-row-name">{highlightText(result.name, query)}</div>
        <div className="result-row-path">{result.path}</div>
      </div>
    </li>
  );
}