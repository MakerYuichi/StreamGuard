import { useEffect, useRef, useState } from 'react'
import Graph from './Graph.jsx'
import './App.css'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8080'
const MAX_VISIBLE_NODES = 45
const MAX_VISIBLE_EDGES = 55
const MAX_VISIBLE_ALERTS = 12

export default function App() {
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])
  const [alerts, setAlerts] = useState([])
  const [alertCount, setAlertCount] = useState(0)
  const [rate, setRate] = useState(0)
  const [connected, setConnected] = useState(false)
  const queue = useRef([])
  const rateTimes = useRef([])

  useEffect(() => {
    let ws
    let retry
    let stopped = false

    const connect = () => {
      if (stopped) return
      try { ws = new WebSocket(WS_URL) } catch { retry = setTimeout(connect, 3000); return }

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!stopped) retry = setTimeout(connect, 3000)
      }
      ws.onerror = () => setConnected(false)
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg?.type === 'alert' && msg.data) {
            queue.current.push(msg.data)
            rateTimes.current.push(Date.now())
          }
        } catch { /* ignore malformed messages */ }
      }
    }

    connect()

    // One small React update every 300 ms. The stream itself is not throttled.
    const flush = setInterval(() => {
      const batch = queue.current.splice(0)
      if (!batch.length) return

      setAlertCount(c => c + batch.length)
      setAlerts(prev => [...batch.reverse(), ...prev].slice(0, MAX_VISIBLE_ALERTS))

      setNodes(prev => {
        const map = new Map(prev.map(n => [String(n.id), n]))
        for (const a of batch) {
          if (a.src != null) map.set(String(a.src), { id: String(a.src) })
          if (a.dst != null) map.set(String(a.dst), { id: String(a.dst) })
        }
        return Array.from(map.values()).slice(-MAX_VISIBLE_NODES)
      })

      setEdges(prev => {
        const map = new Map(prev.map(e => [`${e.source}|${e.target}`, e]))
        for (const a of batch) {
          if (a.src == null || a.dst == null) continue
          const source = String(a.src), target = String(a.dst)
          map.set(`${source}|${target}`, { source, target, score: Number(a.score) || 0, isAlert: true })
        }
        return Array.from(map.values()).slice(-MAX_VISIBLE_EDGES)
      })
    }, 300)

    const rateTimer = setInterval(() => {
      const cutoff = Date.now() - 1000
      rateTimes.current = rateTimes.current.filter(t => t >= cutoff)
      setRate(rateTimes.current.length)
    }, 500)

    return () => {
      stopped = true
      clearTimeout(retry)
      clearInterval(flush)
      clearInterval(rateTimer)
      try { ws?.close() } catch {}
    }
  }, [])

  return (
    <div className="app">
      <header className="header">
        <div>
          <div className="title-row">
            <h1>StreamGuard</h1>
            <span className={connected ? 'live on' : 'live'}><i />{connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
          <p>Real-Time Graph Anomaly Detection</p>
        </div>
        <div className="connection"><i className={connected ? 'on' : ''} />WebSocket {connected ? 'Connected' : 'Disconnected'}</div>
      </header>

      <main className="layout">
        <section className="graph-section">
          <div className="toolbar">
            <div><b>LIVE GRAPH</b><span>Streaming network connections</span></div>
            <div className="legend"><span><i className="blue"/>Normal</span><span><i className="red"/>Anomaly</span><span><em/>Alert edge</span></div>
          </div>
          <div className="graph-area">
            <Graph nodes={nodes} edges={edges} />
            {!nodes.length && <div className="empty"><div className="empty-dot"/><strong>Waiting for stream data</strong><span>Start the DARPA replayer to populate the graph.</span></div>}
          </div>
        </section>

        <aside className="sidebar">
          <section className="panel">
            <div className="panel-head"><h2>SYSTEM METRICS</h2><span>LIVE</span></div>
            <div className="metrics">
              <div><small>Alerts received</small><strong className="danger">{alertCount}</strong></div>
              <div><small>Nodes tracked</small><strong>{nodes.length}</strong></div>
              <div><small>Alerts / sec</small><strong>{rate}</strong></div>
              <div><small>Graph edges</small><strong>{edges.length}</strong></div>
            </div>
          </section>
          <section className="panel feed">
            <div className="panel-head"><h2>ALERT FEED</h2><span className="count">{alerts.length}</span></div>
            {!alerts.length && <div className="waiting">✓ &nbsp; Waiting for anomalies</div>}
            {alerts.map((a, i) => <div className="alert" key={`${a.alert_id ?? ''}-${a.timestamp ?? ''}-${i}`}>
              <div><b>{a.src} → {a.dst}</b><small>Detected anomaly</small></div>
              <strong>{Number(a.score).toFixed(2)}</strong>
            </div>)}
          </section>
        </aside>
      </main>
    </div>
  )
}
