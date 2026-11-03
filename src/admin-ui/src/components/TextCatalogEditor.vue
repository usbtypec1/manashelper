<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { AdminApi, ApiError } from '../api'
import { clone, locales, type Schemas } from '../types'
import { t, type CopyKey } from '../i18n'
import TelegramText from './TelegramText.vue'

const props = defineProps<{
  api: AdminApi
  ask: (key: CopyKey, detail?: string) => Promise<boolean>
}>()
const emit = defineEmits<{ dirty: [boolean]; published: []; failure: [unknown] }>()
const draft = ref<Schemas['TextCatalogDraft'] | null>(null)
const releases = ref<Schemas['TextCatalogRelease'][]>([])
const selected = ref<Schemas['TextEntry'] | null>(null)
const saved = ref(''),
  query = ref(''),
  locale = ref('en'),
  theme = ref('basic'),
  form = ref('other')
const busy = ref(false),
  error = ref<CopyKey | null>(null),
  issues = ref<Schemas['ContractIssue'][]>([])
const dirty = computed(() => !!selected.value && JSON.stringify(selected.value) !== saved.value)
watch(dirty, (value) => emit('dirty', value), { immediate: true })
const entries = computed(() => {
  const term = query.value.trim().toLowerCase()
  return (
    draft.value?.document.entries.filter(
      (entry) =>
        !term ||
        entry.key.toLowerCase().includes(term) ||
        entry.variants.some((variant) => variant.text.toLowerCase().includes(term)),
    ) ?? []
  )
})
const forms = computed(
  () =>
    selected.value?.variants
      .filter((variant) => variant.locale === locale.value && variant.theme === theme.value)
      .map((variant) => variant.form) ?? [],
)
const active = computed(() =>
  selected.value?.variants.find(
    (variant) =>
      variant.locale === locale.value && variant.theme === theme.value && variant.form === form.value,
  ),
)
watch(forms, (values) => {
  if (!values.includes(form.value as never)) form.value = values[0] ?? 'other'
})
function select(entry: Schemas['TextEntry']) {
  selected.value = clone(entry)
  saved.value = JSON.stringify(selected.value)
}
async function choose(entry: Schemas['TextEntry']) {
  if (!dirty.value || (await props.ask('discardChanges'))) select(entry)
}
function failed(failure: unknown) {
  error.value = failure instanceof ApiError && failure.status === 409 ? 'conflict' : 'requestFailed'
  issues.value = failure instanceof ApiError ? failure.issues : []
  emit('failure', failure)
}
async function load() {
  if (dirty.value && !(await props.ask('discardChanges'))) return
  busy.value = true
  try {
    const [value, history] = await Promise.all([
      props.api.request<Schemas['TextCatalogDraft']>('/texts'),
      props.api.request<Schemas['TextCatalogVersions']>('/texts/releases'),
    ])
    const key = selected.value?.key
    draft.value = value
    releases.value = history.items
    const entry = value.document.entries.find((item) => item.key === key) ?? value.document.entries[0]
    if (entry) select(entry)
    error.value = null
    issues.value = []
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function save() {
  if (!selected.value || !draft.value) return
  busy.value = true
  try {
    const key = selected.value.key
    const value = await props.api.request<Schemas['TextCatalogDraft']>(
      '/texts/' + encodeURIComponent(key),
      'PUT',
      {
        entry: selected.value,
        expected_revision: draft.value.revision,
      },
    )
    draft.value = value
    select(value.document.entries.find((entry) => entry.key === key)!)
    error.value = null
    issues.value = []
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function publish() {
  if (!draft.value || !(await props.ask('textPublishConfirm'))) return
  busy.value = true
  try {
    await props.api.request('/texts/publish', 'POST', { expected_revision: draft.value.revision })
    await load()
    emit('published')
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function activate(release: number) {
  if (!draft.value || !(await props.ask('textActivateConfirm', 'v' + release))) return
  busy.value = true
  try {
    draft.value = await props.api.request<Schemas['TextCatalogDraft']>('/texts/activate', 'POST', {
      release_id: release,
      expected_current_release: draft.value.current_release,
    })
    error.value = null
    emit('published')
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="text-catalog" data-testid="text-catalog">
    <header class="row between">
      <div>
        <h1>{{ t('textCatalog') }}</h1>
        <p>{{ t('textCatalogHint') }}</p>
        <span v-if="draft" class="pill"
          >r{{ draft.revision }} · {{ t('textCurrentRelease') }} v{{ draft.current_release }}</span
        >
      </div>
      <div class="row">
        <button type="button" :disabled="busy" @click="load">{{ t('reload') }}</button>
        <button type="button" class="primary" :disabled="busy || dirty || !draft" @click="publish">
          {{ t('publish') }}
        </button>
      </div>
    </header>
    <div v-if="error" class="notice-bar error" role="alert">
      {{ t(error) }}
      <ul v-if="issues.length">
        <li v-for="issue in issues" :key="issue.path + issue.code">{{ issue.message }} · {{ issue.path }}</li>
      </ul>
    </div>
    <label class="field"
      >{{ t('textSearch') }}<input v-model="query" type="search" :aria-label="t('textSearch')"
    /></label>
    <div class="text-catalog-body">
      <nav class="text-key-list" :aria-label="t('textKey')">
        <button
          v-for="entry in entries"
          :key="entry.key"
          type="button"
          :disabled="busy"
          :class="{ active: selected?.key === entry.key }"
          @click="choose(entry)"
        >
          {{ entry.key }}
        </button>
        <p v-if="!entries.length">{{ t('textNoMatches') }}</p>
      </nav>
      <main v-if="selected" class="text-entry">
        <h2>{{ selected.key }}</h2>
        <p>
          {{ t('textOwner') }}: <code>{{ selected.owner }}</code> · {{ t('textContentType') }}:
          <code>{{ selected.content_type }}</code>
        </p>
        <p>
          {{ t('textParameters') }}: <code>{{ (selected.parameters ?? []).join(', ') || '—' }}</code>
        </p>
        <div class="row">
          <label
            >{{ t('locale')
            }}<select v-model="locale" :disabled="busy">
              <option v-for="value in locales" :key="value">{{ value }}</option>
            </select></label
          >
          <label
            >{{ t('theme')
            }}<select v-model="theme" :disabled="busy">
              <option>basic</option>
              <option>halloween</option>
            </select></label
          >
          <label
            >{{ t('textForm')
            }}<select v-model="form" :disabled="busy">
              <option v-for="value in forms" :key="value">{{ value }}</option>
            </select></label
          >
        </div>
        <label v-if="active" class="field"
          >{{ t('textKey')
          }}<textarea v-model="active.text" :disabled="busy" rows="7" :aria-label="selected.key" />
        </label>
        <p v-else>{{ t('textNoMatches') }}</p>
        <div class="row">
          <span class="pill">{{ dirty ? t('unsaved') : t('saved') }}</span
          ><button type="button" class="secondary" :disabled="busy || !dirty" @click="save">
            {{ t('save') }}
          </button>
        </div>
        <h3>{{ t('preview') }}</h3>
        <TelegramText v-if="active" :text="active.text" />
      </main>
    </div>
    <details v-if="draft">
      <summary>{{ t('textReleases') }}</summary>
      <div v-for="release in releases" :key="release.id" class="row">
        <span>v{{ release.id }} · r{{ release.draft_revision }} · {{ release.published_at }}</span
        ><button
          type="button"
          :disabled="busy || release.id === draft.current_release"
          @click="activate(release.id)"
        >
          {{ t('activate') }}
        </button>
      </div>
    </details>
  </section>
</template>

<style scoped>
.text-catalog {
  padding: 20px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.text-catalog p {
  color: var(--muted);
}
.text-catalog-body {
  display: grid;
  grid-template-columns: minmax(150px, 270px) minmax(0, 1fr);
  gap: 20px;
  margin: 16px 0;
}
.text-key-list {
  display: flex;
  flex-direction: column;
  max-height: 60vh;
  overflow: auto;
}
.text-key-list button {
  justify-content: flex-start;
  white-space: normal;
  overflow-wrap: anywhere;
  text-align: left;
}
.text-key-list .active {
  background: var(--accent-wash);
}
.text-entry {
  min-width: 0;
}
.text-entry textarea {
  width: 100%;
}
.text-entry .row {
  flex-wrap: wrap;
}
@media (max-width: 650px) {
  .text-catalog-body {
    grid-template-columns: minmax(0, 1fr);
  }
  .text-key-list {
    max-height: 160px;
  }
}
</style>
