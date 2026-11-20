import { getJson, isRecord } from '../../shared/api/http'

export type UserProfile = {
  id: string
  full_name: string
  username: string | null
  locale: string
  theme: string
  bot_stopped: boolean
}

export type UserFilters = {
  q?: string
  locale?: string
  theme?: string
  status?: string
}

function isUserProfile(value: unknown): value is UserProfile {
  return isRecord(value) && typeof value.id === 'string' && typeof value.full_name === 'string'
    && (value.username === null || typeof value.username === 'string')
    && typeof value.locale === 'string' && typeof value.theme === 'string' && typeof value.bot_stopped === 'boolean'
}

export async function getUsers(initData: string, cursor: string | null, filters: UserFilters, signal: AbortSignal) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value)
  }
  if (cursor !== null) params.set('after', cursor)
  const data = await getJson('admin/users?' + params, initData, signal)
  if (!isRecord(data) || !Array.isArray(data.users) || !data.users.every(isUserProfile)
    || (data.next_cursor !== null && typeof data.next_cursor !== 'string')) {
    throw new Error('Invalid user list')
  }
  return { users: data.users, nextCursor: data.next_cursor }
}
