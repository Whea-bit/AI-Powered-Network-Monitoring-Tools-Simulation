import React from 'react';
import { useNetwork } from '../contexts/NetworkContext';

const NODE_POSITIONS = {
    'core-sw-01':  { x: 400, y: 80,  label: 'Core-Switch-01',  icon: '🔲' },
    'dist-fw-01':  { x: 200, y: 200, label: 'Edge-FortiGate',   icon: '🛡️' },
    'acc-sw-02':   { x: 600, y: 200, label: 'Access-Switch-02', icon: '🔲' },
    'acc-ap-01':   { x: 150, y: 340, label: 'Aruba-AP-Lobby',   icon: '📡' },
    'acc-ap-02':   { x: 650, y: 340, label: 'Meraki-AP-Hall',   icon: '📡' },
};

const LINKS = [
    { from: 'core-sw-01', to: 'dist-fw-01' },
    { from: 'core-sw-01', to: 'acc-sw-02' },
    { from: 'dist-fw-01', to: 'acc-ap-01' },
    { from: 'acc-sw-02', to: 'acc-ap-02' },
];

const TopologyMap = () => {
    const { devices } = useNetwork();

    const deviceMap = {};
    devices.forEach((d) => { deviceMap[d.id] = d; });

    const statusColor = (id) => {
        const d = deviceMap[id];
        if (!d) return '#6b7280';
        if (d.status === 'ONLINE') return '#4ade80';
        if (d.status === 'DEGRADED') return '#fbbf24';
        return '#f87171';
    };

    const linkColor = (fromId, toId) => {
        const from = deviceMap[fromId];
        const to = deviceMap[toId];
        if (!from || !to) return '#374151';
        if (from.status === 'OFFLINE' || to.status === 'OFFLINE') return '#ef4444';
        const avgCpu = (from.cpu + to.cpu) / 2;
        if (avgCpu > 80) return '#ef4444';
        if (avgCpu > 60) return '#fbbf24';
        return '#4ade80';
    };

    const linkWidth = (fromId, toId) => {
        const from = deviceMap[fromId];
        const to = deviceMap[toId];
        if (!from || !to) return 2;
        const avgCpu = (from.cpu + to.cpu) / 2;
        return Math.max(2, Math.min(6, avgCpu / 20));
    };

    return (
        <div style={{ marginTop: '1rem' }}>
            <h2 style={{ fontSize: '1.5rem', color: '#f3f4f6', marginBottom: '1rem' }}>Network Topology</h2>
            <div style={{
                backgroundColor: '#1f2937', borderRadius: '0.5rem', border: '1px solid #374151',
                padding: '1rem', position: 'relative'
            }}>
                {/* Legend */}
                <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', fontSize: '0.75rem' }}>
                    <span><span style={{ color: '#4ade80' }}>●</span> Online / &lt;60% util</span>
                    <span><span style={{ color: '#fbbf24' }}>●</span> Degraded / 60-80%</span>
                    <span><span style={{ color: '#ef4444' }}>●</span> Offline / &gt;80%</span>
                </div>

                <svg viewBox="0 0 800 420" style={{ width: '100%', height: 'auto' }}>
                    {/* Links */}
                    {LINKS.map((link, idx) => {
                        const from = NODE_POSITIONS[link.from];
                        const to = NODE_POSITIONS[link.to];
                        return (
                            <line key={idx}
                                x1={from.x} y1={from.y}
                                x2={to.x} y2={to.y}
                                stroke={linkColor(link.from, link.to)}
                                strokeWidth={linkWidth(link.from, link.to)}
                                strokeDasharray={
                                    deviceMap[link.from]?.status === 'OFFLINE' || deviceMap[link.to]?.status === 'OFFLINE'
                                        ? '8,4' : 'none'
                                }
                            />
                        );
                    })}

                    {/* Nodes */}
                    {Object.entries(NODE_POSITIONS).map(([id, pos]) => {
                        const dev = deviceMap[id];
                        const color = statusColor(id);
                        return (
                            <g key={id}>
                                {/* Glow ring */}
                                <circle cx={pos.x} cy={pos.y} r={32}
                                    fill="none" stroke={color} strokeWidth={2} opacity={0.3} />
                                {/* Main circle */}
                                <circle cx={pos.x} cy={pos.y} r={26}
                                    fill="#1f2937" stroke={color} strokeWidth={2.5} />
                                {/* Icon */}
                                <text x={pos.x} y={pos.y + 5} textAnchor="middle"
                                    fontSize="18" fill="white">
                                    {pos.icon}
                                </text>
                                {/* Label */}
                                <text x={pos.x} y={pos.y + 50} textAnchor="middle"
                                    fontSize="11" fill="#d1d5db" fontFamily="system-ui">
                                    {pos.label}
                                </text>
                                {/* Status + CPU below label */}
                                <text x={pos.x} y={pos.y + 64} textAnchor="middle"
                                    fontSize="10" fill={color} fontFamily="monospace">
                                    {dev ? `${dev.status} · CPU ${dev.cpu}%` : 'NO DATA'}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>
        </div>
    );
};

export default TopologyMap;