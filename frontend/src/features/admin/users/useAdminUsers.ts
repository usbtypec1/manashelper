import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { HttpError } from '../../../shared/api/http'
import { getUsers, type UserFilters } from './api'

type Status = 'open_telegram' | 'loading' | 'ready' | 'session_expired' | 'denied' | 'error'
type ReadMode = 'more' | 'refresh'

export function useAdminUsers(rawInitData: Readonly<Ref<string | undefined>>, filters: Readonly<Ref<UserFilters>>) {
  const status = ref<Status>('open_telegram')
  const users = ref<Awaited<ReturnType<typeof getUsers>>['users']>([])
  const nextCursor = ref<string | null>(null)
  const pending = ref<ReadMode | null>(null)
  let active: AbortController | undefined
  let lastMode: ReadMode = 'refresh'

  async function load(mode: ReadMode) {
    const initData = rawInitData.value
    if (!initData || active) return
    const request = new AbortController()
    active = request
    pending.value = mode
    lastMode = mode
    status.value = 'loading'
    try {
      const page = await getUsers(initData, mode === 'more' ? nextCursor.value : null, filters.value, request.signal)
      if (request.signal.aborted) return
      if (mode === 'more') users.value.push(...page.users)
      else users.value = page.users
      nextCursor.value = page.nextCursor
      status.value = 'ready'
    } catch (error) {
      if (request.signal.aborted) return
      if (error instanceof HttpError && error.unauthorized) {
        users.value = []
        nextCursor.value = null
        status.value = error.status === 403 ? 'denied' : 'session_expired'
      } else {
        status.value = 'error'
      }
    } finally {
      if (active === request) {
        active = undefined
        pending.value = null
      }
    }
  }

  watch([rawInitData, filters], ([initData], [previousInitData], onCleanup) => {
    active?.abort()
    active = undefined
    pending.value = null
    users.value = []
    nextCursor.value = null
    status.value = initData ? 'loading' : 'open_telegram'
    if (!initData) return
    if (initData !== previousInitData) {
      void load('refresh')
    } else {
      const timer = setTimeout(() => void load('refresh'), 200)
      onCleanup(() => clearTimeout(timer))
    }
  }, { immediate: true })
  onScopeDispose(() => active?.abort())

  return {
    status, users, nextCursor, pending,
    loadMore: () => load('more'),
    refresh: () => load('refresh'),
    retry: () => load(lastMode),
  }
}
