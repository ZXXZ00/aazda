import { useEffect, useState, useRef } from 'react';

export function Settings() {
  const [activeTab, setActiveTab] = useState<'indexing' | 'appearance' | 'logs'>('appearance');
  const [savedConfig, setSavedConfig] = useState({ watchDir: '', watchInterval: 10, opacity: 0.72 });
  const [formWatchDir, setFormWatchDir] = useState('');
  const [formWatchInterval, setFormWatchInterval] = useState(10);
  const [opacity, setOpacity] = useState(0.72);
  const [showSavedAlert, setShowSavedAlert] = useState(false);

  const [activeLogType, setActiveLogType] = useState<'python' | 'electron'>('python');
  const [logsText, setLogsText] = useState('Loading logs...');
  const logBodyRef = useRef<HTMLPreElement | null>(null);
  const isFirstLoad = useRef(true);

  // 1. Load initial settings
  useEffect(() => {
    window.ipcRenderer.getSettings().then((config) => {
      const normalized = {
        watchDir: config.watchDir,
        watchInterval: config.watchInterval,
        opacity: config.opacity ?? 0.72
      };
      setSavedConfig(normalized);
      setFormWatchDir(normalized.watchDir);
      setFormWatchInterval(normalized.watchInterval);
      setOpacity(normalized.opacity);
    });
  }, []);

  // 2. Debounce saving transparency setting when it changes (no python restarts)
  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false;
      return;
    }

    const timer = setTimeout(() => {
      window.ipcRenderer.saveSettings({
        watchDir: savedConfig.watchDir,
        watchInterval: savedConfig.watchInterval,
        opacity
      }).then(() => {
        setSavedConfig(prev => ({ ...prev, opacity }));
      });
    }, 100);

    return () => clearTimeout(timer);
  }, [opacity]);

  // 3. Poll logs when activeTab is 'logs'
  useEffect(() => {
    if (activeTab !== 'logs') return;

    const fetchLogs = () => {
      window.ipcRenderer.getLogs(activeLogType).then((text) => {
        setLogsText(text);
        if (logBodyRef.current) {
          logBodyRef.current.scrollTop = logBodyRef.current.scrollHeight;
        }
      });
    };

    fetchLogs(); // Initial load
    const interval = setInterval(fetchLogs, 2000);

    return () => clearInterval(interval);
  }, [activeTab, activeLogType]);

  const handleBrowse = async () => {
    const dir = await window.ipcRenderer.selectDirectory();
    if (dir) {
      setFormWatchDir(dir);
    }
  };

  const handleSaveBackend = async () => {
    const updated = {
      watchDir: formWatchDir,
      watchInterval: Number(formWatchInterval),
      opacity
    };
    const success = await window.ipcRenderer.saveSettings(updated);
    if (success) {
      await window.ipcRenderer.restartPython();
      setSavedConfig(updated);
      setShowSavedAlert(true);
      setTimeout(() => setShowSavedAlert(false), 3000);
    }
  };

  const handleOpenLogFile = () => {
    window.ipcRenderer.openLogFile(activeLogType);
  };

  const handleOpenLogsDir = () => {
    window.ipcRenderer.openLogsDir();
  };

  const hasBackendChanges = 
    formWatchDir !== savedConfig.watchDir || 
    Number(formWatchInterval) !== savedConfig.watchInterval;

  return (
    <div className="settings-container">
      <div className="settings-header">
        <h2>Local Search Settings</h2>
        <p>Configure directory monitoring options and inspect logs.</p>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="settings-tabs">
        <button
          className={`settings-tab-btn ${activeTab === 'appearance' ? 'active' : ''}`}
          onClick={() => setActiveTab('appearance')}
        >
          Appearance
        </button>
        <button
          className={`settings-tab-btn ${activeTab === 'indexing' ? 'active' : ''}`}
          onClick={() => setActiveTab('indexing')}
        >
          Index Settings
        </button>
        <button
          className={`settings-tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          System Logs
        </button>
      </div>

      <div className="settings-panel">
        {activeTab === 'indexing' && (
          <>
            <div className="form-group">
              <label>Watch Directory</label>
              <div className="directory-picker">
                <input
                  type="text"
                  className="form-input"
                  value={formWatchDir}
                  readOnly
                  placeholder="Select a directory to index and watch"
                />
                <button className="btn" onClick={handleBrowse}>
                  Browse...
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>Scan Interval (Seconds)</label>
              <input
                type="number"
                className="form-input"
                value={formWatchInterval}
                onChange={(e) => setFormWatchInterval(Math.max(1, Number(e.target.value)))}
                min={1}
              />
            </div>

            {showSavedAlert && (
              <div className="settings-alert settings-alert-success">
                ✓ Settings saved and background server restarted successfully!
              </div>
            )}

            <div className="settings-actions">
              <button 
                className={`btn btn-primary ${!hasBackendChanges ? 'btn-secondary' : ''}`} 
                onClick={handleSaveBackend}
                disabled={!hasBackendChanges}
              >
                Save & Restart Server
              </button>
            </div>
          </>
        )}

        {activeTab === 'appearance' && (
          <>
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Window Transparency ({Math.round(opacity * 100)}%)</label>
              <input
                type="range"
                className="form-input"
                min="0.10"
                max="1.00"
                step="0.05"
                value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))}
                style={{ padding: '0', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Window transparency changes are saved and applied automatically in real-time.
              </span>
            </div>
          </>
        )}

        {activeTab === 'logs' && (
          <>
            <div className="log-console-container">
              <div className="log-console-header">
                <span className="log-console-title">Log output</span>
                <div className="log-console-tabs">
                  <button
                    className={`log-console-tab ${activeLogType === 'python' ? 'active' : ''}`}
                    onClick={() => setActiveLogType('python')}
                  >
                    Python API
                  </button>
                  <button
                    className={`log-console-tab ${activeLogType === 'electron' ? 'active' : ''}`}
                    onClick={() => setActiveLogType('electron')}
                  >
                    Electron App
                  </button>
                </div>
              </div>
              <pre ref={logBodyRef} className="log-console-body">
                {logsText}
              </pre>
            </div>

            <div className="log-actions">
              <button className="btn btn-secondary" onClick={handleOpenLogFile}>
                Open Current Log File
              </button>
              <button className="btn btn-secondary" onClick={handleOpenLogsDir}>
                Browse Logs Folder
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
