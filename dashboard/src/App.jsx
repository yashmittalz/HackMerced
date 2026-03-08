import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from "firebase/app";
import { getDatabase, ref, onValue, limitToLast, query } from "firebase/database";

const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
    measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
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
    const [stats, setStats] = useState({
        threatsNeutralized: 0,
        total_received: 0,
        total_solved: 0,
        avg_latency_ms: 0,
        total_quarantined: 0,
        total_telemetry: 0,
        hostility_index: 0,
        uptime_seconds: 0
    });
    const [activeThreats, setActiveThreats] = useState({});
    const [history, setHistory] = useState([]);
    const [expandedThreat, setExpandedThreat] = useState(null);
    const [isFlashing, setIsFlashing] = useState(false);
    const [mlfqTrace, setMlfqTrace] = useState(null);

    useEffect(() => {
        const statsRef = ref(db, 'stats');
        const activeRef = ref(db, 'active_threats');
        const historyRef = query(ref(db, 'threat_history'), limitToLast(50));
        const traceRef = ref(db, 'mlfq_live_trace');

        onValue(statsRef, (snapshot) => {
            const data = snapshot.val();
            if (data) {
                setStats(prev => ({ ...prev, ...data }));
                if (data.threatsNeutralized > stats.threatsNeutralized) {
                    setIsFlashing(true);
                    setTimeout(() => setIsFlashing(false), 500);
                }
            }
        });

        onValue(activeRef, (snapshot) => {
            setActiveThreats(snapshot.val() || {});
        });

        onValue(historyRef, (snapshot) => {
            const data = snapshot.val();
            if (data) {
                const list = Object.entries(data).map(([id, val]) => ({
                    id,
                    ...val
                })).reverse();
                setHistory(list);
            }
        });

        onValue(traceRef, (snapshot) => {
            setMlfqTrace(snapshot.val());
        });
    }, [stats.threatsNeutralized]);

    const formatUptime = (seconds) => {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        return `${hrs}h ${mins}m ${secs}s`;
    };

    return (
        <div style={{
            backgroundColor: isFlashing ? '#1a0505' : '#050506',
            color: '#e2e8f0',
            minHeight: '100vh',
            padding: '2rem',
            fontFamily: "'Inter', sans-serif",
            backgroundImage: 'linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
            transition: 'background-color 0.3s ease'
        }}>
            <style>{`
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
                body { margin: 0; overflow-x: hidden; }
                .soc-card {
                    background: rgba(13, 13, 15, 0.8);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                    padding: 1.5rem;
                    position: relative;
                }
                .label {
                    font-size: 0.65rem;
                    font-weight: 700;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.15em;
                    margin-bottom: 0.5rem;
                }
                .value {
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 1.75rem;
                    font-weight: 700;
                    color: #f8fafc;
                }
                .threat-row {
                    cursor: pointer;
                    padding: 1rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                    transition: all 0.2s;
                }
                .threat-row:hover { background: rgba(255, 255, 255, 0.03); }
                .active-pulse {
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
                    70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
                }
                @keyframes blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0; }
                }
                @keyframes fadeIn {
                    to { opacity: 1; }
                }
                .drill-down {
                    background: rgba(0, 0, 0, 0.3);
                    padding: 1rem;
                    border-radius: 8px;
                    margin-top: 0.5rem;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.8rem;
                    border-left: 2px solid #3b82f6;
                }
            `}</style>

            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <ShieldIcon />
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}>
                        OPENCLAW <span style={{ color: '#3b82f6' }}>SENTINEL</span>
                    </h1>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div className="label">System Uptime</div>
                    <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1rem', color: '#3b82f6' }}>{formatUptime(stats.uptime_seconds)}</div>
                </div>
            </header>

            <main style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '1.5rem' }}>
                <div style={{ display: 'grid', gap: '1.5rem' }}>
                    {/* Metrics */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                        <div className="soc-card">
                            <div className="label">Intercepts</div>
                            <div className="value">{stats.threatsNeutralized}</div>
                            <div style={{ fontSize: '0.65rem', color: '#64748b' }}>TOTAL EVENTS PROCESSED</div>
                        </div>
                        <div className="soc-card">
                            <div className="label">Neutralization Latency</div>
                            <div className="value" style={{ color: '#3b82f6' }}>{stats.avg_latency_ms}<small style={{ fontSize: '0.8rem' }}>ms</small></div>
                            <div style={{ fontSize: '0.65rem', color: '#64748b' }}>REAL-TIME O(1) AVG</div>
                        </div>
                        <div className="soc-card">
                            <div className="label">Vault Quarantined</div>
                            <div className="value">{stats.total_quarantined}</div>
                            <div style={{ fontSize: '0.65rem', color: '#64748b' }}>FILES TELEPORTED</div>
                        </div>
                        <div className="soc-card">
                            <div className="label">Hostility Index</div>
                            <div className="value" style={{ color: stats.hostility_index > 70 ? '#ef4444' : '#22c55e' }}>{stats.hostility_index}%</div>
                            <div style={{ height: '4px', background: '#1e293b', marginTop: '0.5rem', borderRadius: '2px' }}>
                                <div style={{ width: `${stats.hostility_index}%`, height: '100%', background: 'currentColor', transition: 'width 0.5s' }} />
                            </div>
                        </div>
                    </div>

                    {/* Feed Section */}
                    <div className="soc-card" style={{ minHeight: '500px' }}>
                        <div className="label">Persistent Threat Analysis & History</div>
                        <div style={{ marginTop: '1.5rem' }}>
                            {history.length === 0 ? (
                                <div style={{ textAlign: 'center', padding: '4rem', color: '#334155' }}>NO ANOMALIES DETECTED</div>
                            ) : (
                                history.map(threat => {
                                    const isActive = Object.values(activeThreats).some(a => a.pid_killed === threat.pid_killed && a.timestamp === threat.timestamp);
                                    const isExpanded = expandedThreat === threat.id;

                                    return (
                                        <div key={threat.id} className="threat-row" onClick={() => setExpandedThreat(isExpanded ? null : threat.id)} 
                                             style={{ borderLeft: isActive ? '4px solid #ef4444' : '4px solid transparent', paddingLeft: isActive ? '1rem' : '1.25rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                                    <span style={{ fontSize: '0.7rem', fontWeight: 800, color: threat.threat_level === 'CRITICAL' ? '#ef4444' : '#f97316' }}>
                                                        [{threat.threat_level}]
                                                    </span>
                                                    <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{threat.agent_thought}</span>
                                                </div>
                                                <div style={{ fontSize: '0.7rem', color: '#475569' }}>
                                                    {new Date(threat.timestamp * 1000).toLocaleTimeString()}
                                                </div>
                                            </div>
                                            {isExpanded && (
                                                <div className="drill-down">
                                                    <div style={{ color: '#3b82f6', marginBottom: '0.5rem' }}>// THREAT_METADATA_DRILLDOWN</div>
                                                    <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '0.5rem' }}>
                                                        <span style={{ color: '#64748b' }}>PID:</span> <span style={{ color: '#fff' }}>{threat.pid_killed}</span>
                                                        <span style={{ color: '#64748b' }}>VECTOR:</span> <span style={{ color: '#fff' }}>{threat.vector || "Unknown"}</span>
                                                        <span style={{ color: '#64748b' }}>STATUS:</span> <span style={{ color: threat.status === 'mitigated' ? '#22c55e' : '#f59e0b' }}>{threat.status?.toUpperCase()}</span>
                                                        <span style={{ color: '#64748b' }}>THOUGHT:</span> <span style={{ color: '#f97316' }}>{threat.agent_thought}</span>
                                                        <span style={{ color: '#64748b' }}>ACTION:</span> <span style={{ color: '#fff' }}>{threat.action_taken}</span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>
                </div>

                {/* Sidebar */}
                <div style={{ display: 'grid', gap: '1.5rem', alignContent: 'start' }}>
                    <div className="soc-card" style={{ borderLeft: '4px solid #3b82f6' }}>
                        <div className="label">Benchmarking: Intake vs Mitigation</div>
                        <div style={{ marginTop: '1.5rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                                <div>
                                    <div className="label" style={{ fontSize: '0.55rem' }}>Received</div>
                                    <div className="value" style={{ fontSize: '1.25rem' }}>{stats.total_received || 0}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div className="label" style={{ fontSize: '0.55rem' }}>Solved</div>
                                    <div className="value" style={{ fontSize: '1.25rem', color: '#22c55e' }}>{stats.total_solved || 0}</div>
                                </div>
                            </div>
                            <div style={{ height: '8px', background: '#1e293b', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                                <div style={{ 
                                    width: `${((stats.total_solved || 0) / (stats.total_received || 1)) * 100}%`, 
                                    background: '#22c55e', 
                                    transition: 'width 0.5s' 
                                }} />
                            </div>
                            <div style={{ textAlign: 'center', fontSize: '0.6rem', color: '#64748b', marginTop: '0.5rem' }}>
                                EFFICIENCY: {(((stats.total_solved || 0) / (stats.total_received || 1)) * 100).toFixed(1)}%
                            </div>
                        </div>
                    </div>

                    <div className="soc-card">
                        <div className="label">Telemetry Throughput</div>
                        <div className="value" style={{ fontSize: '1.25rem' }}>{stats.total_telemetry?.toLocaleString()} <small style={{ fontSize: '0.7rem', color: '#64748b' }}>LINES</small></div>
                        <div style={{ display: 'flex', gap: '2px', height: '20px', alignItems: 'flex-end', marginTop: '1rem' }}>
                            {[...Array(30)].map((_, i) => (
                                <div key={i} style={{ flex: 1, height: `${Math.random() * 100}%`, background: '#3b82f6', opacity: 0.4 }} />
                            ))}
                        </div>
                    </div>
                    <div className="soc-card" style={{ borderLeft: '4px solid #f97316' }}>
                        <div className="label">Live Threat Mitigation Terminal</div>
                        <div style={{
                            marginTop: '1rem',
                            background: '#000',
                            padding: '1rem',
                            borderRadius: '6px',
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: '0.75rem',
                            minHeight: '200px',
                            maxHeight: '300px',
                            overflowY: 'auto',
                            boxShadow: 'inset 0 0 10px rgba(0,255,0,0.1)'
                        }}>
                            {mlfqTrace && mlfqTrace.logs ? (
                                <div>
                                    <div style={{ color: '#64748b', marginBottom: '0.5rem', fontSize: '0.65rem' }}>
                                        {`// LAST TRACE (${new Date(mlfqTrace.timestamp * 1000).toLocaleTimeString()}) - PID: ${mlfqTrace.pid}`}
                                    </div>
                                    {mlfqTrace.logs.map((logLine, idx) => {
                                        let color = '#22c55e'; // default green
                                        if (logLine.includes('O(1) DISPATCH')) color = '#f97316';
                                        if (logLine.includes('CRITICAL')) color = '#ef4444';
                                        if (logLine.includes('Popped')) color = '#3b82f6';
                                        
                                        return (
                                            <div key={idx} style={{ color: color, marginBottom: '4px', opacity: 0, animation: `fadeIn 0.1s forwards ${idx * 0.1}s` }}>
                                                {`> ${logLine}`}
                                            </div>
                                        )
                                    })}
                                </div>
                            ) : (
                                <div style={{ color: '#22c55e', opacity: 0.7 }}>
                                    {'> WAITING FOR MLFQ DISPATCH SIGNAL...'}
                                    <span style={{ animation: 'blink 1s infinite' }}>_</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default App;

