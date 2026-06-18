/// <reference types="vite-plugin-electron/electron-env" />

declare namespace NodeJS {
  interface ProcessEnv {
    /**
     * The built directory structure
     *
     * ```tree
     * ├─┬─┬ dist
     * │ │ └── index.html
     * │ │
     * │ ├─┬ dist-electron
     * │ │ ├── main.js
     * │ │ └── preload.js
     * │
     * ```
     */
    APP_ROOT: string
    /** /dist/ or /public/ */
    VITE_PUBLIC: string
  }
}

// Used in Renderer process, expose in `preload.ts`
interface Window {
  ipcRenderer: {
    openFile(filePath: string): Promise<void>
    getSettings(): Promise<{ watchDir: string; watchInterval: number; opacity?: number }>
    saveSettings(config: { watchDir: string; watchInterval: number; opacity?: number }): Promise<boolean>
    selectDirectory(): Promise<string | null>
    getLogs(type: 'python' | 'electron'): Promise<string>
    openLogFile(type: 'python' | 'electron'): Promise<boolean>
    openLogsDir(): Promise<boolean>
    restartPython(): Promise<boolean>
    onSettingsUpdated(callback: (event: any, config: { watchDir: string; watchInterval: number; opacity?: number }) => void): () => void;
  }
}
