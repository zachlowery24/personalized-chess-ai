import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import './App.css'
import { getPlayerByUsername } from './players'
import type { PlayerProfile } from './players'
import type { SavedGame } from './games'
import { formatGameResult, getPlayerGames } from './games'
import GameReplay from './GameReplay'
import { getLatestAnalysisRun } from './analyses'
import PracticeQueue from './PracticeQueue'



function App() {
  const [username, setUsername] = useState('')
  const [player, setPlayer] = useState<PlayerProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [games, setGames] = useState<SavedGame[]>([])
  const [selectedGame, setSelectedGame] = useState<SavedGame | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const replayWorkspace = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<'games' | 'practice'>('games')

  useEffect(() => {
    if (selectedGame) {
      replayWorkspace.current?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'start',
      })
    }
  }, [selectedGame])

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()

    await loadPlayer(username)
  }

  async function loadPlayer(name: string, demo = false) {
    const normalizedUsername = name.trim().toLowerCase()

    if (!normalizedUsername || loading) {
      return
    }

    setLoading(true)
    setDemoLoading(demo)
    setNotice(null)
    setError(null)
    setPlayer(null)
    setGames([])
    setSelectedGame(null)
    setView('games')

    try {
      const foundPlayer = await getPlayerByUsername(normalizedUsername)
      const savedGames = await getPlayerGames(foundPlayer.id)

      setPlayer(foundPlayer)
      setGames(savedGames)

      if (demo) {
        let choice = savedGames[0] ?? null
        let foundAnalysis = false
        try {
          // Check metadata only; the replay loads the selected run's full results.
          for (const game of savedGames) {
            if (await getLatestAnalysisRun(game.id)) {
              choice = game
              foundAnalysis = true
              break
            }
          }
          if (!savedGames.length) setNotice('No saved demo games are available yet.')
          else if (!foundAnalysis) setNotice('Replay is ready. No saved analysis is available for these games yet.')
        } catch {
          setNotice('Replay is available, but saved analysis could not be checked. Please try again later.')
        }
        setSelectedGame(choice)
      }

    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setLoading(false)
      setDemoLoading(false)
    }
  }

  return (
    <main>
      <header className="app-heading"><h1>ChessDNA</h1><span className="brand-tag">A chess study notebook</span></header>
      <p>Replay your games. Compare your decisions with Stockfish.</p>
      <div className="demo-entry">
        <button type="button" disabled={loading} onClick={() => {
          setUsername('cashmoneylow')
          void loadPlayer('cashmoneylow', true)
        }}>
          {demoLoading ? 'Opening demo…' : 'Try demo'}
        </button>
        <p>Open a saved game with move-by-move analysis. No account needed.</p>
      </div>

      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Find a saved Chess.com player</label>

        <input
          id="username"
          name="username"
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="cashmoneylow"
          maxLength={255}
          disabled={loading}
          required
        />



        <button type="submit" disabled={loading || !username.trim()}>
          {loading ? 'Finding player…' : 'Find player'}
        </button>
      </form>

      {loading && <p role="status">Loading player and games…</p>}

      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      {player && (
        <section aria-label="Player details" className="player-section">
          <h2>{player.username}</h2>

          <p className="player-meta">{player.source} · {games.length} recent saved games</p>


          <div role="group" aria-label="Player view">
            <button
              type="button"
              aria-pressed={view === 'games'}
              onClick={() => setView('games')}
            >
              Games
            </button>
            <button
              type="button"
              aria-pressed={view === 'practice'}
              onClick={() => setView('practice')}
            >
              Practice
            </button>
          </div>

          {view === 'games' && (
            <>

              <h3>Recent saved games</h3>

              {games.length === 0 ? (
                <p>No saved games found.</p>
              ) : (
                <div className="games-table-scroll">
                  <table className="games-table">
                    <caption className="sr-only">Recent saved games for {player.username}</caption>
                    <thead><tr>
                      <th scope="col">Format</th><th scope="col">Played</th>
                      <th scope="col">Your side</th><th scope="col">Result</th>
                      <th scope="col">Review</th><th scope="col">Source</th>
                    </tr></thead>
                    <tbody>
                      {games.map((game) => {
                        const color = game.white_player_id === player.id ? 'white' : 'black'
                        const result = formatGameResult(game, player.id)
                        const outcome = result.startsWith('Win') ? 'win' : result.startsWith('Loss') ? 'loss' : 'neutral'
                        const selected = selectedGame?.id === game.id
                        return (
                          <tr key={game.id} className={selected ? 'game-selected' : undefined}>
                            <td><span className="time-class">{game.time_class}</span></td>
                            <td><time dateTime={game.ended_at}>
                              {new Date(game.ended_at).toLocaleDateString()}
                              <span className="game-time">{new Date(game.ended_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
                            </time></td>
                            <td><span className={`side-icon side-${color}`} role="img" aria-label={`Played as ${color}`} title={`Played as ${color}`}>♚</span></td>
                            <td><span className={`result-badge result-${outcome}`}>{result}</span></td>
                            <td><button type="button" aria-pressed={selected} onClick={() => setSelectedGame(game)}>
                              {selected ? 'Reviewing' : 'Review game'}
                            </button></td>
                            <td><a href={game.source_url} target="_blank" rel="noopener noreferrer" aria-label={`View game ${game.id} on Chess.com`}>Chess.com ↗</a></td>
                          </tr>
                        )
                      })}

                    </tbody>
                  </table>
                </div>

              )}

              {selectedGame && (
                <div ref={replayWorkspace} className="replay-workspace">
                  <GameReplay
                    key={selectedGame.id}
                    gameId={selectedGame.id}
                    orientation={
                      selectedGame.white_player_id === player.id ? 'white' : 'black'
                    }
                  />
                </div>
              )}
            </>
          )}

          {view === 'practice' && (
            <PracticeQueue key={player.id} playerId={player.id} />
          )}

        </section>
      )
      }

    </main >
  )
}

export default App
