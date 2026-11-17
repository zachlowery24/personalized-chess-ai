export interface AnalysisRun {
  analysis_id: number
  game_id: number
  engine_name: string
  requested_depth: number
  created_at: string
}

export interface PlayerAnalysisSummary {
  color: 'white' | 'black'
  total_moves: number
  scored_moves: number
  unscored_moves: number
  average_centipawn_loss: number | null
}

export interface AnalyzedMove {
  ply: number
  color: 'white' | 'black'
  uci: string
  san: string
  fen_before: string
  fen_after: string

  before_best_move: string | null
  before_score_cp: number | null
  before_mate_in: number | null
  before_depth: number | null

  after_best_move: string | null
  after_score_cp: number | null
  after_mate_in: number | null
  after_depth: number | null

  centipawn_loss: number | null
}

export interface SavedAnalysis extends AnalysisRun {
  moves: AnalyzedMove[]
  white_summary: PlayerAnalysisSummary
  black_summary: PlayerAnalysisSummary
}

export async function getLatestAnalysisRun(
  gameId: number,
  signal?: AbortSignal,
): Promise<AnalysisRun | null> {
  const listResponse = await fetch(
    `/api/games/${gameId}/analyses?limit=1&offset=0`,
    { signal },
  )

  if (!listResponse.ok) {
    throw new Error('Could not load saved analyses.')
  }

  const runs: AnalysisRun[] = await listResponse.json()
  return runs[0] ?? null
}

export async function getLatestGameAnalysis(
  gameId: number,
  signal?: AbortSignal,
): Promise<SavedAnalysis | null> {
  const latest = await getLatestAnalysisRun(gameId, signal)

  if (!latest) {
    return null
  }

  const response = await fetch(
    `/api/analyses/${latest.analysis_id}`,
    { signal },
  )

  if (!response.ok) {
    throw new Error('Could not load the saved analysis results.')
  }

  return response.json()
}
