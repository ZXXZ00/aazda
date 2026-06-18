
import mime from 'mime';

interface FileIconProps {
  fileType: string;
  path?: string;
  className?: string;
  selected?: boolean;
}

export function FileIcon({ fileType, path, selected, className = '' }: FileIconProps) {
  // If selected, we might want to override color to white for maximum contrast on the Indigo background
  const iconColor = (defaultColor: string) => (selected ? '#ffffff' : defaultColor);

  let normalized = fileType.toLowerCase();

  if (path) {
    const isGenericOrIncorrect =
      normalized === 'unknown' ||
      normalized === 'application/octet-stream' ||
      normalized.startsWith('application/x-') ||
      (!normalized.includes('/') || 
       normalized.startsWith('application/jpg') || 
       normalized.startsWith('application/jpeg') || 
       normalized.startsWith('application/png') ||
       normalized.startsWith('application/gif') ||
       normalized.startsWith('application/webp') ||
       normalized.startsWith('application/mp3') ||
       normalized.startsWith('application/mp4') ||
       normalized.startsWith('application/wav'));

    if (isGenericOrIncorrect) {
      const guessed = mime.getType(path);
      if (guessed) {
        normalized = guessed.toLowerCase();
      }
    }
  }

  // 1. Directory/Folder
  if (normalized === 'inode/directory') {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#eab308')} // Yellow-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      </svg>
    );
  }

  // 2. PDF
  if (normalized === 'application/pdf') {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#ef4444')} // Red-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M9 15h1.5a1.5 1.5 0 0 0 0-3H9v4" />
        <path d="M14 12v4" />
      </svg>
    );
  }

  // 3. Word Document (.docx, etc.)
  if (
    normalized.includes('wordprocessingml') ||
    normalized.includes('msword') ||
    (normalized.includes('office-document') && normalized.includes('word'))
  ) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#3b82f6')} // Blue-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="14" y2="17" />
      </svg>
    );
  }

  // 4. Excel/Spreadsheet (.xlsx, etc.)
  if (
    normalized.includes('spreadsheetml') ||
    normalized.includes('ms-excel') ||
    (normalized.includes('office-document') && normalized.includes('spreadsheet'))
  ) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#10b981')} // Green-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M8 13h8" />
        <path d="M8 17h8" />
        <path d="M12 11v8" />
      </svg>
    );
  }

  // 5. PowerPoint/Slide (.pptx, etc.)
  if (
    normalized.includes('presentationml') ||
    normalized.includes('ms-powerpoint') ||
    (normalized.includes('office-document') && normalized.includes('presentation'))
  ) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#a855f7')} // Purple-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <rect x="8" y="12" width="8" height="6" rx="1" />
      </svg>
    );
  }

  // 6. Plain Text & Source Code (contains "text/" or is JSON)
  if (normalized.startsWith('text/') || normalized.includes('json') || normalized.includes('javascript') || normalized.includes('typescript')) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#818cf8')} // Indigo-400
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M8 13h8" />
        <path d="M8 17h8" />
        <path d="M10 9h2" />
      </svg>
    );
  }

  // 6b. Image
  if (normalized.startsWith('image/')) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#f97316')} // Orange-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <circle cx="9" cy="9" r="2" />
        <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
      </svg>
    );
  }

  // 6c. Video
  if (normalized.startsWith('video/')) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#ec4899')} // Pink-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="m22 8-6 4 6 4V8Z" />
        <rect x="2" y="5" width="14" height="14" rx="2" ry="2" />
      </svg>
    );
  }

  // 6d. Audio
  if (normalized.startsWith('audio/')) {
    return (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke={iconColor('#14b8a6')} // Teal-500
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
      >
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    );
  }

  // 7. Fallback Generic File
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke={iconColor('#9ca3af')} // Gray-400
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}
