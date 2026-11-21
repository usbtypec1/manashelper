import { deleteJson, getJson, postJson, putJson } from '../../shared/api/http'

export const notificationKeys = ['schedule_changes', 'exam_grades', 'lesson_skips'] as const
export const meals = ['lunch', 'dinner'] as const
type Notification = typeof notificationKeys[number]
type Meal = typeof meals[number]
export type CourseLevel = 'bachelor' | 'master' | 'doctorate'
export type Course = { id: number; number: number; is_tracked: boolean; level?: CourseLevel }
type TrackedCourse = { id: number; number: number; department_name: string; faculty_name: string; level?: CourseLevel }
export type CatalogItem = { id: string; name: string }
export type Settings = {
  locale: string
  theme: string
  ui: Record<string, string>
  has_obis_credentials: boolean
  notifications: { schedule_changes_enabled: boolean; exam_grades_enabled: boolean; lesson_skips_enabled: boolean; broadcast_muted_until: string | null }
  food: { weekday: number; lunch_enabled: boolean; dinner_enabled: boolean }[]
  eders: Record<string, boolean> | null
  tracked_courses: TrackedCourse[]
}

export function getSettings(initData: string) {
  return getJson('settings', initData) as Promise<Settings>
}

export function updateLocale(initData: string, locale: string) {
  return putJson('settings/locale', initData, { locale }) as Promise<Settings>
}

export function updateTheme(initData: string, theme: string) {
  return putJson('settings/theme', initData, { theme }) as Promise<Settings>
}

export function disconnectObis(initData: string) {
  return deleteJson('settings/obis', initData) as Promise<Settings>
}

export function requestChatSettings(initData: string, section: 'obis' | 'feedback') {
  return postJson('settings/chat', initData, { section })
}

export async function getFaculties(initData: string) {
  const data = await getJson('studies/faculties', initData) as { faculties: CatalogItem[] }
  return data.faculties
}

export async function getDepartments(initData: string, facultyId: string) {
  const query = new URLSearchParams({ faculty_id: facultyId })
  const data = await getJson(`studies/departments?${query}`, initData) as { departments: CatalogItem[] }
  return data.departments
}

export async function getCourses(initData: string, departmentId: string) {
  const query = new URLSearchParams({ department_id: departmentId })
  const data = await getJson(`studies/courses?${query}`, initData) as { courses: Course[] }
  return data.courses
}

export function updateNotification(initData: string, setting: Notification, enabled: boolean) {
  return putJson('settings/notifications', initData, { setting, enabled }) as Promise<Settings>
}

export function updateFood(initData: string, weekday: number, meal: Meal, enabled: boolean) {
  return putJson('settings/food', initData, { weekday, meal, enabled }) as Promise<Settings>
}

export function updateEders(initData: string, setting: string, enabled: boolean) {
  return putJson('settings/eders', initData, { setting, enabled }) as Promise<Settings>
}

export function updateBroadcast(initData: string, muted: boolean) {
  return putJson('settings/broadcast', initData, { muted }) as Promise<Settings>
}

export function updateCourse(initData: string, id: number, tracked: boolean) {
  return putJson(`studies/courses/${id}`, initData, { tracked }) as Promise<Settings>
}
