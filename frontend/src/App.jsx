import { useState } from 'react'
import Graph from './Graph.jsx'
import './App.css'

// --- PHASE 1: hardcoded fake data. Phase 2 replaces this with
// live data coming in over the WebSocket from Role 3's backend. ---
const FAKE_NODES = [
  { id: '192.168.1.2' }, { id: '192.168.1.4' }, { id: '192.168.1.6' },
  { id: '192.168.1.9' }, { id: '10.0.0.4' }, { id: '10.0.0.5' },
  { id: '10.0.0.8' }, { id: '10.0.0.12' }, { id: '10.0.0.17' },
]

const FAKE_EDGES = [
  { source: '192.168.1.2', target: '10.0.0.4', isAlert: false },
  { source: '192.168.1.4', target: '10.0.0.5', isAlert: false },
  { source: '192.168.1.6', target: '10.0.0.8', isAlert: true },
  { source: '192.168.1.9', target: '10.0.0.12', isAlert: false },
  { source: '192.168.1.9', target: '10.0.0.17', isAlert: true },
]

function App() {
  const [eventCount] = useState(20)
  const [alertCount] = useState(2)

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>StreamGuard</h1>
        <span className="subtitle">Real-Time Graph Anomaly Detection</span>
      </header>

      <div className="main-layout">
        <div className="graph-panel">
          <Graph nodes={FAKE_NODES} edges={FAKE_EDGES} />
        </div>

        <div className="side-panel">
          <div className="metrics-box">
            <h2>Metrics</h2>
            <div className="metric-row">
              <span>Events processed</span>
              <strong>{eventCount}</strong>
            </div>
            <div className="metric-row">
              <span>Alerts raised</span>
              <strong className="alert-text">{alertCount}</strong>
            </div>
            <div className="metric-row">
              <span>Events/sec</span>
              <strong>-- (Phase 2)</strong>
            </div>
          </div>

          <div className="alert-feed-box">
            <h2>Alert Feed</h2>
            <p className="placeholder-text">
              -- live alerts will appear here in Phase 2 --
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App