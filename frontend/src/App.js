import React, { useState } from 'react';
import { NetworkProvider } from './contexts/NetworkContext';
import SummaryStrip from './components/SummaryStrip';
import DeviceList from './components/DeviceList';
import CliPanel from './components/CliPanel';
import AlertsPanel from './components/AlertsPanel';
import TopologyMap from './components/TopologyMap';
import AiAssist from './components/AiAssist';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'topology', label: 'Topology' },
  { id: 'devices', label: 'Devices' },
  { id: 'cli', label: 'CLI' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'ai', label: 'AI Assist' },
];

function App() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <NetworkProvider>
      <div style={{ backgroundColor: '#111827', minHeight: '100vh', color: 'white', fontFamily: 'system-ui, sans-serif' }}>

        <header style={{ padding: '1.5rem 2rem 0 2rem' }}>
          <h1 style={{ color: '#4ade80', fontSize: '2rem', margin: 0 }}>AI-NOC Dashboard</h1>
          <p style={{ color: '#9ca3af', margin: '0.5rem 0 0 0' }}>Network Operations Center • Live Telemetry</p>
        </header>

        <nav style={{
          display: 'flex', gap: '0.25rem', padding: '1rem 2rem 0 2rem',
          borderBottom: '1px solid #374151', overflowX: 'auto'
        }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '0.6rem 1.2rem',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid #4ade80' : '2px solid transparent',
                backgroundColor: 'transparent',
                color: activeTab === tab.id ? '#4ade80' : '#9ca3af',
                fontWeight: activeTab === tab.id ? 'bold' : 'normal',
                fontSize: '0.9rem',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'color 0.2s'
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div style={{ padding: '1.5rem 2rem' }}>
          {activeTab === 'overview' && (
            <>
              <SummaryStrip />
              <DeviceList />
            </>
          )}
          {activeTab === 'topology' && <TopologyMap />}
          {activeTab === 'devices' && <DeviceList />}
          {activeTab === 'cli' && <CliPanel />}
          {activeTab === 'alerts' && <AlertsPanel />}
          {activeTab === 'ai' && <AiAssist />}
        </div>

      </div>
    </NetworkProvider>
  );
}

export default App;