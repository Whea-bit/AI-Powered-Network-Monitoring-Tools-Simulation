import React, { createContext, useState, useEffect, useContext } from 'react';
import axios from 'axios';

const NetworkContext = createContext();

export const useNetwork = () => {
    return useContext(NetworkContext);
};

export const NetworkProvider = ({ children }) => {
    const [devices, setDevices] = useState([]);
    const [summary, setSummary] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchTelemetry = async () => {
            try {
                // fetch devices and summary together
                const [devicesRes, summaryRes] = await Promise.all([
                    axios.get('/api/devices'),
                    axios.get('/api/summary'),
                ]);

                setDevices(devicesRes.data);
                setSummary(summaryRes.data);
                setLastUpdated(new Date().toLocaleTimeString());
                setError(null);
                setLoading(false);
            } catch (error) {
                console.error("Failed to reach Python backend:", error);
                setError("Backend offline");
                setLoading(false);
            }
        };

        fetchTelemetry();
        const interval = setInterval(fetchTelemetry, 5000);
        return () => clearInterval(interval);
    }, []);

    const value = {
        devices,
        summary,
        lastUpdated,
        loading,
        error
    };

    return (
        <NetworkContext.Provider value={value}>
            {children}
        </NetworkContext.Provider>
    );
};