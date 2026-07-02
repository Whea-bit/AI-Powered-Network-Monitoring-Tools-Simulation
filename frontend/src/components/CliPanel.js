import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const CliPanel = () => {
    const [history, setHistory] = useState([
        { type: 'system', text: "AI-NOC Console ready. Type 'help' for commands." }
    ]);
    const [input, setInput] = useState('');
    const [cmdHistory, setCmdHistory] = useState([]);
    const [histIndex, setHistIndex] = useState(-1);
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history]);

    const runCommand = async () => {
        const cmd = input.trim();
        if (!cmd || isLoading) return;

        setHistory((h) => [...h, { type: 'input', text: cmd }]);
        setCmdHistory((c) => [...c, cmd]);
        setHistIndex(-1);
        setInput('');

        if (cmd === 'clear') {
            setHistory([]);
            return;
        }

        setIsLoading(true);
        try {
            const res = await axios.post(`http://${window.location.hostname}:8000/api/cli`, { command: cmd });
            setHistory((h) => [...h, { type: 'output', text: res.data.output }]);
        } catch (err) {
            setHistory((h) => [...h, { type: 'error', text: 'Error: could not reach backend. Make sure uvicorn is running.' }]);
        }
        setIsLoading(false);
    };

    const handleKey = (e) => {
        if (e.key === 'Enter') {
            runCommand();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (cmdHistory.length === 0) return;
            const newIndex = histIndex === -1 ? cmdHistory.length - 1 : Math.max(0, histIndex - 1);
            setHistIndex(newIndex);
            setInput(cmdHistory[newIndex]);
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (histIndex === -1) return;
            const newIndex = histIndex + 1;
            if (newIndex >= cmdHistory.length) {
                setHistIndex(-1);
                setInput('');
            } else {
                setHistIndex(newIndex);
                setInput(cmdHistory[newIndex]);
            }
        }
    };

    const colorFor = (type) => {
        if (type === 'input') return '#4ade80';
        if (type === 'error') return '#f87171';
        if (type === 'system') return '#60a5fa';
        return '#d1d5db';
    };

    return (
        <div style={{ marginTop: '1rem' }}>
            <h2 style={{ fontSize: '1.5rem', color: '#f3f4f6', marginBottom: '1rem' }}>
                Centralized CLI
            </h2>
            <div style={{
                backgroundColor: '#0d1117',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
                overflow: 'hidden',
                fontFamily: 'monospace'
            }}>
                {/* Output area */}
                <div ref={scrollRef} style={{
                    height: '360px',
                    overflowY: 'auto',
                    padding: '1rem',
                    fontSize: '0.875rem',
                    lineHeight: '1.6'
                }}>
                    {history.map((line, idx) => (
                        <div key={idx} style={{
                            color: colorFor(line.type),
                            whiteSpace: 'pre-wrap',
                            marginBottom: '0.25rem'
                        }}>
                            {line.type === 'input' ? `noc> ${line.text}` : line.text}
                        </div>
                    ))}
                    {isLoading && (
                        <div style={{ color: '#9ca3af', fontStyle: 'italic' }}>
                            processing...
                        </div>
                    )}
                </div>

                {/* Input row */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    borderTop: '1px solid #374151',
                    padding: '0.5rem 1rem',
                    gap: '0.5rem'
                }}>
                    <span style={{ color: '#4ade80', fontFamily: 'monospace' }}>noc&gt;</span>
                    <input
                        id="cli-input"
                        name="cli-input"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKey}
                        placeholder="type a command and press Enter..."
                        disabled={isLoading}
                        autoComplete="off"
                        style={{
                            flex: 1,
                            backgroundColor: 'transparent',
                            border: 'none',
                            outline: 'none',
                            color: '#f3f4f6',
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                            cursor: isLoading ? 'wait' : 'text'
                        }}
                        autoFocus
                    />
                </div>
            </div>

            {/* Command hint bar */}
            <div style={{ color: '#6b7280', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                Commands: &nbsp;
                <code style={{ color: '#9ca3af' }}>show devices</code> ·
                <code style={{ color: '#9ca3af' }}> show device &lt;name&gt;</code> ·
                <code style={{ color: '#9ca3af' }}> show loops</code> ·
                <code style={{ color: '#9ca3af' }}> show faults</code> ·
                <code style={{ color: '#9ca3af' }}> show alerts</code> ·
                <code style={{ color: '#9ca3af' }}> top</code> ·
                <code style={{ color: '#9ca3af' }}> ping &lt;ip&gt;</code> ·
                <code style={{ color: '#9ca3af' }}> ask &lt;question&gt;</code> ·
                <code style={{ color: '#9ca3af' }}> clear</code> ·
                <code style={{ color: '#9ca3af' }}> help</code>
            </div>
        </div>
    );
};

export default CliPanel;