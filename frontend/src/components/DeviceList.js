import React, { useState } from 'react';
import { useNetwork } from '../contexts/NetworkContext';

const DeviceList = () => {
    const { devices, loading, lastUpdated } = useNetwork();
    const [expanded, setExpanded] = useState(null);

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
                        const borderColor = isOnline ? '#22c55e' : isDegraded ? '#fbbf24' : '#ef4444';
                        const badgeBg = isOnline ? 'rgba(34, 197, 94, 0.1)' : isDegraded ? 'rgba(251, 191, 36, 0.1)' : 'rgba(239, 68, 68, 0.1)';
                        const badgeColor = isOnline ? '#4ade80' : isDegraded ? '#fbbf24' : '#f87171';
                        const isExpanded = expanded === device.id;

                        return (
                            <div key={device.id} style={{
                                backgroundColor: '#1f2937',
                                padding: '1.5rem',
                                borderRadius: '0.5rem',
                                borderTop: `4px solid ${borderColor}`,
                                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                                cursor: 'pointer',
                                transition: 'box-shadow 0.2s'
                            }}
                            onClick={() => setExpanded(isExpanded ? null : device.id)}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                                    <div>
                                        <h3 style={{ margin: 0, color: '#f9fafb', fontSize: '1.25rem' }}>{device.name}</h3>
                                        <span style={{ color: '#9ca3af', fontSize: '0.875rem' }}>{device.vendor} • {device.ip}</span>
                                    </div>
                                    <span style={{
                                        backgroundColor: badgeBg, color: badgeColor,
                                        padding: '0.25rem 0.75rem', borderRadius: '9999px',
                                        fontSize: '0.875rem', fontWeight: 'bold', height: 'fit-content'
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

                                {/* Fault badges */}
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

                                {/* Port map — shown when card is clicked */}
                                {isExpanded && device.ports && device.ports.length > 0 && (
                                    <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #374151' }}>
                                        <div style={{ color: '#9ca3af', fontSize: '0.75rem', marginBottom: '0.5rem' }}>
                                            Port Map — {device.ports.filter(p => p.state === 'up').length}/{device.ports.length} up
                                        </div>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                            {device.ports.map((port, idx) => {
                                                const portColor = port.state === 'up' ? '#22c55e'
                                                    : port.state === 'fault' ? '#ef4444'
                                                    : '#4b5563';
                                                return (
                                                    <div key={idx} title={`${port.name} — ${port.state} (${port.utilization}%)`} style={{
                                                        width: '18px', height: '18px',
                                                        backgroundColor: portColor,
                                                        borderRadius: '3px',
                                                        opacity: port.state === 'down' ? 0.4 : 1,
                                                        cursor: 'default',
                                                        position: 'relative'
                                                    }} />
                                                );
                                            })}
                                        </div>
                                        <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.7rem', color: '#6b7280' }}>
                                            <span><span style={{ color: '#22c55e' }}>■</span> Up</span>
                                            <span><span style={{ color: '#4b5563', opacity: 0.4 }}>■</span> Down</span>
                                            <span><span style={{ color: '#ef4444' }}>■</span> Fault</span>
                                        </div>
                                    </div>
                                )}

                                {/* Expand hint */}
                                <div style={{ textAlign: 'center', color: '#4b5563', fontSize: '0.7rem', marginTop: '0.75rem' }}>
                                    {isExpanded ? '▲ click to collapse' : '▼ click for port map'}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default DeviceList;