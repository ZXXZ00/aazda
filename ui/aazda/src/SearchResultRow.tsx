import { SearchMapping } from './useSearch';

interface SearchResultRowProps {
  result: SearchMapping
  id: string
  onClick: (id: string) => void;
  selected?: boolean;
}

export function SearchResultRow({result, id, selected, onClick}: SearchResultRowProps) {
  return (
    <li 
      className={`result-row ${selected ? 'selected' : ''}`}
      onClick={() => onClick(id)}>
      <div>
        {result.name}
      </div>
    </li>
  );
}