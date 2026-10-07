import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const W = 1000
const H = 680

// Stable D3 renderer: uses D3 for data binding, scales and SVG rendering,
// but intentionally does NOT run d3.forceSimulation(). This keeps the live
// dashboard responsive when thousands of WebSocket alerts arrive.
export default function Graph({ nodes, edges }) {
  const svgRef = useRef(null)

  useEffect(() => {
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const nodeData = (nodes || []).map(n => ({ ...n, id: String(n.id) }))
    const edgeData = (edges || []).filter(e => e?.source != null && e?.target != null)
      .map(e => ({ ...e, source: String(e.source), target: String(e.target) }))

    if (!nodeData.length) return

    // Degree statistics drive a deterministic network layout.
    const out = new Map()
    const incoming = new Map()
    edgeData.forEach(e => {
      out.set(e.source, (out.get(e.source) || 0) + 1)
      incoming.set(e.target, (incoming.get(e.target) || 0) + 1)
    })

    const degree = id => (out.get(id) || 0) + (incoming.get(id) || 0)
    const alertIds = new Set()
    edgeData.forEach(e => {
      if (e.isAlert) {
        alertIds.add(e.source)
        alertIds.add(e.target)
      }
    })

    // Three stable columns: source-dominant, balanced, destination-dominant.
    // This gives the graph a network/topology appearance without a force simulation.
    const groups = { left: [], middle: [], right: [] }
    nodeData.forEach(n => {
      const id = String(n.id)
      const o = out.get(id) || 0
      const i = incoming.get(id) || 0
      if (o > i + 1) groups.left.push(n)
      else if (i > o + 1) groups.right.push(n)
      else groups.middle.push(n)
    })

    Object.values(groups).forEach(g => g.sort((a, b) => degree(String(b.id)) - degree(String(a.id))))

    const positions = new Map()
    const placeColumn = (items, x) => {
      if (!items.length) return
      const y = d3.scalePoint()
        .domain(items.map(d => String(d.id)))
        .range([90, H - 90])
        .padding(0.55)
      items.forEach(n => positions.set(String(n.id), { x, y: y(String(n.id)) }))
    }

    placeColumn(groups.left, 170)
    placeColumn(groups.middle, 500)
    placeColumn(groups.right, 830)

    // If a column is empty, distribute remaining nodes across the central area.
    nodeData.forEach((n, idx) => {
      const id = String(n.id)
      if (!positions.has(id)) {
        positions.set(id, {
          x: 500,
          y: 90 + (idx * 73) % (H - 180)
        })
      }
    })

    const maxDegree = d3.max(nodeData, n => degree(String(n.id))) || 1
    const radius = d3.scaleSqrt().domain([0, maxDegree]).range([7, 15])

    // Subtle grid/background guides, rendered by D3.
    const guides = svg.append('g').attr('class', 'd3-guides')
    ;[170, 500, 830].forEach(x => {
      guides.append('line')
        .attr('x1', x).attr('y1', 55).attr('x2', x).attr('y2', H - 55)
        .attr('class', 'graph-guide')
    })

    // Edges: D3 data join, no React-per-edge rendering.
    const edgeLayer = svg.append('g').attr('class', 'd3-edges')
    edgeLayer.selectAll('line')
      .data(edgeData, d => `${d.source}|${d.target}`)
      .join('line')
      .attr('x1', d => positions.get(d.source)?.x ?? 500)
      .attr('y1', d => positions.get(d.source)?.y ?? H / 2)
      .attr('x2', d => positions.get(d.target)?.x ?? 500)
      .attr('y2', d => positions.get(d.target)?.y ?? H / 2)
      .attr('class', d => d.isAlert ? 'edge alert-edge' : 'edge')
      .attr('opacity', d => d.isAlert ? 0.72 : 0.28)

    // Nodes and labels: D3 data join.
    const nodeLayer = svg.append('g').attr('class', 'd3-nodes')
    const node = nodeLayer.selectAll('g')
      .data(nodeData, d => String(d.id))
      .join('g')
      .attr('transform', d => {
        const p = positions.get(String(d.id))
        return `translate(${p.x},${p.y})`
      })

    node.append('circle')
      .attr('r', d => radius(degree(String(d.id))))
      .attr('class', d => alertIds.has(String(d.id)) ? 'node alert-node' : 'node')
      .attr('filter', d => alertIds.has(String(d.id)) ? 'url(#glow)' : null)

    node.append('text')
      .attr('x', 17)
      .attr('y', 4)
      .attr('class', 'label')
      .text(d => d.id)

    // Definitions are also created with D3 so the visual layer is entirely D3-driven.
    const defs = svg.append('defs')
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'blur')
    const merge = filter.append('feMerge')
    merge.append('feMergeNode').attr('in', 'blur')
    merge.append('feMergeNode').attr('in', 'SourceGraphic')
  }, [nodes, edges])

  return (
    <svg
      ref={svgRef}
      className="graph"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      aria-label="Live StreamGuard network graph"
    />
  )
}
