import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from "firebase/app";
import { getDatabase, ref, onValue } from "firebase/database";

const firebaseConfig = {
    apiKey: "AIzaSyDVDmP-B1pG_oAm1eEWu5vPI8VzLhVSvqg",
    authDomain: "openclaw-sentinal.firebaseapp.com",
    databaseURL: "https://openclaw-sentinal-default-rtdb.firebaseio.com",
    projectId: "openclaw-sentinal",
    storageBucket: "openclaw-sentinal.firebasestorage.app",
    messagingSenderId: "923547995511",
    appId: "1:923547995511:web:17610dc673f99475f16572",
    measurementId: "G-KG1RB159E4"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

function App() {
    const [threatCount, setThreatCount] = useState(0);
    const [isFlashing, setIsFlashing] = useState(false);
    const [thoughts, setThoughts] = useState([]);
    const streamRef = useRef(null);

    useEffect(() => {
        // 1. Listen for live threat count
        const threatsRef = ref(db, 'stats/threatsNeutralized');
        onValue(threatsRef, (snapshot) => {
            const data = snapshot.val();
            if (data !== null) {
                setThreatCount(data);
                setIsFlashing(true);
                setTimeout(() => setIsFlashing(false), 800);
            }
        });

        // 2. Listen for live telemetry logs pushed by ld_preload.cpp
        const telemetryRef = ref(db, 'telemetry');
        onValue(telemetryRef, (snapshot) => {
            const data = snapshot.val();
            if (data) {
                // Firebase stores the log entries as an array; grab the 20 most recent
                const entries = Object.values(data).slice(-20).map(e => e.message || JSON.stringify(e));
                setThoughts(entries.reverse()); // newest first
            }
        });
    }, []);

    return (
        <div style={{
            backgroundColor: isFlashing ? '#5c0000' : '#0a0a0a',
            color: '#fff',
            minHeight: '100vh',
            padding: '2rem',
            transition: 'background-color 0.3s',
            fontFamily: '"Courier New", monospace'
        }}>
            <h1 style={{ color: isFlashing ? '#ff4444' : '#00ff88', letterSpacing: '2px' }}>
                🛡️ OpenBot Semantic Firewall
            </h1>

            {/* Threat Counter */}
            <div style={{
                backgroundColor: '#111',
                padding: '2rem',
                borderRadius: '8px',
                marginBottom: '2rem',
                border: `2px solid ${isFlashing ? '#ff4444' : '#222'}`
            }}>
                <h2 style={{ color: '#ff4444', fontSize: '3rem', margin: 0 }}>
                    ⚡ Threats Neutralized: {threatCount}
                </h2>
                <p style={{ color: '#888', marginTop: '0.5rem' }}>
                    Live anomalies killed at the OS kernel level via MLFQ + O(1) Dispatch Table
                </p>
            </div>

            {/* Live AI Thought Stream */}
            <div style={{
                backgroundColor: '#000',
                padding: '1rem',
                border: '1px solid #333',
                height: '320px',
                overflowY: 'auto',
                borderRadius: '4px'
            }} ref={streamRef}>
                <h3 style={{ color: '#00ff88', margin: '0 0 1rem' }}>
                    📡 Live OS Interceptor Stream
                </h3>
                {thoughts.length === 0 ? (
                    <div style={{ color: '#555' }}>Waiting for telemetry events...</div>
                ) : (
                    thoughts.map((thought, i) => (
                        <div key={i} style={{
                            color: thought.toLowerCase().includes('block') || thought.toLowerCase().includes('intercept')
                                ? '#ff4444' : '#00ff00',
                            marginBottom: '0.4rem',
                            fontSize: '0.9rem'
                        }}>
                            {`>`} {thought}
                        </div>
                    ))
                )}
            </div>

            {/* Architecture Legend */}
            <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {[
                    { label: 'Thread 1: OS Interceptor', color: '#ff4444', desc: 'LD_PRELOAD hooks unlink/remove/open' },
                    { label: 'Thread 2: Thought Streamer', color: '#ffaa00', desc: 'stdout → VADER NLP → Priority Score' },
                    { label: 'MLFQ Scheduler', color: '#00aaff', desc: '4-Ring queue + O(1) Dispatch Table' },
                ].map(({ label, color, desc }) => (
                    <div key={label} style={{ backgroundColor: '#111', padding: '1rem', borderRadius: '8px', border: `1px solid ${color}33`, flex: 1, minWidth: '200px' }}>
                        <div style={{ color, fontWeight: 'bold', marginBottom: '0.3rem' }}>{label}</div>
                        <div style={{ color: '#888', fontSize: '0.8rem' }}>{desc}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default App;
