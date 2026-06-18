import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import { Settings } from './Settings.tsx';
import './index.css';

const isSettings = window.location.hash === '#settings';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isSettings ? <Settings /> : <App />}
  </React.StrictMode>,
);