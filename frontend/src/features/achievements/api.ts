import { getJson } from '../../shared/api/http'

export type Card = { key: string; name: string; description: string; earned_at: string | null }
type Profile = { score: number; total: number; rank: number | null; locale: string; theme: string; ui: Record<string, string>; achievements: Card[] }
type Entry = { full_name: string; score: number; rank: number; is_self: boolean; achievements: Card[] }

export async function getAchievements(initData: string) {
  const [profile, leaderboard] = await Promise.all([
    getJson('gamification/me', initData) as Promise<Profile>,
    getJson('gamification/leaderboard', initData) as Promise<{ entries: Entry[] }>,
  ])
  return { profile, entries: leaderboard.entries }
}
