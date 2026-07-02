import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = `http://${window.location.hostname}:8000`;

const NotificationSettings = ({ onClose }) => {
    const [settings, setSettings] = useState({
        cpu_threshold: 85,
        mem_threshold: 90,
        email_enabled: false,
        email_address: '',
    });
    const [saved, setSaved] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [testSent, setTestSent] = useState(false);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const { data } = await axios.get(`${API_BASE}/api/settings`);
                setSettings(prev => ({ ...prev, ...data }));
            } catch (err) {
                // defaults fine
            } finally {
                setLoading(false);
            }
        };
        fetchSettings();
    }, []);

    const handleSave = async () => {
        try {
            await axios.post(`${API_BASE}/api/settings`, settings);
            setSaved(true);
            setTimeout(() => setSaved(false), 2500);
            setError(null);
        } catch (err) {
            setError('Failed to save. Make sure the backend is running.');
        }
    };

    const handleTestEmail = async () => {
        if (!settings.email_address) return;
        try {
            await axios.post(`${API_BASE}/api/test-email`, {
                email: settings.email_address
            });
            setTestSent(true);
            setTimeout(() => setTestSent(false), 3000);
            setError(null);
        } catch (err) {
            const detail = err.response?.data?.detail || 'Test failed. Check backend logs.';
            setError(detail);
        }
    };

    const update = (field, value) => {
        setSettings(prev => ({ ...prev, [field]: value }));
    };

    const handleBackdrop = (e) => {
        if (e.target === e.currentTarget) onClose();
    };

    return (
        <div
            onClick={handleBackdrop}
            style={{
                position: 'fixed', inset: 0,
                backgroundColor: 'rgba(0,0,0,0.7)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 1000
            }}
        >
            <div style={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '0.75rem',
                width: '100%',
                maxWidth: '480px',
                padding: '2rem',
                boxShadow: '0 25px 50px rgba(0,0,0,0.5)'
            }}>

                {/* Header */}
                <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: '1.75rem'
                }}>
                    <div>
                        <h2 style={{ color: '#f3f4f6', margin: 0, fontSize: '1.25rem' }}>
                            ⚙️ Notification Settings
                        </h2>
                        <p style={{ color: '#9ca3af', fontSize: '0.8rem', margin: '0.25rem 0 0 0' }}>
                            Configure alert thresholds and email notifications
                        </p>
                    </div>
                    <button onClick={onClose} style={{
                        backgroundColor: 'transparent', border: 'none',
                        color: '#9ca3af', fontSize: '1.5rem', cursor: 'pointer',
                        lineHeight: 1
                    }}>×</button>
                </div>

                {loading ? (
                    <div style={{ color: '#9ca3af', textAlign: 'center', padding: '2rem' }}>
                        Loading settings...
                    </div>
                ) : (
                    <>
                        {/* ---- THRESHOLDS ---- */}
                        <section style={{ marginBottom: '1.75rem' }}>
                            <h3 style={{
                                color: '#4ade80', fontSize: '0.8rem',
                                textTransform: 'uppercase', letterSpacing: '0.08em',
                                margin: '0 0 1rem 0'
                            }}>
                                Alert Thresholds
                            </h3>

                            {/* CPU */}
                            <div style={{ marginBottom: '1.25rem' }}>
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    marginBottom: '0.4rem'
                                }}>
                                    <label style={{ color: '#d1d5db', fontSize: '0.9rem' }}>
                                        CPU Usage Threshold
                                    </label>
                                    <span style={{
                                        color: '#4ade80', fontWeight: 'bold',
                                        fontFamily: 'monospace'
                                    }}>
                                        {settings.cpu_threshold}%
                                    </span>
                                </div>
                                <input
                                    type="range" min="50" max="99"
                                    value={settings.cpu_threshold}
                                    onChange={e => update('cpu_threshold', parseInt(e.target.value))}
                                    style={{ width: '100%', accentColor: '#4ade80' }}
                                />
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    color: '#6b7280', fontSize: '0.7rem', marginTop: '0.25rem'
                                }}>
                                    <span>50%</span>
                                    <span>Alert fires above this value</span>
                                    <span>99%</span>
                                </div>
                            </div>

                            {/* Memory */}
                            <div>
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    marginBottom: '0.4rem'
                                }}>
                                    <label style={{ color: '#d1d5db', fontSize: '0.9rem' }}>
                                        Memory Usage Threshold
                                    </label>
                                    <span style={{
                                        color: '#4ade80', fontWeight: 'bold',
                                        fontFamily: 'monospace'
                                    }}>
                                        {settings.mem_threshold}%
                                    </span>
                                </div>
                                <input
                                    type="range" min="50" max="99"
                                    value={settings.mem_threshold}
                                    onChange={e => update('mem_threshold', parseInt(e.target.value))}
                                    style={{ width: '100%', accentColor: '#4ade80' }}
                                />
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    color: '#6b7280', fontSize: '0.7rem', marginTop: '0.25rem'
                                }}>
                                    <span>50%</span>
                                    <span>Alert fires above this value</span>
                                    <span>99%</span>
                                </div>
                            </div>
                        </section>

                        <div style={{ borderTop: '1px solid #374151', marginBottom: '1.75rem' }} />

                        {/* ---- EMAIL ---- */}
                        <section style={{ marginBottom: '1.75rem' }}>
                            <h3 style={{
                                color: '#4ade80', fontSize: '0.8rem',
                                textTransform: 'uppercase', letterSpacing: '0.08em',
                                margin: '0 0 1rem 0'
                            }}>
                                Email Notifications
                            </h3>

                            <div style={{
                                backgroundColor: '#111827',
                                border: '1px solid #374151',
                                borderRadius: '0.5rem',
                                padding: '1rem',
                            }}>
                                {/* Toggle row */}
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginBottom: settings.email_enabled ? '0.75rem' : 0
                                }}>
                                    <div style={{
                                        display: 'flex', alignItems: 'center', gap: '0.5rem'
                                    }}>
                                        <span>📧</span>
                                        <div>
                                            <div style={{
                                                color: '#f3f4f6', fontSize: '0.9rem',
                                                fontWeight: '500'
                                            }}>
                                                Email Alerts (SMTP)
                                            </div>
                                            <div style={{ color: '#6b7280', fontSize: '0.7rem' }}>
                                                Send critical alerts to your inbox
                                            </div>
                                        </div>
                                    </div>

                                    {/* Toggle switch */}
                                    <div
                                        onClick={() => update('email_enabled', !settings.email_enabled)}
                                        style={{
                                            width: '44px', height: '24px',
                                            backgroundColor: settings.email_enabled ? '#4ade80' : '#374151',
                                            borderRadius: '9999px', cursor: 'pointer',
                                            position: 'relative', transition: 'background-color 0.2s',
                                            flexShrink: 0
                                        }}
                                    >
                                        <div style={{
                                            position: 'absolute', top: '3px',
                                            left: settings.email_enabled ? '23px' : '3px',
                                            width: '18px', height: '18px',
                                            backgroundColor: 'white', borderRadius: '50%',
                                            transition: 'left 0.2s'
                                        }} />
                                    </div>
                                </div>

                                {/* Email fields — only when enabled */}
                                {settings.email_enabled && (
                                    <>
                                        <input
                                            type="email"
                                            id="email-notification"
                                            name="email-notification"
                                            placeholder="recipient@email.com"
                                            value={settings.email_address}
                                            onChange={e => update('email_address', e.target.value)}
                                            style={{
                                                width: '100%',
                                                backgroundColor: '#1f2937',
                                                border: '1px solid #4b5563',
                                                borderRadius: '0.375rem',
                                                padding: '0.5rem 0.75rem',
                                                color: '#f3f4f6',
                                                fontSize: '0.85rem',
                                                outline: 'none',
                                                boxSizing: 'border-box',
                                                marginBottom: '0.75rem'
                                            }}
                                        />

                                        <div style={{ color: '#6b7280', fontSize: '0.7rem', marginBottom: '0.75rem' }}>
                                            Alerts sent via Gmail SMTP when a device goes OFFLINE or DEGRADED.
                                            Configure sender credentials in <code style={{ color: '#9ca3af' }}>server.py</code>
                                        </div>

                                        {/* Test button */}
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                            <button
                                                onClick={handleTestEmail}
                                                disabled={!settings.email_address}
                                                style={{
                                                    backgroundColor: 'transparent',
                                                    border: '1px solid #4ade80',
                                                    color: '#4ade80',
                                                    borderRadius: '0.375rem',
                                                    padding: '0.35rem 0.75rem',
                                                    fontSize: '0.8rem',
                                                    cursor: settings.email_address ? 'pointer' : 'not-allowed',
                                                    opacity: settings.email_address ? 1 : 0.5
                                                }}
                                            >
                                                📤 Send Test Email
                                            </button>
                                            {testSent && (
                                                <span style={{ color: '#4ade80', fontSize: '0.8rem' }}>
                                                    ✓ Test email sent!
                                                </span>
                                            )}
                                        </div>
                                    </>
                                )}
                            </div>
                        </section>

                        {/* Feedback */}
                        {error && (
                            <div style={{
                                backgroundColor: 'rgba(239,68,68,0.1)',
                                border: '1px solid #ef4444',
                                borderRadius: '0.375rem',
                                padding: '0.75rem',
                                color: '#f87171', fontSize: '0.8rem',
                                marginBottom: '1rem',
                                lineHeight: '1.5'
                            }}>
                                ⚠️ {error}
                                {error.includes('blocked') || error.includes('connect') ? (
                                    <div style={{ marginTop: '0.5rem', color: '#9ca3af' }}>
                                        Corporate networks often block SMTP ports 465/587.
                                        Try from a personal hotspot or home network.
                                    </div>
                                ) : null}
                            </div>
                        )}

                        {saved && (
                            <div style={{
                                backgroundColor: 'rgba(74,222,128,0.1)',
                                border: '1px solid #4ade80',
                                borderRadius: '0.375rem',
                                padding: '0.5rem 0.75rem',
                                color: '#4ade80', fontSize: '0.8rem',
                                marginBottom: '1rem'
                            }}>
                                ✓ Settings saved — thresholds applied to alert engine
                            </div>
                        )}

                        {/* Action buttons */}
                        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                            <button onClick={onClose} style={{
                                backgroundColor: 'transparent',
                                border: '1px solid #374151',
                                color: '#9ca3af', borderRadius: '0.375rem',
                                padding: '0.5rem 1.25rem', cursor: 'pointer',
                                fontSize: '0.9rem'
                            }}>
                                Cancel
                            </button>
                            <button onClick={handleSave} style={{
                                backgroundColor: '#4ade80', border: 'none',
                                color: '#111827', borderRadius: '0.375rem',
                                padding: '0.5rem 1.25rem', cursor: 'pointer',
                                fontWeight: 'bold', fontSize: '0.9rem'
                            }}>
                                Save Settings
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default NotificationSettings;