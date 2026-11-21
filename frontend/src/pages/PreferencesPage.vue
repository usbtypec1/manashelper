<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { meals, notificationKeys, type CourseLevel } from '../features/preferences/api'
import { usePreferences } from '../features/preferences/usePreferences'
import TermsLink from '../features/terms/TermsLink.vue'
import { locales } from '../shared/i18n/locale'
import { confirmTelegramAction } from '../shared/telegram/confirmation'
import '../features/admin/admin.css'

const props = defineProps<{ tab: 'settings' | 'courses' }>()
const {
  rawInitData, locale, data, copy, loading, busy, error, expired, saved, sentToChat,
  faculties, departments, courses, faculty, department, broadcastsEnabled,
  load, selectFaculty, selectDepartment, setLocale, setTheme, openChat, clearObis,
  setNotification, setFood, setEders, setBroadcast, setCourse,
} = usePreferences()
const tab = computed(() => props.tab)
const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const
const themes = computed(() => Object.entries(copy.value)
  .filter(([key]) => key.startsWith('theme_'))
  .map(([key, name]) => ({ value: key.slice('theme_'.length), name })))

function selectedValue(event: Event) {
  return (event.target as HTMLSelectElement).value
}
function changeProfile(event: Event, current: string, update: (value: string) => Promise<void>) {
  const select = event.target as HTMLSelectElement
  const desired = select.value
  select.value = current
  void update(desired)
}
async function confirmObisRemoval() {
  if (busy.value || !copy.value.obis_remove_prompt || !copy.value.obis_remove_confirm) return
  if (await confirmTelegramAction(copy.value.obis_remove_prompt, copy.value.obis_remove_confirm)) await clearObis()
}
function checked(event: Event) {
  const input = event.target as HTMLInputElement
  const desired = input.checked
  // Show the persisted value until the server confirms the change.
  input.checked = !desired
  return desired
}
function courseName(course: { number: number; level?: CourseLevel }) {
  // Graduate programmes are numbered 5/6 on the timetable site; show their names instead.
  if (course.level === 'master') return copy.value.course_master
  if (course.level === 'doctorate') return copy.value.course_doctorate
  return copy.value.course_number?.replace('{number}', String(course.number))
}
</script>

