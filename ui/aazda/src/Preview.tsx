import mime from 'mime';
import axios from 'axios';
import { useEffect, useState } from 'react';
import { SearchResult, SEARCH_ENDPOINT } from './useSearch';
import { FileIcon } from './FileIcon';

const URL = `${SEARCH_ENDPOINT}/content`;

interface PreviewProps {
  result: SearchResult;
}

// Map file types to generic renderer types
type RendererType = 'DIRECTORY' | 'IMAGE' | 'VIDEO' | 'AUDIO' | 'PDF' | 'HTML' | 'TEXT' | 'PARSED_TEXT' | 'UNSUPPORTED';

const getRendererType = (mimeType: string, path: string): RendererType => {
  const normalized = mimeType.toLowerCase();
  
  if (normalized === 'inode/directory') {
    return 'DIRECTORY';
  }
  
  if (normalized.startsWith('image/')) {
    return 'IMAGE';
  }
  
  if (normalized.startsWith('video/')) {
    return 'VIDEO';
  }
  
  if (normalized.startsWith('audio/')) {
    return 'AUDIO';
  }
  
  if (normalized === 'application/pdf') {
    return 'PDF';
  }
  
  if (normalized === 'text/html') {
    return 'HTML';
  }
  
  // Text & Code files
  if (
    normalized.startsWith('text/') ||
    normalized.includes('json') ||
    normalized.includes('javascript') ||
    normalized.includes('typescript') ||
    normalized.includes('xml')
  ) {
    return 'TEXT';
  }
  
  // Known extensions that our backend parses into text (docx, xlsx, pptx)
  const ext = path.split('.').pop()?.toLowerCase();
  const parsedDocExts = new Set(['docx', 'xlsx', 'pptx']);
  if (ext && parsedDocExts.has(ext)) {
    return 'PARSED_TEXT';
  }
  
  // Common text-based configuration and script extensions that might be typed generic binary
  const textExts = new Set(['yaml', 'yml', 'ini', 'sh', 'bat', 'log', 'env', 'conf', 'cfg', 'properties']);
  if (ext && textExts.has(ext)) {
    return 'TEXT';
  }
  
  return 'UNSUPPORTED';
};

const encodeFilePath = (pathStr: string) => {
  const normalizedPath = pathStr.replace(/\\/g, '/');
  return normalizedPath
    .split('/')
    .map(segment => {
      // Don't encode Windows drive letter (e.g. C:)
      if (/^[a-zA-Z]:$/.test(segment)) {
        return segment;
      }
      return encodeURIComponent(segment);
    })
    .join('/');
};

export function Preview({ result }: PreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);

  const pathMime = mime.getType(result.path);
  const mimeType = pathMime || result.file_type || 'application/octet-stream';
  const rendererType = getRendererType(mimeType, result.path);
  const filePath = `file://${encodeFilePath(result.path)}`;

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        setContentLoading(true);
        setContentError(null);
        
        const response = await axios.get(URL, { params: { path: result.path } });
        
        if (active) {
          setContent(response.data.content);
        }
      } catch (err) {
        if (active) {
          setContentError('Failed to load file content');
        }
      } finally {
        if (active) {
          setContentLoading(false);
        }
      }
    };

    // Only make network requests to parse text content
    if (rendererType === 'TEXT' || rendererType === 'PARSED_TEXT') {
      fetchData();
    } else {
      setContent(null);
      setContentError(null);
    }

    return () => {
      active = false;
    };
  }, [result.path, rendererType]);

  const formatFileSize = (bytes: number) => {
    if (bytes === undefined || bytes === null || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return '--';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
      });
    } catch (e) {
      return isoString;
    }
  };

  const renderContentPane = () => {
    switch (rendererType) {
      case 'DIRECTORY':
        return <div className="preview-placeholder-text">Folder contents cannot be previewed.</div>;

      case 'IMAGE':
        return <img className="preview-image" src={filePath} alt={result.name} />;

      case 'VIDEO':
        return <video className="preview-video" src={filePath} controls />;

      case 'AUDIO':
        return <audio className="preview-audio" src={filePath} controls />;

      case 'PDF':
        return <object className="preview-object-viewer" data={filePath} type="application/pdf"></object>;

      case 'HTML':
        return <iframe className="preview-iframe-viewer" src={filePath}></iframe>;

      case 'TEXT':
      case 'PARSED_TEXT': {
        if (contentError) {
          return <div className="preview-placeholder-text">{contentError}</div>;
        }

        if (content !== null) {
          const displayContent =
            content.length > 50000
              ? content.slice(0, 50000) + '\n\n--- [UI showing first 50,000 characters for performance] ---'
              : content;

          return (
            <pre 
              className="preview-text-viewer" 
              style={{ 
                opacity: contentLoading ? 0.45 : 1, 
                transition: 'opacity 0.15s ease' 
              }}
            >
              {displayContent || 'No content available'}
            </pre>
          );
        }

        if (contentLoading) {
          return <div className="preview-placeholder-text">Loading file content...</div>;
        }

        return <div className="preview-placeholder-text">No preview content available.</div>;
      }

      case 'UNSUPPORTED':
      default:
        return <div className="preview-placeholder-text">Preview not supported for this file type.</div>;
    }
  };

  return (
    <div className="preview-container">
      <div className="preview-header">
        <div className="preview-title-bar">
          <FileIcon fileType={result.file_type} path={result.path} selected={false} />
          <div className="preview-filename">{result.name}</div>
        </div>
        
        <div className="preview-meta-grid">
          <div className="preview-meta-item">
            <span className="preview-meta-label">Size</span>
            <span className="preview-meta-value">{rendererType === 'DIRECTORY' ? '--' : formatFileSize(result.size)}</span>
          </div>
          <div className="preview-meta-item">
            <span className="preview-meta-label">Open Count</span>
            <span className="preview-meta-value">{result.open_count || 0}</span>
          </div>
          <div className="preview-meta-item">
            <span className="preview-meta-label">Created</span>
            <span className="preview-meta-value">{formatDate(result.created_at)}</span>
          </div>
          <div className="preview-meta-item">
            <span className="preview-meta-label">Modified</span>
            <span className="preview-meta-value">{formatDate(result.updated_at)}</span>
          </div>
        </div>
      </div>

      <div className="preview-content-pane">
        {renderContentPane()}
      </div>
    </div>
  );
}