import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Chessboard } from 'react-chessboard'
import { getGameMoves } from './games'
import type { GameReplay as GameReplayData } from './games'
import './GameReplay.css'
import AnalysisPanel from './AnalysisPanel'
import EvaluationBar from './EvaluationBar'
import EvaluationGraph from './EvaluationGraph'
import { getLatestGameAnalysis } from './analyses'
import type { SavedAnalysis } from './analyses'



interface Props {
  gameId: number
  orientation: 'white' | 'black'
}

export default function GameReplay({ gameId, orientation }: Props) {
  const [replay, setReplay] = useState<GameReplayData | null>(null)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const moveList = useRef<HTMLDivElement>(null)
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(true)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const result = await getLatestGameAnalysis(gameId, controller.signal)
        if (!controller.signal.aborted) setAnalysis(result)
      } catch (error) {
        if (!controller.signal.aborted) {
          setAnalysisError(error instanceof Error ? error.message : 'Could not load analysis.')
        }
      } finally {
        if (!controller.signal.aborted) setAnalysisLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [gameId])

  useEffect(() => {
    if (!replay?.moves.length) return

    function handleKey(event: KeyboardEvent) {
      const target = event.target
      if (
        event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
        (target instanceof HTMLElement &&
          (target.isContentEditable || target.closest('input, textarea, select, [role="textbox"]')))
      ) return

      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const direction = event.key === 'ArrowRight' ? 1 : -1
        setStep((current) => Math.max(0, Math.min(replay!.moves.length, current + direction)))
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [replay])

  useEffect(() => {
    const list = moveList.current
    const active = list?.querySelector<HTMLElement>('[aria-current="step"]')
    if (!list || !active) return
    const listRect = list.getBoundingClientRect()
    const activeRect = active.getBoundingClientRect()
    if (activeRect.top < listRect.top) list.scrollTop -= listRect.top - activeRect.top
    else if (activeRect.bottom > listRect.bottom) list.scrollTop += activeRect.bottom - listRect.bottom
  }, [step])

  useEffect(() => {
    const controller = new AbortController()

    async function loadMoves() {
      try {
        const result = await getGameMoves(gameId, controller.signal)

        if (!controller.signal.aborted) {
          setReplay(result)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setError(
            error instanceof Error ? error.message : 'Could not load replay.',
          )
        }
      }
    }

    void loadMoves()

    return () => controller.abort()
  }, [gameId])

  if (error) {
    return <p role="alert">{error}</p>
  }

  if (!replay) {
    return <p role="status">Loading replay…</p>
  }

  if (replay.moves.length === 0) {
    return <p>This game has no moves to replay.</p>
  }

  const position =
    step === 0
      ? replay.moves[0]!.fen_before
      : replay.moves[step - 1]!.fen_after
  const selectedMove = step > 0 ? replay.moves[step - 1] : undefined
  const squareStyles: Record<string, CSSProperties> = {}
  if (selectedMove) {
    squareStyles[selectedMove.uci.slice(0, 2)] = {
      backgroundColor: 'rgba(250, 204, 21, 0.5)',
    }
    squareStyles[selectedMove.uci.slice(2, 4)] = {
      backgroundColor: 'rgba(250, 204, 21, 0.7)',
    }
  }

  // FEN supplies the real move number, including custom Black-to-move starts.
  const rows: { number: string; white?: number; black?: number }[] = []
  replay.moves.forEach((move, index) => {
    const number = move.fen_before.split(' ')[5] ?? '1'
    let row = rows[rows.length - 1]
    if (!row || row.number !== number) {
      row = { number }
      rows.push(row)
    }
    row[move.color] = index
  })

  return (
    <section aria-label="Game replay" className="game-replay">
      <h2>Game replay</h2>
      <p>Use ← and → to navigate, or select a move.</p>
      <div className="replay-layout">
      <div className="replay-board">
        <div className="replay-board-with-eval">
        <EvaluationBar analysis={analysis} ply={step} orientation={orientation} />
        <div className="replay-board-surface">
        <Chessboard
          options={{
            position,
            boardOrientation: orientation,
            allowDragging: false,
            lightSquareStyle: { backgroundColor: '#e9e1cf' },
            darkSquareStyle: { backgroundColor: '#788568' },
            squareStyles,
          }}
        />
        </div>
        </div>
      <p aria-live="polite">
        {step === 0
          ? 'Starting position'
          : `${replay.moves[step - 1]!.color}: ${replay.moves[step - 1]!.san}`}
      </p>

      {analysis && <EvaluationGraph analysis={analysis} selectedPly={step} onSelectPly={setStep} />}
      <div className="replay-controls">
        <button onClick={() => setStep(0)} disabled={step === 0}>
          Start
        </button>
        <button
          onClick={() => setStep((current) => current - 1)}
          disabled={step === 0}
        >
          Previous
        </button>
        <button
          onClick={() => setStep((current) => current + 1)}
          disabled={step === replay.moves.length}
        >
          Next
        </button>
        <button
          onClick={() => setStep(replay.moves.length)}
          disabled={step === replay.moves.length}
        >
          End
        </button>
      </div>
      </div>
      <div className="replay-sidebar">
      <div className="replay-analysis">
        <AnalysisPanel analysis={analysis} loading={analysisLoading} error={analysisError} ply={step} />
      </div>
      <aside className="replay-moves" aria-label="Move list">
        <h3>Moves</h3>
        <div className="replay-move-header"><span>Move</span><span>White</span><span>Black</span></div>
        <div className="replay-move-scroll" ref={moveList}>
          {rows.map((row) => (
            <div className="replay-move-row" key={row.number}>
              <span>{row.number}.</span>
              {(['white', 'black'] as const).map((color) => {
                const index = row[color]
                if (index === undefined) return <span key={color}>—</span>
                const move = replay.moves[index]!
                return (
                  <button
                    key={color}
                    type="button"
                    aria-label={`Move ${row.number}, ${color}: ${move.san}`}
                    aria-current={step === index + 1 ? 'step' : undefined}
                    onClick={() => setStep(index + 1)}
                  >
                    {move.san}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </aside>
      </div>
      </div>
    </section>
  )
}
