<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import messages from './messages.json'

const props = defineProps<{ initialTab: 'settings' | 'courses' }>()
type TelegramApp = {
  initData: string; colorScheme?: string; initDataUnsafe?: { user?: { language_code?: string } }
  ready: () => void; expand: () => void
  onEvent?: (event: string, callback: () => void) => void
  offEvent?: (event: string, callback: () => void) => void
}
type Course = { id: number; number: number; is_tracked: boolean }
type TrackedCourse = { id: number; number: number; department_name: string; faculty_name: string }
type CatalogItem = { id: string; name: string }
type Settings = {
  locale: string; ui: Record<string, string>
  notifications: { schedule_changes_enabled: boolean; exam_grades_enabled: boolean; lesson_skips_enabled: boolean; broadcast_muted_until: string | null }
  food: { weekday: number; lunch_enabled: boolean; dinner_enabled: boolean }[]
  eders: Record<string, boolean> | null; tracked_courses: TrackedCourse[]
}
const telegram = (window as Window & { Telegram?: { WebApp?: TelegramApp } }).Telegram?.WebApp
const detected = telegram?.initDataUnsafe?.user?.language_code?.split('-')[0] ?? 'en'
const locale = ref(detected in messages ? detected : 'en')
const data = ref<Settings>()
const copy = computed<Record<string, string>>(() => data.value?.ui ?? messages[locale.value as keyof typeof messages].preferences)
const tab = ref(props.initialTab)
const loading = ref(true)
const busy = ref(false)
const error = ref(false)
const expired = ref(false)
const saved = ref(false)
const faculties = ref<CatalogItem[]>([])
const departments = ref<CatalogItem[]>([])
const courses = ref<Course[]>([])
const faculty = ref('')
const department = ref('')
const notificationKeys = ['schedule_changes', 'exam_grades', 'lesson_skips'] as const
const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const
const meals = ['lunch', 'dinner'] as const
const broadcastsEnabled = computed(() => {
  const until = data.value?.notifications.broadcast_muted_until
  return !until || new Date(until).getTime() <= Date.now()
})

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body ? 'PUT' : 'GET', cache: 'no-store',
    headers: { Authorization: `tma ${telegram?.initData ?? ''}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (response.status === 401 || response.status === 403) expired.value = true
  if (!response.ok) throw new Error('Request failed')
  return response.json() as Promise<T>
}
function apply(settings: Settings) {
  data.value = settings
  locale.value = settings.locale in messages ? settings.locale : 'en'
  document.documentElement.lang = locale.value
  document.title = settings.ui.title ?? ''
  courses.value = courses.value.map(course => ({
    ...course, is_tracked: settings.tracked_courses.some(selected => selected.id === course.id),
  }))
}
async function load() {
  loading.value = true
  error.value = false
  expired.value = false
  try {
    const [settings, catalog] = await Promise.all([
      api<Settings>('settings'), api<{ faculties: CatalogItem[] }>('studies/faculties'),
    ])
    apply(settings)
    faculties.value = catalog.faculties
  } catch { error.value = true }
  finally { loading.value = false }
}
async function save(path: string, body: object) {
  if (busy.value) return
  busy.value = true
  saved.value = false
  error.value = false
  try { apply(await api<Settings>(path, body)); saved.value = true }
  catch { error.value = true }
  finally { busy.value = false }
}
async function selectFaculty(event: Event) {
  faculty.value = (event.target as HTMLSelectElement).value
  department.value = ''
  departments.value = []
  courses.value = []
  if (!faculty.value) return
  busy.value = true
  error.value = false
  try { departments.value = (await api<{ departments: CatalogItem[] }>(`studies/departments?faculty_id=${faculty.value}`)).departments }
  catch { error.value = true }
  finally { busy.value = false }
}
async function selectDepartment(event: Event) {
  department.value = (event.target as HTMLSelectElement).value
  courses.value = []
  if (!department.value) return
  busy.value = true
  error.value = false
  try { courses.value = (await api<{ courses: Course[] }>(`studies/courses?department_id=${department.value}`)).courses }
  catch { error.value = true }
  finally { busy.value = false }
}
function checked(event: Event) {
  const input = event.target as HTMLInputElement
  const desired = input.checked
  // Show the persisted value until the server confirms the change.
  input.checked = !desired
  return desired
}
function courseName(number: number) { return copy.value.course_number?.replace('{number}', String(number)) }
function applyTheme() { document.documentElement.dataset.theme = telegram?.colorScheme ?? 'dark' }
onMounted(() => {
  applyTheme()
  telegram?.onEvent?.('themeChanged', applyTheme)
  telegram?.ready()
  telegram?.expand()
  if (telegram?.initData) void load()
  else loading.value = false
})
onUnmounted(() => telegram?.offEvent?.('themeChanged', applyTheme))
</script>

<template>
  <main class="app-shell preferences">
    <section v-if="!telegram?.initData" class="notice" role="status"><p>{{ copy.open_telegram }}</p></section>
    <section v-else-if="loading" class="notice" role="status"><p>{{ copy.loading }}</p></section>
    <section v-else-if="expired" class="notice" role="alert"><p>{{ copy.session_expired }}</p></section>
    <template v-else>
      <h1>{{ copy.title }}</h1>
      <nav class="view-switch" :aria-label="copy.title">
        <button :aria-pressed="tab === 'settings'" @click="tab = 'settings'">{{ copy.notifications }}</button>
        <button :aria-pressed="tab === 'courses'" @click="tab = 'courses'">{{ copy.courses }}</button>
      </nav>
      <div v-if="error" class="preference-error" role="alert">
        <p>{{ copy.error }}</p><button class="primary" :disabled="busy" @click="load">{{ copy.retry }}</button>
      </div>
      <p role="status" aria-live="polite">{{ busy ? copy.saving : saved ? copy.saved : '' }}</p>
      <template v-if="data">
        <fieldset v-if="tab === 'settings'" :disabled="busy">
          <legend>{{ copy.notifications }}</legend>
          <p>{{ copy.note }}</p>
          <label v-for="key in notificationKeys" :key="key" class="preference-row">
            <span>{{ copy[key] }}</span>
            <input type="checkbox" :checked="data.notifications[`${key}_enabled`]"
              @change="save('settings/notifications', { setting: key, enabled: checked($event) })" />
          </label>
          <h2>{{ copy.food }}</h2>
          <div v-for="day in data.food" :key="day.weekday" class="food-day">
            <h3>{{ copy[weekdays[day.weekday]!] }}</h3>
            <label v-for="meal in meals" :key="meal" class="preference-row">
              <span>{{ copy[meal] }}</span>
              <input type="checkbox" :checked="day[`${meal}_enabled`]"
                @change="save('settings/food', { weekday: day.weekday, meal, enabled: checked($event) })" />
            </label>
          </div>
          <template v-if="data.eders">
            <h2>{{ copy.eders }}</h2>
            <label v-for="(enabled, key) in data.eders" :key="key" class="preference-row">
              <span>{{ copy[key] }}</span><input type="checkbox" :checked="enabled"
                @change="save('settings/eders', { setting: key, enabled: checked($event) })" />
            </label>
          </template>
          <h2>{{ copy.broadcast }}</h2>
          <p>{{ copy.broadcast_note }}</p>
          <label class="preference-row"><span>{{ copy.broadcast }}</span>
            <input type="checkbox" :checked="broadcastsEnabled" @change="save('settings/broadcast', { muted: !checked($event) })" />
          </label>
          <p v-if="!broadcastsEnabled && data.notifications.broadcast_muted_until">
            {{ copy.muted_until?.replace('{until}', new Date(data.notifications.broadcast_muted_until).toLocaleString(locale)) }}
          </p>
        </fieldset>
        <fieldset v-else :disabled="busy">
          <legend>{{ copy.courses }}</legend>
          <h2>{{ copy.selected_courses }}</h2>
          <p v-if="!data.tracked_courses.length">{{ copy.none_selected }}</p>
          <div v-for="course in data.tracked_courses" :key="course.id" class="preference-row">
            <span>{{ course.faculty_name }} · {{ course.department_name }} · {{ courseName(course.number) }}</span>
            <button class="remove-course" :aria-label="`${copy.remove}: ${course.department_name}, ${courseName(course.number)}`"
              @click="save(`studies/courses/${course.id}`, { tracked: false })">{{ copy.remove }}</button>
          </div>
          <label class="catalog-select"><span>{{ copy.choose_faculty }}</span>
            <select :value="faculty" @change="selectFaculty"><option value="">{{ copy.choose_faculty }}</option>
              <option v-for="item in faculties" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
          <label v-if="faculty" class="catalog-select"><span>{{ copy.choose_department }}</span>
            <select :value="department" @change="selectDepartment"><option value="">{{ copy.choose_department }}</option>
              <option v-for="item in departments" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
          <p v-if="department && !courses.length">{{ copy.no_courses }}</p>
          <label v-for="course in courses" :key="course.id" class="preference-row">
            <span>{{ courseName(course.number) }}</span><input type="checkbox" :checked="course.is_tracked"
              @change="save(`studies/courses/${course.id}`, { tracked: checked($event) })" />
          </label>
        </fieldset>
      </template>
    </template>
  </main>
</template>

<style scoped>
.preferences { max-width: 620px; }
fieldset { border: 0; padding: 0; margin: 24px 0; min-width: 0; }
legend { font-size: 24px; font-weight: 650; }
h2 { font-size: 20px; margin: 32px 0 12px; }
h3 { font-size: 16px; margin: 24px 0 4px; }
p { color: var(--muted); line-height: 1.5; }
.preference-row { display: flex; gap: 16px; justify-content: space-between; align-items: center; min-height: 48px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.preference-row span { overflow-wrap: anywhere; min-width: 0; }
input[type='checkbox'] { flex-shrink: 0; width: 24px; height: 24px; accent-color: var(--accent); }
.catalog-select { display: grid; gap: 8px; margin: 24px 0; }
select { width: 100%; min-width: 0; min-height: 44px; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--glass); color: var(--text); font: inherit; }
option { background: Canvas; color: CanvasText; }
.remove-course { background: var(--glass); border-radius: 8px; padding: 12px; flex-shrink: 0; }
.preference-error { padding: 16px 0; }
fieldset:disabled { opacity: .65; }
</style>
