import { useState } from 'react'
import { Chess } from 'chess.js'
import { Chessboard } from 'react-chessboard'
import { revealPracticePosition } from './practice'
import type { PracticePosition, PracticeReveal } from './practice'
import { formatEngineMove } from './notation'

interface Props {
  playerId: number
  position: PracticePosition
}

interface Attempt {
  uci: string
  san: string
  fen: string
}

export default function PracticeExercise({ playerId, position }: Props) {
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [answer, setAnswer] = useState<PracticeReveal | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [promotion, setPromotion] = useState('q')

  function tryMove(sourceSquare: string, targetSquare: string | null) {
    if (!targetSquare || attempt || answer || loading) return false

    try {
      const board = new Chess(position.fen)
      const move = board.move({
        from: sourceSquare,
        to: targetSquare,
        promotion,
      })

      setAttempt({
        uci: `${move.from}${move.to}${move.promotion ?? ''}`,
        san: move.san,
        fen: board.fen(),
      })
      setError(null)
      return true
    } catch {
      setError('That move is not legal in this position.')
      return false
    }
  }

  async function reveal() {
    if (loading || answer) return

    setLoading(true)
    setError(null)

    try {
      setAnswer(await revealPracticePosition(playerId, position))
    } catch (error) {
      setError(
        error instanceof Error ? error.message : 'Could not load the answer.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-label="Practice position">
      <h3>{position.color === 'white' ? 'White' : 'Black'} to move</h3>
      <p>Try a move, then compare it with the saved engine recommendation.</p>

      <div style={{ maxWidth: 480 }}>
        <Chessboard
          options={{
            position: attempt?.fen ?? position.fen,
            boardOrientation: position.color,
            allowDragging: !attempt && !answer && !loading,
            lightSquareStyle: { backgroundColor: '#e9e1cf' },
            darkSquareStyle: { backgroundColor: '#788568' },
            onPieceDrop: ({ sourceSquare, targetSquare }) =>
              tryMove(sourceSquare, targetSquare),
          }}
        />
      </div>

      {!attempt && !answer && (
        <label>
          Promote a pawn to:{' '}
          <select
            value={promotion}
            disabled={loading}
            onChange={(event) => setPromotion(event.target.value)}
          >
            <option value="q">Queen</option>
            <option value="r">Rook</option>
            <option value="b">Bishop</option>
            <option value="n">Knight</option>
          </select>
        </label>
      )}

      {attempt && <p>Your attempt: <strong>{attempt.san}</strong></p>}

      <div>
        {attempt && !answer && (
          <button
            type="button"
            disabled={loading}
            onClick={() => {
              setAttempt(null)
              setError(null)
            }}
          >
            Reset position
          </button>
        )}
        {!answer && (
          <button type="button" disabled={loading} onClick={reveal}>
            {loading ? 'Loading recommendation…' : 'Reveal recommendation'}
          </button>
        )}
      </div>

      {error && <p role="alert">{error}</p>}

      {answer && (
        <div aria-live="polite">
          <p>
            Engine recommendation:{' '}
            <strong>
              {formatEngineMove(answer.fen, answer.recommended_move)}
            </strong>
          </p>
          <p>
            Originally played:{' '}
            {formatEngineMove(answer.fen, answer.played_move)}
            {' — '}
            estimated loss: {answer.centipawn_loss} centipawns.
          </p>
          {attempt && (
            <p>
              {attempt.uci === answer.recommended_move
                ? 'Your move matches the saved engine recommendation.'
                : 'Your move differs from the saved recommendation. Other good moves may exist; your attempt has not been evaluated.'}
            </p>
          )}
          <p>{answer.engine_name} · Depth {answer.requested_depth}</p>
        </div>
      )}
    </section>
  )
}