import { ipcRenderer, contextBridge } from 'electron';

contextBridge.exposeInMainWorld('ipcRenderer', {
  openFile: (filePath: string) => ipcRenderer.invoke('open-file', filePath)
});
