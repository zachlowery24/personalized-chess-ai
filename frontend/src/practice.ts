export interface PracticePosition {
  game_id: number
  analysis_id: number
  ply: number
  color: 'white' | 'black'
  fen: string
  engine_name: string
  requested_depth: number
}

export interface PracticeQueue {
  player_id: number
  positions: PracticePosition[]
  analyzed_game_count: number
}

export interface PracticeReveal extends PracticePosition {
  played_move: string
  recommended_move: string
  centipawn_loss: number
}

export async function getPracticeQueue(
  playerId: number,
  signal?: AbortSignal,
): Promise<PracticeQueue> {
  const response = await fetch(
    `/api/players/${playerId}/practice?limit=3`,
    { signal },
  )

  if (!response.ok) {
    throw new Error('Could not load practice positions.')
  }

  return response.json()
}

export async function revealPracticePosition(
  playerId: number,
  position: PracticePosition,
  signal?: AbortSignal,
): Promise<PracticeReveal> {
  const response = await fetch(
    `/api/players/${playerId}/practice/${position.analysis_id}/${position.ply}/reveal`,
    { signal },
  )

  if (!response.ok) {
    throw new Error('Could not reveal this position. Please try again.')
  }

  return response.json()
}