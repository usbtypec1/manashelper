import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { HttpError } from '../../../shared/api/http'
import {
  getAchievements, grantAchievement, revokeAchievement, setAchievementDisplay,
  type AchievementDisplay, type AdminAchievement,
} from './api'

type Status = 'open_telegram' | 'loading' | 'ready' | 'denied' | 'session_expired' | 'error'
type Notice = 'saved' | 'granted' | 'already_granted' | 'revoked' | 'not_awarded' | 'missing' | 'unavailable' | 'error'
type AwardAction = 'grant' | 'revoke'
type Operation = 'save' | AwardAction

export function useAdminAchievements(rawInitData: Readonly<Ref<string | undefined>>) {
  const status = ref<Status>('open_telegram')
  const achievements = ref<AdminAchievement[]>([])
  const pending = ref<Operation | null>(null)
  const notice = ref<Notice | null>(null)
  let read: AbortController | undefined
  let disposed = false

  function handleDenied(error: unknown) {
    if (!(error instanceof HttpError) || !error.unauthorized) return false
    achievements.value = []
    status.value = error.status === 403 ? 'denied' : 'session_expired'
    return true
  }

  async function load() {
    read?.abort()
    const initData = rawInitData.value
    achievements.value = []
    notice.value = null
    status.value = initData ? 'loading' : 'open_telegram'
    if (!initData) return
    const request = new AbortController()
    read = request
    try {
      const result = await getAchievements(initData, request.signal)
      if (request.signal.aborted) return
      achievements.value = result
      status.value = 'ready'
    } catch (error) {
      if (!request.signal.aborted && !handleDenied(error)) status.value = 'error'
    } finally {
      if (read === request) read = undefined
    }
  }

  async function mutate(
    operation: Operation, perform: (initData: string) => Promise<() => Notice>,
  ) {
    const initData = rawInitData.value
    if (!initData || pending.value || status.value !== 'ready') return
    pending.value = operation
    notice.value = null
    try {
      const apply = await perform(initData)
      if (!disposed && rawInitData.value === initData) notice.value = apply()
    } catch (error) {
      if (disposed || rawInitData.value !== initData || handleDenied(error)) return
      if (operation !== 'save' && error instanceof HttpError && error.status === 404) notice.value = 'missing'
      else if (operation === 'grant' && error instanceof HttpError && error.status === 409) notice.value = 'unavailable'
      else notice.value = 'error'
    } finally {
      pending.value = null
    }
  }

  function save(key: string, display: AchievementDisplay) {
    return mutate('save', async initData => {
      const result = await setAchievementDisplay(initData, key, display)
      return () => {
        const item = achievements.value.find(entry => entry.key === key)
        if (item) Object.assign(item, result)
        return 'saved'
      }
    })
  }

  function changeAward(action: AwardAction, key: string, userId: string) {
    const change = action === 'grant' ? grantAchievement : revokeAchievement
    return mutate(action, async initData => {
      const result = await change(initData, key, userId)
      return () => result
    })
  }

  watch(rawInitData, load, { immediate: true })
  onScopeDispose(() => {
    disposed = true
    read?.abort()
  })
  return { status, achievements, notice, pending, load, save, changeAward }
}
