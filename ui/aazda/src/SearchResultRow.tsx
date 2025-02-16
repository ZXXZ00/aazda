import { SearchResult } from './useSearch';
import DOMPurify from 'dompurify';

interface SearchResultRowProps {
  result: SearchResult
  onClick: () => void;
  selected?: boolean;
}

export function SearchResultRow({result, selected, onClick}: SearchResultRowProps) {
  return (
    <li 
      className={`result-row ${selected ? 'selected' : ''}`}
      onClick={onClick}>
      <div>
        {result.fields.name}
      </div>
      { result.highlight?.content && result.highlight.content.length > 0 &&
        <div className="highlight"
          dangerouslySetInnerHTML={
            {__html:
              DOMPurify.sanitize(result.highlight.content[0], {ALLOWED_TAGS: ['em']})
                .replace(/(&gt;)|(&lt;)|(\/&gt;)/g, '')} // remove html tags
          }>
        </div> }
    </li>
  );
}