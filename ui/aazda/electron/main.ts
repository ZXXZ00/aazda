import { app, BrowserWindow, globalShortcut, ipcMain, shell, WebContentsView, Tray, Menu, nativeImage, dialog } from 'electron';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { spawn, ChildProcess } from 'node:child_process';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

process.env.APP_ROOT = path.join(__dirname, '..');

export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL'];
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron');
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist');

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST;

let win: BrowserWindow | null;
let settingsWin: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
let tray: Tray | null = null;

// --- Config and Logging Daemon Setup ---

const configPath = path.join(app.getPath('userData'), 'config.json');
const logsDir = path.join(app.getPath('userData'), 'logs');

// Ensure log directory exists
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

// Generate unique timestamp for current session
const sessionTimestamp = new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19);
const electronLogPath = path.join(logsDir, `electron_${sessionTimestamp}.log`);
const pythonLogPath = path.join(logsDir, `python_${sessionTimestamp}.log`);

function logElectron(msg: string) {
  const time = new Date().toISOString();
  const line = `[${time}] ${msg}\n`;
  try {
    fs.appendFileSync(electronLogPath, line, 'utf-8');
  } catch (err) {
    console.error('Failed to write to Electron log:', err);
  }
}

function logPython(msg: string) {
  const time = new Date().toISOString();
  const line = `[${time}] ${msg}\n`;
  try {
    fs.appendFileSync(pythonLogPath, line, 'utf-8');
  } catch (err) {
    console.error('Failed to write to Python log:', err);
  }
}

function loadConfig() {
  const defaults = {
    watchDir: process.env.HOME || '',
    watchInterval: 10,
    opacity: 0.72
  };
  try {
    if (fs.existsSync(configPath)) {
      const data = fs.readFileSync(configPath, 'utf-8');
      return { ...defaults, ...JSON.parse(data) };
    }
  } catch (e) {
    logElectron(`Failed to load config: ${e}`);
  }
  return defaults;
}

function saveConfig(config: any) {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
    logElectron(`Saved config to disk: ${JSON.stringify(config)}`);
  } catch (e) {
    logElectron(`Failed to save config: ${e}`);
  }
}

function toggleWindow() {
  if (win?.isVisible()) {
    win.hide();
  } else {
    win?.show();
    win?.focus();
  }
}

function createSettingsWindow() {
  if (settingsWin) {
    settingsWin.focus();
    return;
  }

  logElectron('Opening settings window...');
  settingsWin = new BrowserWindow({
    width: 500,
    height: 480,
    title: 'Settings',
    resizable: false,
    frame: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
      webSecurity: false
    }
  });

  if (VITE_DEV_SERVER_URL) {
    settingsWin.loadURL(`${VITE_DEV_SERVER_URL}#settings`);
  } else {
    settingsWin.loadFile(path.join(RENDERER_DIST, 'index.html'), { hash: 'settings' });
  }

  settingsWin.on('closed', () => {
    settingsWin = null;
    logElectron('Settings window closed');
  });
}

function createTray() {
  const iconPath = path.join(process.env.VITE_PUBLIC || '', 'trayIconTemplate.png');
  const image = nativeImage.createFromPath(iconPath);
  image.setTemplateImage(true);
  
  tray = new Tray(image);
  tray.setToolTip('Local Semantic Search');
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Toggle Search',
      accelerator: 'Cmd+Shift+/',
      click: () => {
        toggleWindow();
      }
    },
    {
      label: 'Settings...',
      click: () => {
        createSettingsWindow();
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      accelerator: 'Cmd+Q',
      click: () => {
        app.quit();
      }
    }
  ]);
  
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    toggleWindow();
  });
}

function getPythonProcessConfig(config: any) {
  const isPackaged = app.isPackaged;
  
  if (isPackaged) {
    const binaryName = process.platform === 'win32' ? 'api.exe' : 'api';
    const binaryPath = path.join(process.resourcesPath, 'bin', binaryName);
    return {
      command: binaryPath,
      args: [],
      options: {
        cwd: path.dirname(binaryPath)
      }
    };
  } else {
    const projectRoot = path.join(process.env.APP_ROOT || __dirname, '../..');
    const apiScript = path.join(projectRoot, 'api.py');
    
    let pythonExec = process.env.PYTHON_PATH || '';
    
    if (!pythonExec) {
      const localVenv = path.join(projectRoot, '.venv', 'bin', 'python');
      const localVenvWin = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');
      const minicondaPath = '/opt/homebrew/Caskroom/miniconda/base/envs/search/bin/python';
      
      if (fs.existsSync(localVenv)) {
        pythonExec = localVenv;
      } else if (fs.existsSync(localVenvWin)) {
        pythonExec = localVenvWin;
      } else if (fs.existsSync(minicondaPath)) {
        pythonExec = minicondaPath;
      } else {
        pythonExec = process.platform === 'win32' ? 'python' : 'python3';
      }
    }
    
    return {
      command: pythonExec,
      args: [apiScript],
      options: {
        cwd: projectRoot,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          WATCH_DIR: config.watchDir,
          WATCH_INTERVAL: String(config.watchInterval)
        }
      }
    };
  }
}

