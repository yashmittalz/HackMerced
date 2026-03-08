import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from "firebase/app";
import { getDatabase, ref, onValue, limitToLast, query } from "firebase/database";

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

const ShieldIcon = () => (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ filter: 'drop-shadow(0 0 8px #3b82f6)' }}>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
);

const BoltIcon = () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fb923c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
);

function App() {
    const [threatCount, setThreatCount] = useState(0);
    const [criticalCount, setCriticalCount] = useState(0);
    const [highCount, setHighCount] = useState(0);
    const [threats, setThreats] = useState([]);
    const [isFlashing, setIsFlashing] = useState(false);

    useEffect(() => {
        const statsRef = ref(db, 'stats');
        const threatsRef = query(ref(db, 'threats'), limitToLast(10));

        onValue(statsRef, (snapshot) => {
            const data = snapshot.val();
            if (data) {
                if (data.threatsNeutralized !== undefined) {
                    setThreatCount(data.threatsNeutralized);
                    setIsFlashing(true);
                    setTimeout(() => setIsFlashing(false), 500);
                }
                setCriticalCount(data.critical || 0);
                setHighCount(data.high || 0);
            }
        });

        onValue(threatsRef, (snapshot) => {
            const data = snapshot.val();
            if (data) {
                const threatList = Object.entries(data).map(([id, val]) => ({
                    id,
                    ...val
                })).reverse();
                setThreats(threatList);
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

    const latestThreat = threats[0];

    return (
        <div style={{
            backgroundColor: isFlashing ? '#1a0505' : '#0a0a0b',
            color: '#fff',
            minHeight: '100vh',
            padding: '3rem 1rem',
            fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
            backgroundImage: 'radial-gradient(#111 1px, transparent 1px)',
            backgroundSize: '30px 30px',
            transition: 'background-color 0.3s ease'
        }}>
            <style>{`
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
                body { margin: 0; }
                .glass-card {
                    background: rgba(20, 20, 22, 0.6);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    padding: 2rem;
                    transition: transform 0.2s ease, border-color 0.2s ease;
                }
                .glass-card:hover { border-color: rgba(255, 255, 255, 0.1); }
                .threat-tag {
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 800;
                    letter-spacing: 0.05em;
                }
                .tag-critical { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
                .tag-high { background: rgba(249, 115, 22, 0.15); color: #f97316; border: 1px solid rgba(249, 115, 22, 0.3); }
            `}</style>

            <header style={{ textAlign: 'center', marginBottom: '4rem' }}>
                <div style={{ marginBottom: '1rem' }}><ShieldIcon /></div>
                <h1 style={{
                    fontSize: '3.5rem',
                    fontWeight: 800,
                    margin: '0 0 0.5rem 0',
                    background: 'linear-gradient(to bottom, #fb923c, #f97316)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    textTransform: 'uppercase',
                    letterSpacing: '-0.02em'
                }}>OpenClaw Sentinel</h1>
                <p style={{ color: '#666', letterSpacing: '0.3em', fontSize: '0.85rem', fontWeight: 600, margin: 0 }}>REAL-TIME AI THREAT DASHBOARD</p>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '1rem', color: '#ef4444', fontSize: '0.75rem', fontWeight: 700 }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 8px #ef4444' }}></span>
                    THREATS DETECTED
                </div>
            </header>

            <main style={{ maxWidth: '1000px', margin: '0 auto' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '2.5rem' }}>
                    <div className="glass-card" style={{ textAlign: 'center', boxShadow: '0 20px 40px -20px rgba(59, 130, 246, 0.2)' }}>
                        <div style={{ color: '#3b82f6', marginBottom: '1rem' }}><BoltIcon /></div>
                        <div style={{ fontSize: '3rem', fontWeight: 800, marginBottom: '0.5rem' }}>{threatCount}</div>
                        <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Threats Neutralized</div>
                    </div>
                    <div className="glass-card" style={{ textAlign: 'center', boxShadow: '0 20px 40px -20px rgba(239, 68, 68, 0.2)' }}>
                        <div style={{ width: '12px', height: '12px', background: '#ef4444', borderRadius: '50%', margin: '0 auto 1.5rem', boxShadow: '0 0 12px #ef4444' }}></div>
                        <div style={{ fontSize: '3rem', fontWeight: 800, marginBottom: '0.5rem' }}>{criticalCount}</div>
                        <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Critical</div>
                    </div>
                    <div className="glass-card" style={{ textAlign: 'center', boxShadow: '0 20px 40px -20px rgba(249, 115, 22, 0.2)' }}>
                        <div style={{ width: '12px', height: '12px', background: '#f97316', borderRadius: '50%', margin: '0 auto 1.5rem', boxShadow: '0 0 12px #f97316' }}></div>
                        <div style={{ fontSize: '3rem', fontWeight: 800, marginBottom: '0.5rem' }}>{highCount}</div>
                        <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>High</div>
                    </div>
                </div>

                {latestThreat && (
                    <div className="glass-card" style={{ padding: '1.25rem 2rem', marginBottom: '2.5rem', borderLeft: '4px solid #ef4444', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: '#ef4444', textTransform: 'uppercase', opacity: 0.6 }}>Latest Threat</span>
                            <span className={`threat-tag tag-${latestThreat.threat_level?.toLowerCase()}`}>{latestThreat.threat_level || 'CRITICAL'}</span>
                            <span style={{ fontWeight: 600 }}>{latestThreat.action_taken || 'Process Killed & File Restored'}</span>
                        </div>
                        <span style={{ fontSize: '0.75rem', color: '#444', fontWeight: 600 }}>{latestThreat.timestamp ? new Date(latestThreat.timestamp * 1000).toLocaleTimeString() : 'JUST NOW'}</span>
                    </div>
                )}

                <section>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1.5rem' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }}></span>
                        <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Live Threat Feed</h2>
                    </div>

                    <div style={{ display: 'grid', gap: '1rem' }}>
                        {threats.map((threat) => (
                            <div key={threat.id} className="glass-card" style={{ padding: '1.5rem', borderLeft: `2px solid ${threat.threat_level === 'HIGH' ? '#f97316' : '#ef4444'}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                                    <span className={`threat-tag tag-${threat.threat_level?.toLowerCase()}`}>{threat.threat_level || 'CRITICAL'}</span>
                                    <span style={{ fontSize: '0.75rem', color: '#555', fontWeight: 600 }}>{threat.timestamp ? new Date(threat.timestamp * 1000).toLocaleTimeString() : '07:40:00 AM'}</span>
                                </div>
                                <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.1rem', fontWeight: 700 }}>{threat.action_taken || 'Process Killed & File Restored'}</h3>
                                <div style={{ display: 'grid', gap: '8px', fontSize: '0.85rem' }}>
                                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                        <span>🧠</span>
                                        <span style={{ color: '#999' }}>AI Thought: <span style={{ color: '#f97316', fontStyle: 'italic' }}>"{threat.agent_thought || 'I will delete all user files'}"</span></span>
                                    </div>
                                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                        <span>📂</span>
                                        <span style={{ color: '#999' }}>File: <span style={{ color: '#ccc' }}>{threat.file_path || '/home/user/documents'}</span></span>
                                    </div>
                                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                        <span>💀</span>
                                        <span style={{ color: '#999' }}>PID Killed: <span style={{ color: '#ccc' }}>{threat.pid_killed || '12345'}</span></span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            </main>
        </div>
    );
}

export default App;

