import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

export default function Graph({ nodes, edges }) {
  const svgRef = useRef(null)

  useEffect(() => {
    const width = 700
    const height = 500

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove() // clear on re-render

    // d3 mutates these objects in place, so clone to avoid
    // weirdness on React re-renders
    const nodesCopy = nodes.map(d => ({ ...d }))
    const edgesCopy = edges.map(d => ({ ...d }))

    const simulation = d3.forceSimulation(nodesCopy)
      .force('link', d3.forceLink(edgesCopy).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-250))
      .force('center', d3.forceCenter(width / 2, height / 2))

    const link = svg.append('g')
      .selectAll('line')
      .data(edgesCopy)
      .join('line')
      .attr('stroke', d => d.isAlert ? '#e63946' : '#999')
      .attr('stroke-width', d => d.isAlert ? 3 : 1.5)
      .attr('stroke-opacity', 0.8)

    const node = svg.append('g')
      .selectAll('circle')
      .data(nodesCopy)
      .join('circle')
      .attr('r', 10)
      .attr('fill', d => {
        const isAlertNode = edgesCopy.some(
          e => e.isAlert && (e.source === d.id || e.source.id === d.id || e.target === d.id || e.target.id === d.id)
        )
        return isAlertNode ? '#e63946' : '#457b9d'
      })
      .call(drag(simulation))

    const label = svg.append('g')
      .selectAll('text')
      .data(nodesCopy)
      .join('text')
      .text(d => d.id)
      .attr('font-size', 10)
      .attr('dx', 14)
      .attr('dy', 4)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)

      label
        .attr('x', d => d.x)
        .attr('y', d => d.y)
    })

    function drag(sim) {
      function dragstarted(event) {
        if (!event.active) sim.alphaTarget(0.3).restart()
        event.subject.fx = event.subject.x
        event.subject.fy = event.subject.y
      }
      function dragged(event) {
        event.subject.fx = event.x
        event.subject.fy = event.y
      }
      function dragended(event) {
        if (!event.active) sim.alphaTarget(0)
        event.subject.fx = null
        event.subject.fy = null
      }
      return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
    }

    return () => simulation.stop()
  }, [nodes, edges])

  return <svg ref={svgRef} width={700} height={500} />
}