function startPythonServer(config: any) {
  const processConfig = getPythonProcessConfig(config);
  logElectron(`Starting Python API server: ${processConfig.command} ${processConfig.args.join(' ')}`);
  
  try {
    pythonProcess = spawn(processConfig.command, processConfig.args, processConfig.options);
    
    pythonProcess.stdout?.on('data', (data) => {
      const msg = data.toString().trim();
      logPython(`[Out] ${msg}`);
    });
    
    pythonProcess.stderr?.on('data', (data) => {
      const msg = data.toString().trim();
      logPython(`[Err] ${msg}`);
    });
    
    pythonProcess.on('error', (err) => {
      logElectron(`Failed to start Python API process: ${err.message}`);
    });
    
    pythonProcess.on('close', (code) => {
      logElectron(`Python API process exited with code ${code}`);
    });
  } catch (error: any) {
    logElectron(`Failed to spawn Python process: ${error.message}`);
  }
}

function restartPythonServer(config: any) {
  if (pythonProcess) {
    logElectron('Stopping Python API server for restart...');
    pythonProcess.kill('SIGTERM');
  }
  startPythonServer(config);
}

// --- IPC Channels Hookups ---

ipcMain.handle('open-file', async (_, filePath: string) => {
  try {
    await shell.openPath(filePath);
    win?.hide();
  } catch (error) {
    logElectron(`Error opening file: ${error}`);
  }
});

ipcMain.handle('get-settings', () => {
  return loadConfig();
});

ipcMain.handle('save-settings', (_, newConfig: any) => {
  saveConfig(newConfig);
  if (win && !win.isDestroyed()) {
    win.webContents.send('settings-updated', newConfig);
  }
  if (settingsWin && !settingsWin.isDestroyed()) {
    settingsWin.webContents.send('settings-updated', newConfig);
  }
  return true;
});

ipcMain.handle('restart-python', () => {
  const config = loadConfig();
  restartPythonServer(config);
  return true;
});

ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  });
  if (result.canceled) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('get-logs', async (_, type: 'python' | 'electron') => {
  const logPath = type === 'python' ? pythonLogPath : electronLogPath;
  try {
    if (fs.existsSync(logPath)) {
      const content = fs.readFileSync(logPath, 'utf-8');
      const lines = content.split('\n');
      return lines.slice(-200).join('\n');
    }
  } catch (err) {
    return `Error reading log file: ${err}`;
  }
  return 'No logs recorded yet.';
});

ipcMain.handle('open-log-file', async (_, type: 'python' | 'electron') => {
  const logPath = type === 'python' ? pythonLogPath : electronLogPath;
  try {
    if (fs.existsSync(logPath)) {
      await shell.openPath(logPath);
      return true;
    }
  } catch (err) {
    logElectron(`Error opening log file: ${err}`);
  }
  return false;
});

ipcMain.handle('open-logs-dir', async () => {
  try {
    await shell.openPath(logsDir);
    return true;
  } catch (err) {
    logElectron(`Error opening logs directory: ${err}`);
  }
  return false;
});

function registerGlobalShortcut() {
  globalShortcut.register('Cmd+Shift+/', () => {
    toggleWindow();
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 800,
    height: 520,
    resizable: false,
    frame: false,
    transparent: true,
    icon: path.join(process.env.VITE_PUBLIC, 'electron-vite.svg'),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
      webSecurity: false
    },
  });

  win.on('blur', () => {
    win?.hide();
  });

  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', (new Date).toLocaleString());
  });

  const view = new WebContentsView();
  view.setBackgroundColor('none');

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html'));
  }
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
    win = null;
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.whenReady().then(() => {
  if (process.platform === 'darwin') {
    app.dock.hide();
  }
  
  const config = loadConfig();
  logElectron(`Application startup. Session timestamp: ${sessionTimestamp}`);
  logElectron(`Log directory located at: ${logsDir}`);
  
  startPythonServer(config);
  createWindow();
  createTray();
  registerGlobalShortcut();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (pythonProcess) {
    logElectron('Stopping Python API server...');
    pythonProcess.kill('SIGTERM');
  }
});
