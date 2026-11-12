<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import messages from '../messages.json'
import TermsLink from '../TermsLink.vue'
import type { CatalogCourse, ComparedCourse, CourseLevel } from '../features/free-time/api'
import { useFreeTime } from '../features/free-time/useFreeTime'
import { useTelegram } from '../shared/telegram/telegram'

const MAX_COURSE_ID = 2147483647
const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const

const route = useRoute()
const router = useRouter()
const { rawInitData, languageCode } = useTelegram()
const {
  status, profile, faculties, departments, courses, faculty, department, result, comparing, catalogBusy, failed,
  load, compare, selectFaculty, selectDepartment,
} = useFreeTime(rawInitData)

const locale = computed(() => {
  const candidate = profile.value?.locale ?? languageCode.value
  return candidate in messages ? candidate : 'en'
})
const copy = computed<Record<string, string>>(
  () => profile.value?.ui ?? messages[locale.value as keyof typeof messages].preferences,
)

/** Selected courses live in the URL so a comparison can be reloaded or shared with friends. */
const queryIds = computed<number[] | undefined>(() => {
  const raw = route.query.courses
  if (typeof raw !== 'string') return undefined
  const ids = raw.split(',').map(Number).filter(id => Number.isInteger(id) && id > 0 && id <= MAX_COURSE_ID)
  return [...new Set(ids)]
})
const selectedIds = computed(() => queryIds.value ?? profile.value?.trackedCourseIds ?? [])
const maxCourses = computed(() => result.value?.maxCourses ?? 8)
const atLimit = computed(() => selectedIds.value.length >= maxCourses.value)
const comparedCourses = computed<ComparedCourse[]>(() => {
  const byId = new Map((result.value?.courses ?? []).map(course => [course.id, course]))
  return selectedIds.value.flatMap(id => byId.get(id) ?? [])
})
const busy = computed(() => comparing.value || catalogBusy.value)

function courseName(course: { number: number; level: CourseLevel }) {
  if (course.level === 'master') return copy.value.course_master
  if (course.level === 'doctorate') return copy.value.course_doctorate
  return copy.value.course_number?.replace('{number}', String(course.number))
}
function weekdayName(weekday: number) { return copy.value[weekdays[weekday - 1] ?? 'monday'] }
function periods(count: number) { return copy.value.free_time_periods?.replace('{count}', String(count)) }
function setSelection(ids: number[]) {
  void router.replace({ query: { ...route.query, courses: ids.join(',') }, hash: route.hash })
}
function addCourse(course: CatalogCourse) {
  if (selectedIds.value.includes(course.id) || atLimit.value) return
  setSelection([...selectedIds.value, course.id])
}
function removeCourse(id: number) { setSelection(selectedIds.value.filter(selected => selected !== id)) }
function selectedValue(event: Event) { return event.target instanceof HTMLSelectElement ? event.target.value : '' }

watch(() => profile.value?.theme, theme => { if (theme) document.documentElement.dataset.botTheme = theme })
watch(locale, value => { document.documentElement.lang = value }, { immediate: true })
watch(() => copy.value.free_time, title => { document.title = title ?? '' }, { immediate: true })
watch(
  () => (status.value === 'ready' ? selectedIds.value.join(',') : undefined),
  key => { if (key !== undefined) void compare(selectedIds.value) },
  { immediate: true },
)
onMounted(() => { if (rawInitData.value) void load() })
function retryAll() { if (status.value === 'ready') void compare(selectedIds.value); else void load() }
</script>

