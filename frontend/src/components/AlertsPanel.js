import React, { useState, useEffect } from 'react';
import axios from 'axios';

const AlertsPanel = () => {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const { data } = await axios.get('/api/alerts');
                setAlerts(data);
                setLoading(false);
            } catch (err) {
                console.error("Failed to fetch alerts:", err);
                setLoading(false);
            }
        };
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 5000);
        return () => clearInterval(interval);
    }, []);

    const severityStyle = (severity) => {
        if (severity === 'critical') return { bg: 'rgba(239, 68, 68, 0.1)', color: '#f87171', icon: '🔴' };
        if (severity === 'warning') return { bg: 'rgba(251, 191, 36, 0.1)', color: '#fbbf24', icon: '🟡' };
        return { bg: 'rgba(96, 165, 250, 0.1)', color: '#60a5fa', icon: '🔵' };
    };

    if (loading) {
        return <div style={{ color: '#9ca3af', marginTop: '2rem' }}>Loading alerts...</div>;
    }

    return (
        <div style={{ marginTop: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ fontSize: '1.5rem', color: '#f3f4f6', margin: 0 }}>Alert Feed</h2>
                <span style={{ color: '#9ca3af', fontSize: '0.875rem' }}>
                    {alerts.length} alert{alerts.length !== 1 ? 's' : ''} recorded
                </span>
            </div>

            {alerts.length === 0 ? (
                <div style={{
                    backgroundColor: '#1f2937', padding: '2rem', borderRadius: '0.5rem',
                    textAlign: 'center', border: '1px dashed #374151'
                }}>
                    <p style={{ color: '#9ca3af' }}>No alerts yet. The system will log events as they occur.</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {alerts.map((alert) => {
                        const s = severityStyle(alert.severity);
                        return (
                            <div key={alert.id} style={{
                                backgroundColor: s.bg,
                                border: `1px solid ${s.color}33`,
                                borderRadius: '0.5rem',
                                padding: '1rem 1.25rem',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'flex-start'
                            }}>
                                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                                    <span style={{ fontSize: '1.1rem' }}>{s.icon}</span>
                                    <div>
                                        <div style={{ color: s.color, fontWeight: 'bold', fontSize: '0.875rem', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                                            {alert.severity}
                                        </div>
                                        <div style={{ color: '#f3f4f6', fontSize: '0.9rem' }}>
                                            {alert.message}
                                        </div>
                                        <div style={{ color: '#6b7280', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                            {alert.device_name}
                                        </div>
                                    </div>
                                </div>
                                <div style={{ color: '#6b7280', fontSize: '0.75rem', whiteSpace: 'nowrap', marginLeft: '1rem' }}>
                                    {new Date(alert.created_at).toLocaleTimeString()}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default AlertsPanel;