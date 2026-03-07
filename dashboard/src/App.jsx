import React, { useState, useEffect } from 'react';
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
    const [thoughts, setThoughts] = useState([
        "Scanning local directory...",
        "Found target file: database.sqlite",
        "Attempting: rm database.sqlite..."
    ]);

    useEffect(() => {
        const threatsRef = ref(db, 'stats/threatsNeutralized');

        // Listen for live updates from Firebase
        onValue(threatsRef, (snapshot) => {
            const data = snapshot.val();
            if (data !== null) {
                setThreatCount(data);

                // Flash the screen red when the count goes up
                setIsFlashing(true);
                setTimeout(() => setIsFlashing(false), 800);
            }
        });
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
                        {">"} {thought}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default App;
