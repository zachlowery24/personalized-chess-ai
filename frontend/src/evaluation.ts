import type { SavedAnalysis } from './analyses'

export interface EvaluationPoint {
  ply: number
  value: number | null
  label: string
}

function makePoint(
  ply: number,
  scoreCp: number | null,
  mateIn: number | null,
  fen: string,
): EvaluationPoint {
  if (mateIn !== null) {
    // At mate distance zero, the side to move has been checkmated.
    const whiteWinning =
      mateIn === 0
        ? fen.split(' ')[1] === 'b'
        : mateIn > 0

    return {
      ply,
      value: whiteWinning ? 1 : -1,
      label:
        mateIn === 0
          ? `${whiteWinning ? 'White' : 'Black'} wins by checkmate`
          : `${whiteWinning ? 'White' : 'Black'} mates in ${Math.abs(mateIn)}`,
    }
  }

  if (scoreCp === null) {
    return { ply, value: null, label: 'Evaluation unavailable' }
  }

  const pawns = scoreCp / 100

  return {
    ply,
    value: Math.tanh(scoreCp / 400),
    label: `${pawns > 0 ? '+' : ''}${pawns.toFixed(2)}`,
  }
}

export function buildEvaluationPoints(
  analysis: SavedAnalysis,
): EvaluationPoint[] {
  const moves = [...analysis.moves].sort((a, b) => a.ply - b.ply)
  const first = moves[0]

  if (!first) return []

  return [
    makePoint(
      0,
      first.before_score_cp,
      first.before_mate_in,
      first.fen_before,
    ),
    ...moves.map((move) =>
      makePoint(
        move.ply,
        move.after_score_cp,
        move.after_mate_in,
        move.fen_after,
      ),
    ),
  ]
}