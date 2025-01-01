import mime from'mime';

interface PreviewProps {
  path: string
}

export function Preview({path}: PreviewProps) {
  const filePath = `file://${path}`;
  const mimeType = mime.getType(path);
  return (
    mimeType ?
      <object className="preview-content" data={filePath} type={mimeType}></object> :
      <p>preview not supported for this file</p>
  );
}