import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useNetwork } from '../contexts/NetworkContext';

const AiAssist = () => {
    const { devices } = useNetwork();
    const [messages, setMessages] = useState([
        { role: 'assistant', content: "I'm your AI network assistant. I have full visibility into your device states. Ask me anything — troubleshooting, analysis, recommendations." }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const sendMessage = async () => {
        const text = input.trim();
        if (!text || loading) return;

        const userMsg = { role: 'user', content: text };
        const updatedMessages = [...messages, userMsg];
        setMessages(updatedMessages);
        setInput('');
        setLoading(true);

        try {
            // Updated to talk to your local Gemini-ready FastAPI backend
            const res = await axios.post(`http://${window.location.hostname}:8000/api/ai-assist`, {
                message: text
            });

            setMessages([...updatedMessages, { role: 'assistant', content: res.data.response }]);
        } catch (err) {
            console.error("Backend error:", err);
            setMessages([...updatedMessages, { 
                role: 'assistant', 
                content: 'Error: Could not connect to the AI network assistant. Please ensure your backend server is running.' 
            }]);
        }
        setLoading(false);
    };

    return (
        <div style={{ marginTop: '1rem' }}>
            <h2 style={{ fontSize: '1.5rem', color: '#f3f4f6', marginBottom: '1rem' }}>AI Network Assistant</h2>
            <div style={{
                backgroundColor: '#0d1117', border: '1px solid #374151',
                borderRadius: '0.5rem', overflow: 'hidden', fontFamily: 'system-ui, sans-serif'
            }}>
                <div ref={scrollRef} style={{
                    height: '400px', overflowY: 'auto', padding: '1rem',
                    display: 'flex', flexDirection: 'column', gap: '0.75rem'
                }}>
                    {messages.map((msg, idx) => (
                        <div key={idx} style={{
                            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                            maxWidth: '80%',
                            backgroundColor: msg.role === 'user' ? 'rgba(74, 222, 128, 0.1)' : '#1f2937',
                            border: msg.role === 'user' ? '1px solid #4ade8033' : '1px solid #374151',
                            borderRadius: '0.75rem',
                            padding: '0.75rem 1rem',
                            fontSize: '0.9rem',
                            lineHeight: '1.5'
                        }}>
                            <div style={{ color: msg.role === 'user' ? '#4ade80' : '#60a5fa', fontSize: '0.7rem', fontWeight: 'bold', marginBottom: '0.25rem' }}>
                                {msg.role === 'user' ? 'YOU' : 'AI ASSISTANT'}
                            </div>
                            <div style={{ color: '#f3f4f6', whiteSpace: 'pre-wrap' }}>
                                {msg.content}
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div style={{ color: '#9ca3af', fontSize: '0.85rem', fontStyle: 'italic' }}>
                            Analyzing network state...
                        </div>
                    )}
                </div>

                <div style={{
                    display: 'flex', alignItems: 'center',
                    borderTop: '1px solid #374151', padding: '0.75rem 1rem', gap: '0.75rem'
                }}>
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                        name="ai-input"
                        placeholder="Ask about your network..."
                        style={{
                            flex: 1, backgroundColor: 'transparent', border: 'none',
                            outline: 'none', color: '#f3f4f6', fontSize: '0.9rem'
                        }}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={loading}
                        style={{
                            backgroundColor: '#4ade80', color: '#111827',
                            border: 'none', borderRadius: '0.375rem',
                            padding: '0.5rem 1rem', fontWeight: 'bold',
                            cursor: loading ? 'wait' : 'pointer',
                            opacity: loading ? 0.5 : 1
                        }}
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AiAssist;