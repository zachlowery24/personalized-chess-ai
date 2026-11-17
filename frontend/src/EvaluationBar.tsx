import type { SavedAnalysis } from './analyses'
import { buildEvaluationPoints } from './evaluation'

interface Props {
  analysis: SavedAnalysis | null
  ply: number
  orientation: 'white' | 'black'
}

export default function EvaluationBar({ analysis, ply, orientation }: Props) {
  const point = analysis
    ? buildEvaluationPoints(analysis).find((item) => item.ply === ply)
    : undefined
  const available = point?.value != null
  const whitePercent = available ? ((point.value! + 1) / 2) * 100 : 50
  const label = available ? point.label : 'Evaluation unavailable'
  const whiteWinning = available && point.value! >= 0
  const scoreAtBottom = whiteWinning === (orientation === 'white')
  const compactScore = !available
    ? '—'
    : point.label.includes('checkmate')
      ? 'M0'
      : point.label.includes('mates in')
        ? `M${point.label.split(' ').at(-1)}`
        : Math.abs(Number(point.label)).toFixed(1)

  return (
    <div className={`evaluation-bar ${available ? '' : 'evaluation-bar-unavailable'}`}
      role="img" aria-label={`Position evaluation: ${label}`} title={label}>
      {available && (
        <div className="evaluation-bar-white" style={{
          height: `${whitePercent}%`,
          ...(orientation === 'white' ? { bottom: 0 } : { top: 0 }),
        }} />
      )}
      <span className="evaluation-bar-midpoint" />
      <span className="evaluation-bar-score" style={{
        ...(scoreAtBottom ? { bottom: 6 } : { top: 6 }),
        color: available && whiteWinning ? '#18181b' : '#fff',
      }}>{compactScore}</span>
    </div>
  )
}
