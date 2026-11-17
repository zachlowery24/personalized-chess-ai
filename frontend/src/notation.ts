import { Chess } from 'chess.js'

export function formatEngineMove(fen: string, uci: string | null): string {
  if (!uci) return 'None'

  try {
    const board = new Chess(fen)
    const move = board.move({
      from: uci.slice(0, 2),
      to: uci.slice(2, 4),
      promotion: uci.length === 5 ? uci[4] : undefined,
    })
    return move.san
  } catch {
    return 'Recommendation unavailable'
  }
}
