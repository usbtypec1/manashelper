import { onScopeDispose, ref, shallowRef, type Ref } from 'vue'
import { HttpError } from '../../shared/api/http'
import {
  loadCourses, loadDepartments, loadFaculties, loadFreeTime, loadProfile,
  type CatalogCourse, type CatalogItem, type FreeTime, type Profile,
} from './api'

export type FreeTimeStatus = 'loading' | 'ready' | 'expired' | 'error'

/** Loads the viewer's profile and catalog, and compares the courses selected by the page. */
export function useFreeTime(rawInitData: Readonly<Ref<string | undefined>>) {
  const status = ref<FreeTimeStatus>('loading')
  const profile = shallowRef<Profile>()
  const faculties = shallowRef<CatalogItem[]>([])
  const departments = shallowRef<CatalogItem[]>([])
  const courses = shallowRef<CatalogCourse[]>([])
  const faculty = ref('')
  const department = ref('')
  const result = shallowRef<FreeTime>()
  const comparing = ref(false)
  const catalogBusy = ref(false)
  const failed = ref(false)
  let comparison: AbortController | undefined
  let catalog: AbortController | undefined

  function fail(error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    if (error instanceof HttpError && error.unauthorized) status.value = 'expired'
    else failed.value = true
  }

  async function load() {
    const initData = rawInitData.value
    if (!initData) return
    status.value = 'loading'
    failed.value = false
    try {
      const [loadedProfile, loadedFaculties] = await Promise.all([loadProfile(initData), loadFaculties(initData)])
      profile.value = loadedProfile
      faculties.value = loadedFaculties
      status.value = 'ready'
    } catch (error) {
      fail(error)
      if (status.value === 'loading') status.value = 'error'
    }
  }

  async function compare(courseIds: readonly number[]) {
    comparison?.abort()
    const initData = rawInitData.value
    if (!initData || !courseIds.length) {
      comparison = undefined
      result.value = undefined
      comparing.value = false
      return
    }
    const controller = new AbortController()
    comparison = controller
    comparing.value = true
    failed.value = false
    try {
      const loaded = await loadFreeTime(initData, courseIds, controller.signal)
      if (comparison === controller) result.value = loaded
    } catch (error) {
      if (comparison === controller) fail(error)
    } finally {
      if (comparison === controller) comparing.value = false
    }
  }

  async function catalogRequest<T>(request: (initData: string, signal: AbortSignal) => Promise<T>): Promise<T | undefined> {
    catalog?.abort()
    const initData = rawInitData.value
    if (!initData) return undefined
    const controller = new AbortController()
    catalog = controller
    catalogBusy.value = true
    failed.value = false
    try {
      const loaded = await request(initData, controller.signal)
      return catalog === controller ? loaded : undefined
    } catch (error) {
      if (catalog === controller) fail(error)
      return undefined
    } finally {
      if (catalog === controller) catalogBusy.value = false
    }
  }

  async function selectFaculty(id: string) {
    faculty.value = id
    department.value = ''
    departments.value = []
    courses.value = []
    if (!id) { catalog?.abort(); catalogBusy.value = false; return }
    const loaded = await catalogRequest((initData, signal) => loadDepartments(initData, id, signal))
    if (loaded && faculty.value === id) departments.value = loaded
  }

  async function selectDepartment(id: string) {
    department.value = id
    courses.value = []
    if (!id) { catalog?.abort(); catalogBusy.value = false; return }
    const loaded = await catalogRequest((initData, signal) => loadCourses(initData, id, signal))
    if (loaded && department.value === id) courses.value = loaded
  }

  onScopeDispose(() => { comparison?.abort(); catalog?.abort() })

  return {
    status, profile, faculties, departments, courses, faculty, department, result, comparing, catalogBusy, failed,
    load, compare, selectFaculty, selectDepartment,
  }
}
