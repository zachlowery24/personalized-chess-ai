export interface SavedGame {
  id: number
  source: string
  source_url: string
  white_player_id: number
  black_player_id: number
  white_result: string
  black_result: string
  time_class: string
  rules: 'chess'
  ended_at: string
  pgn: string
  created_at: string
}

export async function getPlayerGames(
  playerId: number,
): Promise<SavedGame[]> {
  const params = new URLSearchParams({
    limit: '20',
    offset: '0',
  })

  const response = await fetch(
    `/api/players/${playerId}/games?${params}`,
  )

  if (!response.ok) {
    throw new Error('Could not load saved games. Please try again.')
  }

  return response.json()
}



export function formatGameResult(
  game: SavedGame,
  playerId: number,
): string {
  const isWhite = game.white_player_id === playerId
  const playerResult = isWhite ? game.white_result : game.black_result
  const opponentResult = isWhite ? game.black_result : game.white_result

  const lossReasons: Record<string, string> = {
    checkmated: 'checkmate',
    resigned: 'resignation',
    timeout: 'timeout',
    abandoned: 'abandonment',
    lose: 'loss',
  }

  const drawReasons: Record<string, string> = {
    agreed: 'agreement',
    repetition: 'repetition',
    stalemate: 'stalemate',
    insufficient: 'insufficient material',
    '50move': '50-move rule',
    timevsinsufficient: 'timeout vs. insufficient material',
  }

  if (playerResult === 'win') {
    const reason = lossReasons[opponentResult]
    return reason ? `Win (${reason})` : 'Win'
  }

  const drawReason = drawReasons[playerResult]

  if (drawReason) {
    return `Draw (${drawReason})`
  }

  const lossReason = lossReasons[playerResult]

  if (lossReason) {
    return `Loss (${lossReason})`
  }

  return `Unknown result (${playerResult})`
}


export interface MoveRecord {
  ply: number
  color: 'white' | 'black'
  uci: string
  san: string
  fen_before: string
  fen_after: string
}

export interface GameReplay {
  game_id: number
  moves: MoveRecord[]
}

export async function getGameMoves(
  gameId: number,
  signal?: AbortSignal,
): Promise<GameReplay> {
  const response = await fetch(`/api/games/${gameId}/moves`, { signal })

  if (!response.ok) {
    throw new Error('Could not load this game’s moves.')
  }

  return response.json()
}

