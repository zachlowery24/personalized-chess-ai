import { useEffect, useState } from 'react'
import { getPracticeQueue } from './practice'
import type { PracticeQueue as QueueData } from './practice'
import PracticeExercise from './PracticeExercise'

interface Props {
  playerId: number
}

export default function PracticeQueue({ playerId }: Props) {
  const [queue, setQueue] = useState<QueueData | null>(null)
  const [index, setIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const result = await getPracticeQueue(playerId, controller.signal)

        if (!controller.signal.aborted) {
          setQueue(result)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setError(
            error instanceof Error
              ? error.message
              : 'Could not load practice positions.',
          )
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [playerId])

  if (error) return <p role="alert">{error}</p>
  if (!queue) return <p role="status">Finding practice positions…</p>

  const position = queue.positions[index]

  return (
    <section aria-label="Personal practice">
      <h3>Your practice positions</h3>
      <p>
        Selected from {queue.analyzed_game_count} analyzed{' '}
        {queue.analyzed_game_count === 1 ? 'game' : 'games'}.
        {' '}These are decisions from your games, not necessarily forced tactics.
      </p>

      {position ? (
        <>
          <div>
            <button
              type="button"
              disabled={index === 0}
              onClick={() => setIndex((current) => current - 1)}
            >
              Previous position
            </button>
            {' '}
            <span>Position {index + 1} of {queue.positions.length}</span>
            {' '}
            <button
              type="button"
              disabled={index === queue.positions.length - 1}
              onClick={() => setIndex((current) => current + 1)}
            >
              Next position
            </button>
          </div>

          <PracticeExercise
            key={`${position.analysis_id}-${position.ply}`}
            playerId={playerId}
            position={position}
          />
        </>
      ) : (
        <p>
          {queue.analyzed_game_count === 0
            ? 'Analyze a saved game first to generate practice positions.'
            : 'No eligible practice positions were found in the saved analyses.'}
        </p>
      )}
    </section>
  )
}