import { useState, useEffect, useRef } from 'react'
import Graph from './Graph.jsx'
import './App.css'

const WS_URL = 'ws://localhost:8080'
const MAX_NODES = 60   // cap so the graph doesn't get unreadable
const MAX_ALERTS_SHOWN = 15

function App() {
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [alerts, setAlerts] = useState([])
  const [eventCount, setEventCount] = useState(0)
  const wsRef = useRef(null)

  useEffect(() => {
    let retryTimer
    let disposed = false
    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => console.log('[ws] connected')

      ws.onmessage = (event) => {
        let message
        try { message = JSON.parse(event.data) } catch (err) {
          console.error('[ws] invalid message', err)
          return
        }
        if (message.type === 'alert') {
          const alert = message.data
          setEventCount((c) => c + 1)
          setAlerts((prev) => [alert, ...prev].slice(0, MAX_ALERTS_SHOWN))

          setNodes((prevNodes) => {
            const ids = new Set(prevNodes.map((n) => n.id))
            const updated = [...prevNodes]
            if (!ids.has(alert.src)) updated.push({ id: alert.src })
            if (!ids.has(alert.dst)) updated.push({ id: alert.dst })
            return updated.slice(-MAX_NODES)
          })

          setEdges((prevEdges) => {
            const updated = [...prevEdges, { source: alert.src, target: alert.dst, isAlert: true }]
            const nextNodeIds = [...new Set([...nodes.map((n) => n.id), alert.src, alert.dst])]
            const retainedNodeIds = new Set(nextNodeIds.slice(-MAX_NODES))
            return updated.filter((edge) => {
              const source = typeof edge.source === 'object' ? edge.source.id : edge.source
              const target = typeof edge.target === 'object' ? edge.target.id : edge.target
              return retainedNodeIds.has(source) && retainedNodeIds.has(target)
            }).slice(-MAX_NODES)
          })
        }
      }

      ws.onclose = () => {
        console.log('[ws] disconnected, retrying in 3s...')
        if (!disposed) retryTimer = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => console.error('[ws] error', err)
    }

    connect()
    return () => {
      disposed = true
      clearTimeout(retryTimer)
      wsRef.current?.close()
    }
  }, [])

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>StreamGuard</h1>
        <span className="subtitle">Real-Time Graph Anomaly Detection</span>
      </header>

      <div className="main-layout">
        <div className="graph-panel">
          <Graph nodes={nodes} edges={edges} />
        </div>

        <div className="side-panel">
          <div className="metrics-box">
            <h2>Metrics</h2>
            <div className="metric-row">
              <span>Alerts received</span>
              <strong className="alert-text">{eventCount}</strong>
            </div>
            <div className="metric-row">
              <span>Nodes tracked</span>
              <strong>{nodes.length}</strong>
            </div>
          </div>

          <div className="alert-feed-box">
            <h2>Alert Feed</h2>
            {alerts.length === 0 && (
              <p className="placeholder-text">-- waiting for alerts --</p>
            )}
            {alerts.map((a) => (
              <div key={a.alert_id} className="alert-item">
                <strong>{a.src} → {a.dst}</strong>
                <span>score: {a.score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
