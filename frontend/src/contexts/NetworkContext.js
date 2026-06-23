import React, { createContext, useState, useEffect, useContext } from 'react';
import axios from 'axios'; 

// 1. Create the Context (The central data vault)
const NetworkContext = createContext();

// 2. Custom Hook (A shortcut for your UI components to access the vault)
export const useNetwork = () => {
    return useContext(NetworkContext);
};

// 3. The Provider (The engine that fetches the data and wraps your app)
export const NetworkProvider = ({ children }) => {
    // State to hold our live network data
    const [devices, setDevices] = useState([]);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Function to fetch data from your Python backend
        const fetchTelemetry = async () => {
            try {
                // IMPORTANT: If your Python backend runs on a different machine later, 
                // change this IP to match your server (e.g., 'http://192.168.1.50:5000/api/devices')
                const response = await axios.get('http://localhost:5000/api/devices');
                
                setDevices(response.data);
                setLastUpdated(new Date().toLocaleTimeString());
                setLoading(false);
            } catch (error) {
                // If the backend is off, we don't want the UI to crash, just log the error quietly.
                console.error("Failed to reach Python backend:", error);
            }
        };

        // Fetch immediately when the app loads...
        fetchTelemetry();
        
        // ...and then automatically fetch every 5 seconds (Polling)
        const interval = setInterval(fetchTelemetry, 5000); 

        // Cleanup the interval if the user leaves the page
        return () => clearInterval(interval);
    }, []);

    // Bundle the data we want to share with the rest of the app
    const value = {
        devices,
        lastUpdated,
        loading
    };

    return (
        <NetworkContext.Provider value={value}>
            {children}
        </NetworkContext.Provider>
    );
};