import { getJson, isRecord, isStringRecord } from '../../shared/api/http'

export type CourseLevel = 'bachelor' | 'master' | 'doctorate'
export type CatalogItem = { id: string; name: string }
export type CatalogCourse = { id: number; number: number; level: CourseLevel }
export type ComparedCourse = CatalogCourse & { department_name: string; faculty_name: string }
export type FreeWindow = { start: string; end: string; periods: number }
export type FreeDay = { weekday: number; windows: FreeWindow[] }
export type FreeTime = { maxCourses: number; courses: ComparedCourse[]; days: FreeDay[] }
export type Profile = {
  locale: string
  theme: string
  ui: Record<string, string>
  trackedCourseIds: number[]
}

const levels: readonly CourseLevel[] = ['bachelor', 'master', 'doctorate']

class InvalidResponseError extends Error {}

function invalid(): never { throw new InvalidResponseError('Unexpected Mini App API response') }

function asArray(value: unknown): unknown[] { return Array.isArray(value) ? value : invalid() }
function asNumber(value: unknown): number { return typeof value === 'number' && Number.isFinite(value) ? value : invalid() }
function asString(value: unknown): string { return typeof value === 'string' ? value : invalid() }
function asLevel(value: unknown): CourseLevel {
  return levels.find(level => level === value) ?? 'bachelor'
}

function catalogCourse(value: unknown): CatalogCourse {
  if (!isRecord(value)) invalid()
  return { id: asNumber(value.id), number: asNumber(value.number), level: asLevel(value.level) }
}

export async function loadProfile(rawInitData: string): Promise<Profile> {
  const data = await getJson('settings', rawInitData)
  if (!isRecord(data) || !isStringRecord(data.ui)) invalid()
  return {
    locale: asString(data.locale),
    theme: asString(data.theme),
    ui: data.ui,
    trackedCourseIds: asArray(data.tracked_courses).map(course => catalogCourse(course).id),
  }
}

export async function loadFaculties(rawInitData: string): Promise<CatalogItem[]> {
  return catalogItems(await getJson('studies/faculties', rawInitData), 'faculties')
}

export async function loadDepartments(rawInitData: string, facultyId: string, signal: AbortSignal): Promise<CatalogItem[]> {
  const query = new URLSearchParams({ faculty_id: facultyId })
  return catalogItems(await getJson(`studies/departments?${query}`, rawInitData, signal), 'departments')
}

export async function loadCourses(rawInitData: string, departmentId: string, signal: AbortSignal): Promise<CatalogCourse[]> {
  const query = new URLSearchParams({ department_id: departmentId })
  const data = await getJson(`studies/courses?${query}`, rawInitData, signal)
  if (!isRecord(data)) invalid()
  return asArray(data.courses).map(catalogCourse)
}

export async function loadFreeTime(rawInitData: string, courseIds: readonly number[], signal: AbortSignal): Promise<FreeTime> {
  const query = new URLSearchParams({ course_ids: courseIds.join(',') })
  const data = await getJson(`studies/free-time?${query}`, rawInitData, signal)
  if (!isRecord(data)) invalid()
  return {
    maxCourses: asNumber(data.max_courses),
    courses: asArray(data.courses).map(value => {
      if (!isRecord(value)) invalid()
      return {
        ...catalogCourse(value),
        department_name: asString(value.department_name),
        faculty_name: asString(value.faculty_name),
      }
    }),
    days: asArray(data.days).map(value => {
      if (!isRecord(value)) invalid()
      return {
        weekday: asNumber(value.weekday),
        windows: asArray(value.windows).map(window => {
          if (!isRecord(window)) invalid()
          return { start: asString(window.start), end: asString(window.end), periods: asNumber(window.periods) }
        }),
      }
    }),
  }
}

function catalogItems(data: unknown, key: 'faculties' | 'departments'): CatalogItem[] {
  if (!isRecord(data)) invalid()
  return asArray(data[key]).map(value => {
    if (!isRecord(value)) invalid()
    return { id: asString(value.id), name: asString(value.name) }
  })
}