<template>
  <div class="telegram-admin">
    <div v-if="!rawInitData" class="app-shell"><section class="notice" role="status"><p>{{ copy.open_telegram }}</p></section></div>
    <div v-else-if="loading" class="app-shell"><section class="notice" role="status"><p>{{ copy.loading }}</p></section></div>
    <div v-else-if="expired" class="app-shell"><section class="notice" role="alert"><p>{{ copy.session_expired }}</p></section></div>
    <div v-else class="app-shell admin-shell preferences">
      <nav class="admin-tabs" :aria-label="copy.title">
        <RouterLink :to="{ name: 'settings' }" :aria-current="tab === 'settings' ? 'page' : undefined">{{ copy.title }}</RouterLink>
        <RouterLink :to="{ name: 'courses' }" :aria-current="tab === 'courses' ? 'page' : undefined">{{ copy.courses }}</RouterLink>
      </nav>
      <main class="admin-main">
        <h1>{{ copy.title }}</h1>
        <div v-if="error" class="preference-error" role="alert">
          <p class="admin-hint">{{ copy.error }}</p>
          <button class="admin-button primary" :disabled="busy" @click="load">{{ copy.retry }}</button>
        </div>
        <p class="admin-hint" role="status" aria-live="polite">
          {{ busy ? copy.saving : sentToChat ? copy.sent_to_chat : saved ? copy.saved : '' }}
        </p>
        <template v-if="data">
          <template v-if="tab === 'settings'">
            <fieldset class="admin-card profile-settings" :disabled="busy">
              <label class="admin-field">
                <span>{{ copy.language }}</span>
                <select :value="data.locale" @change="changeProfile($event, data.locale, setLocale)">
                  <option v-for="option in locales" :key="option" :value="option">{{ copy[`locale_${option}`] }}</option>
                </select>
              </label>
              <label class="admin-field">
                <span>{{ copy.theme }}</span>
                <select :value="data.theme" @change="changeProfile($event, data.theme, setTheme)">
                  <option v-for="option in themes" :key="option.value" :value="option.value">{{ option.name }}</option>
                </select>
              </label>
            </fieldset>
            <fieldset class="admin-card" :disabled="busy">
              <h2>{{ copy.obis }}</h2>
              <div class="admin-actions">
                <button type="button" class="admin-button" @click="openChat('obis')">
                  {{ data.has_obis_credentials ? copy.obis_update : copy.obis_link }}
                </button>
                <button v-if="data.has_obis_credentials" type="button" class="admin-button" @click="confirmObisRemoval">
                  {{ copy.obis_remove }}
                </button>
              </div>
            </fieldset>
            <fieldset class="admin-card" :disabled="busy">
              <h2>{{ copy.notifications }}</h2>
              <p class="admin-hint">{{ copy.note }}</p>
              <label v-for="key in notificationKeys" :key="key" class="preference-row">
                <span>{{ copy[key] }}</span>
                <input type="checkbox" :checked="data.notifications[`${key}_enabled`]"
                  @change="setNotification(key, checked($event))" />
              </label>
            </fieldset>
            <fieldset class="admin-card" :disabled="busy">
              <h2>{{ copy.food }}</h2>
              <div v-for="day in data.food" :key="day.weekday" class="food-day">
                <h3>{{ copy[weekdays[day.weekday]!] }}</h3>
                <label v-for="meal in meals" :key="meal" class="preference-row">
                  <span>{{ copy[meal] }}</span>
                  <input type="checkbox" :checked="day[`${meal}_enabled`]"
                    @change="setFood(day.weekday, meal, checked($event))" />
                </label>
              </div>
            </fieldset>
            <fieldset v-if="data.eders" class="admin-card" :disabled="busy">
              <h2>{{ copy.eders }}</h2>
              <label v-for="(enabled, key) in data.eders" :key="key" class="preference-row">
                <span>{{ copy[key] }}</span><input type="checkbox" :checked="enabled"
                  @change="setEders(key, checked($event))" />
              </label>
            </fieldset>
            <fieldset class="admin-card" :disabled="busy">
              <h2>{{ copy.broadcast }}</h2>
              <p class="admin-hint">{{ copy.broadcast_note }}</p>
              <label class="preference-row"><span>{{ copy.broadcast }}</span>
                <input type="checkbox" :checked="broadcastsEnabled" @change="setBroadcast(!checked($event))" />
              </label>
              <p v-if="!broadcastsEnabled && data.notifications.broadcast_muted_until" class="admin-hint">
                {{ copy.muted_until?.replace('{until}', new Date(data.notifications.broadcast_muted_until).toLocaleString(locale)) }}
              </p>
            </fieldset>
            <button type="button" class="admin-button" :disabled="busy" @click="openChat('feedback')">
              {{ copy.feedback }}
            </button>
          </template>
          <template v-else>
            <fieldset class="admin-card" :disabled="busy">
              <h2>{{ copy.selected_courses }}</h2>
              <p v-if="!data.tracked_courses.length" class="admin-hint">{{ copy.none_selected }}</p>
              <RouterLink v-else class="free-time-link" :to="{ name: 'free-time' }">{{ copy.free_time }} →</RouterLink>
              <div v-for="course in data.tracked_courses" :key="course.id" class="preference-row">
                <span>{{ course.faculty_name }} · {{ course.department_name }} · {{ courseName(course) }}</span>
                <button class="admin-button remove-course" :aria-label="`${copy.remove}: ${course.department_name}, ${courseName(course)}`"
                  @click="setCourse(course.id, false)">{{ copy.remove }}</button>
              </div>
            </fieldset>
            <fieldset class="admin-card" :disabled="busy">
              <label class="admin-field"><span>{{ copy.choose_faculty }}</span>
                <select :value="faculty" @change="selectFaculty(selectedValue($event))"><option value="">{{ copy.choose_faculty }}</option>
                  <option v-for="item in faculties" :key="item.id" :value="item.id">{{ item.name }}</option>
                </select>
              </label>
              <label v-if="faculty" class="admin-field"><span>{{ copy.choose_department }}</span>
                <select :value="department" @change="selectDepartment(selectedValue($event))"><option value="">{{ copy.choose_department }}</option>
                  <option v-for="item in departments" :key="item.id" :value="item.id">{{ item.name }}</option>
                </select>
              </label>
              <p v-if="department && !courses.length" class="admin-hint">{{ copy.no_courses }}</p>
              <label v-for="course in courses" :key="course.id" class="preference-row">
                <span>{{ courseName(course) }}</span><input type="checkbox" :checked="course.is_tracked"
                  @change="setCourse(course.id, checked($event))" />
              </label>
            </fieldset>
          </template>
        </template>
        <TermsLink :locale="locale" :from="tab" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.profile-settings { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(12rem, 100%), 1fr)); }
.food-day { margin: 20px 0; }
.food-day:first-child { margin-top: 0; }
.food-day h3 { margin: 0 0 4px; font-size: 16px; font-weight: 600; color: var(--admin-hint); }
.preference-row { display: flex; gap: 16px; justify-content: space-between; align-items: center; min-height: 48px; padding: 12px 0; }
.preference-row + .preference-row { border-top: 1px solid var(--admin-divider); }
.preference-row span { overflow-wrap: anywhere; min-width: 0; }
input[type='checkbox'] { flex-shrink: 0; width: 24px; height: 24px; accent-color: var(--admin-accent); }
.free-time-link { display: inline-flex; align-items: center; min-height: 44px; color: var(--admin-accent); text-decoration: none; }
.remove-course { flex-shrink: 0; }
.preference-error { display: grid; gap: 12px; justify-items: start; padding: 16px 0; }
fieldset:disabled { opacity: .65; }
</style>
