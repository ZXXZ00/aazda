import mime from'mime';
import DOMPurify from 'dompurify';
import axios from 'axios';
import { useEffect, useState } from 'react';

import { INDEX, SEARCH_ENDPOINT } from './useSearch';

const URL = `${SEARCH_ENDPOINT}/${INDEX}/_source/`;

interface PreviewProps {
  id: string
  type: string
  path: string
}

const typesRenderingFromFile = new Set(['application/pdf']);

// for future maybe depends on the file type using different renderer
export function Preview({ id, type, path }: PreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mimeType = type === 'UNKNOWN' ? mime.getType(path) : type;
  const filePath = `file://${path}`;

  useEffect(() => {
    const fetchData = async () => {
      try {
        const source = await axios.get(URL + id, { params: { _source_includes: 'content' } });
        setContent(source.data.content);
      } catch (err) {
        setError('Failed to load content');
      }
    };

    if (!mimeType || mimeType === 'application/octet-stream') {
      setError('Preview not supported for this file');
      return;
    }
    if (!typesRenderingFromFile.has(mimeType)) {
      fetchData();
    }
  }, [id, mimeType]);

  if (error) {
    return <p>{error}</p>;
  }

  if (mimeType && typesRenderingFromFile.has(mimeType)) {
    return <object className="preview-content" data={filePath} type={mimeType}></object>;
  }

  return (
    <div dangerouslySetInnerHTML={
      { __html: DOMPurify.sanitize(content || 'Could not preview for this file') }}>
    </div>
  );
}