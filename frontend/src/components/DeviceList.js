import React from 'react';
import { useNetwork } from '../contexts/NetworkContext';

const DeviceList = () => {
    const { devices, loading, lastUpdated } = useNetwork();

    if (loading) {
        return <div style={{ color: '#9ca3af', marginTop: '2rem' }}>Loading network telemetry...</div>;
    }

    return (
        <div style={{ marginTop: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ fontSize: '1.5rem', color: '#f3f4f6', margin: 0 }}>Active Network Devices</h2>
                <span style={{ fontSize: '0.875rem', color: '#9ca3af' }}>
                    {lastUpdated ? `Last heartbeat: ${lastUpdated}` : 'Awaiting heartbeat...'}
                </span>
            </div>

            {devices.length === 0 ? (
                <div style={{ backgroundColor: '#1f2937', padding: '2rem', borderRadius: '0.5rem', textAlign: 'center', border: '1px dashed #374151' }}>
                    <p style={{ color: '#9ca3af' }}>No devices detected. Make sure the Python agent is running.</p>
                </div>
            ) : (
                <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
                    {devices.map((device) => (
                        <div key={device.id} style={{
                            backgroundColor: '#1f2937',
                            padding: '1.5rem',
                            borderRadius: '0.5rem',
                            borderTop: `4px solid ${device.status === 'ONLINE' ? '#22c55e' : '#ef4444'}`,
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                        }}>
                            
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                                <div>
                                    <h3 style={{ margin: 0, color: '#f9fafb', fontSize: '1.25rem' }}>{device.name}</h3>
                                    <span style={{ color: '#9ca3af', fontSize: '0.875rem' }}>{device.vendor} • {device.ip}</span>
                                </div>
                                <span style={{
                                    backgroundColor: device.status === 'ONLINE' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                                    color: device.status === 'ONLINE' ? '#4ade80' : '#f87171',
                                    padding: '0.25rem 0.75rem',
                                    borderRadius: '9999px',
                                    fontSize: '0.875rem',
                                    fontWeight: 'bold',
                                    height: 'fit-content'
                                }}>
                                    {device.status}
                                </span>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                                <div>
                                    <div style={{ color: '#9ca3af', fontSize: '0.875rem', marginBottom: '0.25rem' }}>CPU Usage</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: device.cpu > 80 ? '#f87171' : '#f3f4f6' }}>
                                        {device.cpu}%
                                    </div>
                                </div>
                                <div>
                                    <div style={{ color: '#9ca3af', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Memory</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: device.memory > 80 ? '#f87171' : '#f3f4f6' }}>
                                        {device.memory}%
                                    </div>
                                </div>
                            </div>

                            {(device.loops?.length > 0 || device.rjFaults?.length > 0) && (
                                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #374151' }}>
                                    {device.loops?.map((loop, idx) => (
                                        <div key={`loop-${idx}`} style={{ color: '#f87171', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
                                            ⚠️ {loop}
                                        </div>
                                    ))}
                                    {device.rjFaults?.map((fault, idx) => (
                                        <div key={`fault-${idx}`} style={{ color: '#f87171', fontSize: '0.875rem' }}>
                                            🔌 {fault}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default DeviceList;