export interface PlayerProfile {
  id: number
  source: string
  username: string
  created_at: string
}

export async function getPlayerByUsername(
  username: string,
): Promise<PlayerProfile> {
  const params = new URLSearchParams({ username })

  const response = await fetch(`/api/players/lookup?${params}`)

  if (response.status === 404) {
    throw new Error('No saved player found. Import their games first.')
  }

  if (!response.ok) {
    throw new Error('Could not load the player. Please try again.')
  }

  return response.json()
}