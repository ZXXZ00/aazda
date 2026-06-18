import { ipcRenderer, contextBridge } from 'electron';

contextBridge.exposeInMainWorld('ipcRenderer', {
  openFile: (filePath: string) => ipcRenderer.invoke('open-file', filePath),
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (config: any) => ipcRenderer.invoke('save-settings', config),
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  getLogs: (type: 'python' | 'electron') => ipcRenderer.invoke('get-logs', type),
  openLogFile: (type: 'python' | 'electron') => ipcRenderer.invoke('open-log-file', type),
  openLogsDir: () => ipcRenderer.invoke('open-logs-dir'),
  restartPython: () => ipcRenderer.invoke('restart-python'),
  onSettingsUpdated: (callback: any) => {
    const subscription = (_event: any, config: any) => callback(_event, config);
    ipcRenderer.on('settings-updated', subscription);
    return () => {
      ipcRenderer.removeListener('settings-updated', subscription);
    };
  }
});
