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
                    {devices.map((device) => {
                        const isOnline = device.status === 'ONLINE';
                        const isDegraded = device.status === 'DEGRADED';
                        // border: green online, amber degraded, red offline
                        const borderColor = isOnline ? '#22c55e' : isDegraded ? '#fbbf24' : '#ef4444';
                        const badgeBg = isOnline ? 'rgba(34, 197, 94, 0.1)' : isDegraded ? 'rgba(251, 191, 36, 0.1)' : 'rgba(239, 68, 68, 0.1)';
                        const badgeColor = isOnline ? '#4ade80' : isDegraded ? '#fbbf24' : '#f87171';

                        return (
                            <div key={device.id} style={{
                                backgroundColor: '#1f2937',
                                padding: '1.5rem',
                                borderRadius: '0.5rem',
                                borderTop: `4px solid ${borderColor}`,
                                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                            }}>

                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                                    <div>
                                        <h3 style={{ margin: 0, color: '#f9fafb', fontSize: '1.25rem' }}>{device.name}</h3>
                                        <span style={{ color: '#9ca3af', fontSize: '0.875rem' }}>{device.vendor} • {device.ip}</span>
                                    </div>
                                    <span style={{
                                        backgroundColor: badgeBg,
                                        color: badgeColor,
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

                                {/* --- FAULT BADGES: loops + RJ45/cable faults --- */}
                                {(device.loops?.length > 0 || device.cable_faults?.length > 0) && (
                                    <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #374151' }}>
                                        {device.loops?.map((loop, idx) => (
                                            <div key={`loop-${idx}`} style={{
                                                display: 'flex', alignItems: 'center', gap: '0.4rem',
                                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                                color: '#f87171', fontSize: '0.8rem',
                                                padding: '0.35rem 0.6rem', borderRadius: '0.375rem',
                                                marginBottom: '0.4rem'
                                            }}>
                                                🔁 <strong>LOOP</strong> {loop.port}: {loop.detail}
                                            </div>
                                        ))}
                                        {device.cable_faults?.map((fault, idx) => (
                                            <div key={`fault-${idx}`} style={{
                                                display: 'flex', alignItems: 'center', gap: '0.4rem',
                                                backgroundColor: 'rgba(251, 191, 36, 0.1)',
                                                color: '#fbbf24', fontSize: '0.8rem',
                                                padding: '0.35rem 0.6rem', borderRadius: '0.375rem',
                                                marginBottom: '0.4rem'
                                            }}>
                                                🔌 <strong>RJ45</strong> {fault.port}: {fault.detail}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default DeviceList;