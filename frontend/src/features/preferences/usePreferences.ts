import { computed, onMounted, ref } from 'vue'
import { HttpError } from '../../shared/api/http'
import { normalizeLocale } from '../../shared/i18n/locale'
import messages from '../../shared/i18n/messages.json'
import { closeTelegramMiniApp, useTelegram } from '../../shared/telegram/telegram'
import {
  getCourses, getDepartments, getFaculties, getSettings, meals, notificationKeys,
  disconnectObis, requestChatSettings, updateBroadcast, updateCourse, updateEders, updateFood,
  updateLocale, updateNotification, updateTheme,
  type CatalogItem, type Course, type Settings,
} from './api'

export function usePreferences() {
  const { rawInitData, languageCode } = useTelegram()
  const locale = ref(normalizeLocale(languageCode.value))
  const data = ref<Settings>()
  const copy = computed<Record<string, string>>(() => data.value?.ui ?? messages[locale.value].preferences)
  const loading = ref(true)
  const busy = ref(false)
  const error = ref(false)
  const expired = ref(false)
  const saved = ref(false)
  const sentToChat = ref(false)
  const faculties = ref<CatalogItem[]>([])
  const departments = ref<CatalogItem[]>([])
  const courses = ref<Course[]>([])
  const faculty = ref('')
  const department = ref('')
  const broadcastsEnabled = computed(() => {
    const until = data.value?.notifications.broadcast_muted_until
    return !until || new Date(until).getTime() <= Date.now()
  })

  async function withSession<T>(request: Promise<T>): Promise<T> {
    try { return await request }
    catch (failure) {
      if (failure instanceof HttpError && failure.unauthorized) expired.value = true
      throw failure
    }
  }
  function apply(settings: Settings) {
    data.value = settings
    document.documentElement.dataset.botTheme = settings.theme
    locale.value = normalizeLocale(settings.locale)
    document.documentElement.lang = locale.value
    document.title = settings.ui.title ?? ''
    courses.value = courses.value.map(course => ({
      ...course, is_tracked: settings.tracked_courses.some(selected => selected.id === course.id),
    }))
  }
  async function load() {
    loading.value = true
    error.value = false
    sentToChat.value = false
    expired.value = false
    const initData = rawInitData.value ?? ''
    try {
      const [settings, catalog] = await Promise.all([
        withSession(getSettings(initData)), withSession(getFaculties(initData)),
      ])
      apply(settings)
      faculties.value = catalog
    } catch { error.value = true }
    finally { loading.value = false }
  }
  async function save(update: (initData: string) => Promise<Settings>) {
    if (busy.value) return
    busy.value = true
    saved.value = false
    sentToChat.value = false
    error.value = false
    try {
      apply(await withSession(update(rawInitData.value ?? '')))
      saved.value = true
    } catch { error.value = true }
    finally { busy.value = false }
  }
  async function openChat(section: 'obis' | 'feedback') {
    if (!rawInitData.value || busy.value) return
    busy.value = true
    saved.value = false
    sentToChat.value = false
    error.value = false
    try {
      await withSession(requestChatSettings(rawInitData.value, section))
      sentToChat.value = true
      closeTelegramMiniApp()
    } catch { error.value = true }
    finally { busy.value = false }
  }
  async function selectFaculty(value: string) {
    faculty.value = value
    department.value = ''
    departments.value = []
    courses.value = []
    if (!value) return
    busy.value = true
    error.value = false
    try { departments.value = await withSession(getDepartments(rawInitData.value ?? '', value)) }
    catch { error.value = true }
    finally { busy.value = false }
  }
  async function selectDepartment(value: string) {
    department.value = value
    courses.value = []
    if (!value) return
    busy.value = true
    error.value = false
    try { courses.value = await withSession(getCourses(rawInitData.value ?? '', value)) }
    catch { error.value = true }
    finally { busy.value = false }
  }
  onMounted(() => {
    if (rawInitData.value) void load()
    else loading.value = false
  })

  return {
    rawInitData, locale, data, copy, loading, busy, error, expired, saved, sentToChat,
    faculties, departments, courses, faculty, department, broadcastsEnabled,
    load, selectFaculty, selectDepartment, openChat,
    setLocale: (value: string) => save(initData => updateLocale(initData, value)),
    setTheme: (value: string) => save(initData => updateTheme(initData, value)),
    clearObis: () => save(disconnectObis),
    setNotification: (setting: typeof notificationKeys[number], enabled: boolean) =>
      save(initData => updateNotification(initData, setting, enabled)),
    setFood: (weekday: number, meal: typeof meals[number], enabled: boolean) =>
      save(initData => updateFood(initData, weekday, meal, enabled)),
    setEders: (setting: string, enabled: boolean) => save(initData => updateEders(initData, setting, enabled)),
    setBroadcast: (muted: boolean) => save(initData => updateBroadcast(initData, muted)),
    setCourse: (id: number, tracked: boolean) => save(initData => updateCourse(initData, id, tracked)),
  }
}
