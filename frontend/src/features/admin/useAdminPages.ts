import { onScopeDispose, ref, shallowRef, watch, type Ref } from 'vue'
import { HttpError } from '../../shared/api/http'

type Status = 'open_telegram' | 'loading' | 'ready' | 'session_expired' | 'denied' | 'error'
type Page<T> = { items: T[]; nextCursor: string | null }

export function useAdminPages<T>(
  rawInitData: Readonly<Ref<string | undefined>>,
  read: (initData: string, cursor: string | null, signal: AbortSignal) => Promise<Page<T>>,
  resourceKey: Readonly<Ref<string>> = ref(''),
) {
  const status = ref<Status>('open_telegram')
  const items = shallowRef<T[]>([])
  const nextCursor = ref<string | null>(null)
  let active: AbortController | undefined

  async function load(more = false) {
    const initData = rawInitData.value
    if (!initData || active || (more && nextCursor.value === null)) return
    const request = new AbortController()
    active = request
    status.value = 'loading'
    try {
      const page = await read(initData, more ? nextCursor.value : null, request.signal)
      if (request.signal.aborted) return
      items.value = more ? [...items.value, ...page.items] : page.items
      nextCursor.value = page.nextCursor
      status.value = 'ready'
    } catch (error) {
      if (request.signal.aborted) return
      if (error instanceof HttpError && error.unauthorized) {
        items.value = []
        nextCursor.value = null
        status.value = error.status === 403 ? 'denied' : 'session_expired'
      } else {
        status.value = 'error'
      }
    } finally {
      if (active === request) active = undefined
    }
  }

  watch([rawInitData, resourceKey], ([initData]) => {
    active?.abort()
    active = undefined
    items.value = []
    nextCursor.value = null
    status.value = 'open_telegram'
    if (initData) void load()
  }, { immediate: true })
  onScopeDispose(() => active?.abort())

  return { status, items, nextCursor, refresh: () => load(), loadMore: () => load(true) }
}
