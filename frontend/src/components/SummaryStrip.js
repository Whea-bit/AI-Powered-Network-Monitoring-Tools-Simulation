import React from 'react';
import { useNetwork } from '../contexts/NetworkContext';

const SummaryStrip = () => {
    const { summary } = useNetwork();

    if (!summary) return null;

    const cards = [
        { label: 'Total Devices', value: summary.total, color: '#f3f4f6' },
        { label: 'Online', value: summary.online, color: '#4ade80' },
        { label: 'Offline', value: summary.offline, color: summary.offline > 0 ? '#f87171' : '#f3f4f6' },
        { label: 'Degraded', value: summary.degraded, color: summary.degraded > 0 ? '#fbbf24' : '#f3f4f6' },
        { label: 'Loops', value: summary.loops, color: summary.loops > 0 ? '#f87171' : '#f3f4f6' },
        { label: 'Cable Faults', value: summary.cable_faults, color: summary.cable_faults > 0 ? '#fbbf24' : '#f3f4f6' },
        { label: 'Avg CPU', value: `${summary.avg_cpu}%`, color: summary.avg_cpu > 80 ? '#f87171' : '#f3f4f6' },
        { label: 'Open Alerts', value: summary.open_alerts, color: summary.open_alerts > 0 ? '#fbbf24' : '#f3f4f6' },
    ];

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '1rem',
            marginTop: '1.5rem'
        }}>
            {cards.map((card) => (
                <div key={card.label} style={{
                    backgroundColor: '#1f2937',
                    padding: '1rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: '1px solid #374151'
                }}>
                    <div style={{ color: '#9ca3af', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.4rem' }}>
                        {card.label}
                    </div>
                    <div style={{ fontSize: '1.75rem', fontWeight: 'bold', color: card.color }}>
                        {card.value}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default SummaryStrip;