<template>
  <main class="app-shell free-time">
    <section v-if="!rawInitData" class="notice" role="status"><p>{{ copy.open_telegram }}</p></section>
    <section v-else-if="status === 'loading'" class="notice" role="status"><p>{{ copy.loading }}</p></section>
    <section v-else-if="status === 'expired'" class="notice" role="alert"><p>{{ copy.session_expired }}</p></section>
    <section v-else-if="status === 'error'" class="notice" role="alert">
      <p>{{ copy.error }}</p><button class="primary" @click="retryAll">{{ copy.retry }}</button>
    </section>
    <template v-else>
      <h1>{{ copy.free_time }}</h1>
      <p class="note">{{ copy.free_time_note }}</p>
      <div v-if="failed" class="free-time-error" role="alert">
        <p>{{ copy.error }}</p><button class="primary" :disabled="busy" @click="retryAll">{{ copy.retry }}</button>
      </div>

      <h2>{{ copy.free_time_selected }}</h2>
      <p v-if="!selectedIds.length">{{ copy.free_time_empty }}</p>
      <div v-for="course in comparedCourses" :key="course.id" class="course-row">
        <span>{{ course.faculty_name }} · {{ course.department_name }} · {{ courseName(course) }}</span>
        <button class="remove-course" :aria-label="`${copy.remove}: ${course.department_name}, ${courseName(course)}`"
          @click="removeCourse(course.id)">{{ copy.remove }}</button>
      </div>

      <section v-if="selectedIds.length" class="days" :aria-busy="comparing" aria-live="polite">
        <p v-if="comparing && !result" role="status">{{ copy.loading }}</p>
        <article v-for="day in result?.days ?? []" :key="day.weekday" class="day">
          <h3>{{ weekdayName(day.weekday) }}</h3>
          <ul v-if="day.windows.length">
            <li v-for="window in day.windows" :key="window.start">
              <strong>{{ window.start }}–{{ window.end }}</strong><span>{{ periods(window.periods) }}</span>
            </li>
          </ul>
          <p v-else>{{ copy.free_time_none }}</p>
        </article>
      </section>

      <fieldset :disabled="busy || atLimit">
        <legend>{{ copy.free_time_add }}</legend>
        <p v-if="atLimit">{{ copy.free_time_limit?.replace('{count}', String(maxCourses)) }}</p>
        <label class="catalog-select"><span>{{ copy.choose_faculty }}</span>
          <select :value="faculty" @change="selectFaculty(selectedValue($event))">
            <option value="">{{ copy.choose_faculty }}</option>
            <option v-for="item in faculties" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label v-if="faculty" class="catalog-select"><span>{{ copy.choose_department }}</span>
          <select :value="department" @change="selectDepartment(selectedValue($event))">
            <option value="">{{ copy.choose_department }}</option>
            <option v-for="item in departments" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <p v-if="department && !courses.length && !catalogBusy">{{ copy.no_courses }}</p>
        <div v-for="course in courses" :key="course.id" class="course-row">
          <span>{{ courseName(course) }}</span>
          <button class="add-course" :disabled="selectedIds.includes(course.id)"
            :aria-label="`${copy.free_time_add}: ${courseName(course)}`" @click="addCourse(course)">+</button>
        </div>
      </fieldset>
    </template>
    <TermsLink :locale="locale" from="free-time" />
  </main>
</template>

<style scoped>
.free-time { max-width: 620px; }
h1 { margin-top: 12px; }
h2 { font-size: 20px; margin: 28px 0 12px; }
h3 { font-size: 16px; margin: 0 0 8px; }
p { color: var(--muted); line-height: 1.5; }
.note { margin-top: 8px; }
.course-row { display: flex; gap: 16px; justify-content: space-between; align-items: center; min-height: 48px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.course-row span { overflow-wrap: anywhere; min-width: 0; }
.remove-course, .add-course { flex-shrink: 0; min-width: 44px; min-height: 44px; padding: 10px 12px; border-radius: 8px; background: var(--glass); color: var(--text); }
.add-course:disabled { opacity: .45; }
.days { display: grid; gap: 12px; margin-top: 20px; }
.day { padding: 14px 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--glass); }
.day p { margin: 0; }
.day ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
.day li { display: flex; flex-wrap: wrap; gap: 4px 12px; justify-content: space-between; }
.day li span { color: var(--muted); }
fieldset { border: 0; padding: 0; margin: 32px 0 24px; min-width: 0; }
fieldset:disabled { opacity: .65; }
legend { font-size: 20px; font-weight: 650; }
.catalog-select { display: grid; gap: 8px; margin: 20px 0; }
select { width: 100%; min-width: 0; min-height: 44px; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--glass); color: var(--text); font: inherit; }
option { background: Canvas; color: CanvasText; }
.free-time-error { padding: 12px 0; }
</style>
