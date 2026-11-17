import type { SavedAnalysis } from './analyses'
import { formatEngineMove } from './notation'

interface Props {
  analysis: SavedAnalysis | null
  loading: boolean
  error: string | null
  ply: number
}

function formatEvaluation(
  scoreCp: number | null,
  mateIn: number | null,
): string {
  if (mateIn !== null) {
    if (mateIn === 0) return 'Checkmate'

    const side = mateIn > 0 ? 'White' : 'Black'
    return `${side} mates in ${Math.abs(mateIn)}`
  }

  if (scoreCp === null) return 'Unavailable'

  const pawns = scoreCp / 100
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(2)}`
}

export default function AnalysisPanel({ analysis, loading, error, ply }: Props) {
  if (loading) return <p role="status">Loading saved analysis…</p>
  if (error) return <p role="alert">{error}</p>
  if (!analysis) return <p>No saved analysis available.</p>

  const move = analysis.moves.find(
    (record) => record.ply === (ply === 0 ? 1 : ply),
  )

  return (
    <section aria-label="Saved engine analysis" className="analysis-panel">
      <h3>Saved analysis</h3>
      <p>
        {analysis.engine_name} · Depth {analysis.requested_depth}
      </p>

      <details className="analysis-summary">
      <summary>Game summary · average centipawn loss</summary>
      <ul>
        {[analysis.white_summary, analysis.black_summary].map(
          (summary) => (
            <li key={summary.color}>
              {summary.color === 'white' ? 'White' : 'Black'}:{' '}
              {summary.average_centipawn_loss?.toFixed(1) ?? 'Unavailable'}
              {' — '}
              {summary.scored_moves} scored, {summary.unscored_moves} excluded
            </li>
          ),
        )}
      </ul>
      </details>

      {move ? (
        <>
          <h4>{ply === 0 ? 'Starting position' : `Played: ${move.san}`}</h4>

          <p>
            Evaluation (White’s perspective):{' '}
            {formatEvaluation(
              ply === 0 ? move.before_score_cp : move.after_score_cp,
              ply === 0 ? move.before_mate_in : move.after_mate_in,
            )}
          </p>

          <p>
            {ply === 0
              ? 'Recommended first move'
              : 'Engine recommendation before this move'}
            : {formatEngineMove(move.fen_before, move.before_best_move)}
          </p>

          {ply > 0 && (
            <p>
              Move loss:{' '}
              {move.centipawn_loss === null
                ? 'Unavailable for mate-score transitions'
                : `${move.centipawn_loss} centipawns`}
            </p>
          )}
        </>
      ) : (
        <p>No analysis record for this position.</p>
      )}
    </section>
  )
}
