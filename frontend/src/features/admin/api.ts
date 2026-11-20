import { getJson, isRecord } from '../../shared/api/http'

type UserProfile = {
  id: string
  full_name: string
  username: string | null
}

function isUserProfile(value: unknown): value is UserProfile {
  return isRecord(value) && typeof value.id === 'string' && typeof value.full_name === 'string'
    && (value.username === null || typeof value.username === 'string')
}

export async function getUsers(initData: string, cursor: string | null, signal: AbortSignal) {
  const query = cursor === null ? '' : '?' + new URLSearchParams({ after: cursor })
  const data = await getJson('admin/users' + query, initData, signal)
  if (!isRecord(data) || !Array.isArray(data.users) || !data.users.every(isUserProfile)
    || (data.next_cursor !== null && typeof data.next_cursor !== 'string')) {
    throw new Error('Invalid user list')
  }
  return { users: data.users, nextCursor: data.next_cursor }
}
