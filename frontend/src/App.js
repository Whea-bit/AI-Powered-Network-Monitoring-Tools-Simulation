import React from 'react';
import { NetworkProvider } from './contexts/NetworkContext';
import SummaryStrip from './components/SummaryStrip';
import DeviceList from './components/DeviceList'; 
import CliPanel from './components/CliPanel';

function App() {
  return (
    <NetworkProvider>
      <div style={{ backgroundColor: '#111827', minHeight: '100vh', color: 'white', padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
        
        <header style={{ borderBottom: '1px solid #374151', paddingBottom: '1rem', marginBottom: '2rem' }}>
            <h1 style={{ color: '#4ade80', fontSize: '2rem', margin: 0 }}>AI-NOC Dashboard</h1>
            <p style={{ color: '#9ca3af', margin: '0.5rem 0 0 0' }}>Network Operations Center • Live Telemetry</p>
        </header>
        
        <SummaryStrip />
        <DeviceList />
        <CliPanel />
        
      </div>
    </NetworkProvider>
  );
}

export default App;