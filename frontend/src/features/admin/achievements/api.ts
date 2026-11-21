import { getJson, isRecord, putJson } from '../../../shared/api/http'

export type AchievementDisplay = {
  custom_name: string | null
  hidden: boolean
}

export type AdminAchievement = AchievementDisplay & {
  key: string
  emoji: string
  default_name: string
}

function isDisplay(value: unknown): value is AchievementDisplay {
  return isRecord(value)
    && (value.custom_name === null || typeof value.custom_name === 'string')
    && typeof value.hidden === 'boolean'
}

function isAchievement(value: unknown): value is AdminAchievement {
  return isRecord(value) && typeof value.key === 'string' && typeof value.emoji === 'string'
    && typeof value.default_name === 'string' && isDisplay(value)
}

export async function getAchievements(initData: string, signal: AbortSignal): Promise<AdminAchievement[]> {
  const data = await getJson('admin/achievements', initData, signal)
  if (!isRecord(data) || !Array.isArray(data.achievements) || !data.achievements.every(isAchievement)) {
    throw new Error('Invalid achievement catalog')
  }
  return data.achievements
}

export async function setAchievementDisplay(initData: string, key: string, display: AchievementDisplay) {
  const data = await putJson(`admin/achievements/${encodeURIComponent(key)}`, initData, display)
  if (!isDisplay(data)) throw new Error('Invalid achievement display')
  return data
}

export async function grantAchievement(initData: string, key: string, userId: string) {
  const data = await putJson(
    `admin/achievements/${encodeURIComponent(key)}/grants/${encodeURIComponent(userId)}`, initData, undefined,
  )
  if (!isRecord(data) || (data.status !== 'granted' && data.status !== 'already_granted')) {
    throw new Error('Invalid achievement grant')
  }
  return data.status
}
