import { useId } from 'react'
import type { SavedAnalysis } from './analyses'
import { buildEvaluationPoints } from './evaluation'

interface Props {
  analysis: SavedAnalysis
  selectedPly: number
  onSelectPly: (ply: number) => void
}

export default function EvaluationGraph({ analysis, selectedPly, onSelectPly }: Props) {
  const id = useId()
  const points = buildEvaluationPoints(analysis)
  const lastPly = points.at(-1)?.ply ?? 0
  if (!lastPly) return null

  const x = (ply: number) => 16 + (ply / lastPly) * 568
  const y = (value: number) => 80 - value * 60
  // Split at missing evaluations instead of inventing a score or bridging the gap.
  const segments: { x: number; y: number }[][] = []
  let segment: { x: number; y: number }[] = []
  for (const point of points) {
    if (point.value === null) {
      if (segment.length) segments.push(segment)
      segment = []
    } else {
      segment.push({ x: x(point.ply), y: y(point.value) })
    }
  }
  if (segment.length) segments.push(segment)
  const selected = points.find((point) => point.ply === selectedPly)

  return (
    <section className="evaluation-graph" aria-label="Game evaluation graph">
      <div className="evaluation-graph-heading">
        <strong>Evaluation wave</strong>
        <span>{selected?.label ?? 'Unavailable'}</span>
      </div>
      <svg viewBox="0 0 600 160" role="img" aria-label="White advantage above the center; Black advantage below. Click to select a position."
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect()
          const svgX = ((event.clientX - rect.left) / rect.width) * 600
          const nearest = points.reduce((best, point) =>
            Math.abs(x(point.ply) - svgX) < Math.abs(x(best.ply) - svgX) ? point : best,
          points[0]!)
          onSelectPly(nearest.ply)
        }}>
        <defs>
          <clipPath id={`${id}-top`}><rect width="600" height="80" /></clipPath>
          <clipPath id={`${id}-bottom`}><rect y="80" width="600" height="80" /></clipPath>
        </defs>
        <line x1="16" x2="584" y1="80" y2="80" stroke="currentColor" opacity=".35" strokeDasharray="4 4" />
        {segments.map((part, index) => {
          const line = part.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
          const area = `${line} L ${part.at(-1)!.x} 80 L ${part[0]!.x} 80 Z`
          return <g key={index}>
            <path d={area} fill="#ffffff" clipPath={`url(#${id}-top)`} />
            <path d={area} fill="#111111" clipPath={`url(#${id}-bottom)`} />
            <path d={line} fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinejoin="round" />
          </g>
        })}
        <line x1={x(selectedPly)} x2={x(selectedPly)} y1="12" y2="148" stroke="var(--text-h)" opacity=".5" />
        {selected?.value != null && <circle cx={x(selectedPly)} cy={y(selected.value)} r="5" fill="var(--accent)" stroke="var(--bg)" strokeWidth="2" />}
      </svg>
    </section>
  )
}
