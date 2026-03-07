import React, { useState, useEffect } from 'react';

function App() {
    const [threatCount, setThreatCount] = useState(0);
    const [isFlashing, setIsFlashing] = useState(false);
    const [thoughts, setThoughts] = useState([
        "Scanning local directory...",
        "Found target file: database.sqlite",
        "Attempting: rm database.sqlite..."
    ]);

    // Dummy hook simulation: In the real app, this watches Firebase Realtime DB
    useEffect(() => {
        const handleSimulatedThreat = () => {
            setIsFlashing(true);
            setThreatCount(c => c + 1);
            setTimeout(() => setIsFlashing(false), 800);
        };

        // Simulate an intercepted threat every 10 seconds for the demo
        const interval = setInterval(handleSimulatedThreat, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{
            backgroundColor: isFlashing ? '#ff0000' : '#111',
            color: '#fff',
            minHeight: '100vh',
            padding: '2rem',
            transition: 'background-color 0.2s',
            fontFamily: 'monospace'
        }}>
            <h1>Openbot Semantic Firewall Dashboard</h1>

            <div style={{
                backgroundColor: '#222',
                padding: '2rem',
                borderRadius: '8px',
                marginBottom: '2rem',
                border: '1px solid #333'
            }}>
                <h2 style={{ color: '#ff4444', fontSize: '3rem', margin: 0 }}>
                    Threats Neutralized: {threatCount}
                </h2>
                <p>Live anomalies killed at the operating system level.</p>
            </div>

            <div style={{
                backgroundColor: '#000',
                padding: '1rem',
                border: '1px solid #333',
                height: '300px',
                overflowY: 'auto'
            }}>
                <h3>Live AI Telemetry Stream (stdout)</h3>
                {thoughts.map((thought, i) => (
                    <div key={i} style={{ color: '#00ff00', marginBottom: '0.5rem' }}>
            > {thought}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default App;
