<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { VueFlow, type Connection, type NodeDragEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { AdminApi, ApiError } from './api'
import type { Document, Issue, Schemas, FlowNode } from './types'
import {
  clone,
  connect,
  identifier,
  issueNode,
  kinds,
  newDocument,
  newNode,
  ports,
  renameNode,
  textLabel,
} from './types'
import { t, uiLocale, type CopyKey } from './i18n'
import FlowGraphNode from './components/FlowGraphNode.vue'
import NodeInspector from './components/NodeInspector.vue'
import PreviewPane from './components/PreviewPane.vue'
import FieldsEditor from './components/FieldsEditor.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import UserMonitor from './components/UserMonitor.vue'
import ReleaseControl from './components/ReleaseControl.vue'

const props = defineProps<{ ticket: string | null }>()
const api = new AdminApi()
const mode = ref<'editor' | 'users'>('editor')
const session = ref<Schemas['AdminSession'] | null>(null),
  ready = ref(false),
  busy = ref(false)
const flows = ref<Schemas['FlowSummary'][]>([]),
  catalog = ref<Schemas['EditorCatalog']>({ texts: [], capability_fields: {}, capabilities: {} }),
  delegates = ref<Schemas['DelegateDefinition'][]>([])
const document = ref<Document | null>(null),
  revision = ref(0),
  published = ref<number | null>(null)
const snapshot = ref(''),
  rawDirty = ref(false),
  selected = ref<string | null>(null)
const issues = ref<Issue[]>([]),
  notice = ref<CopyKey | null>(null),
  isError = ref(false)
const panel = ref<'settings' | 'preview' | 'fields'>('settings'),
  newModal = ref(false),
  newId = ref('')
const showVersions = ref(false),
  versions = ref<Schemas['FlowVersion'][]>([])
const confirmation = ref<{ message: string; detail?: string; resolve: (answer: boolean) => void } | null>(
  null,
)
const dirty = computed(
  () => !!document.value && (JSON.stringify(document.value) !== snapshot.value || rawDirty.value),
)
const node = computed(() => document.value?.nodes.find((node) => node.id === selected.value))
const graphNodes = computed(
  () =>
    document.value?.nodes.map((node, index) => ({
      id: node.id,
      type: 'flow',
      position: document.value?.layout?.[node.id] ?? {
        x: 80 + (index % 3) * 330,
        y: 80 + Math.floor(index / 3) * 350,
      },
      selected: selected.value === node.id,
      data: {
        kind: node.kind,
        title:
          'text' in node
            ? textLabel(node.text?.[0], uiLocale.value, catalog.value)
            : node.kind === 'action'
              ? node.delegate
              : '',
        ports: ports(node),
        entry: document.value?.entry === node.id,
        invalid: issues.value.some((issue) => issueNode(document.value!, issue) === node.id),
      },
    })) ?? [],
)
const graphEdges = computed(
  () =>
    document.value?.nodes.flatMap((node) =>
      ports(node)
        .filter((port) => document.value?.nodes.some((node) => node.id === port.target))
        .map((port) => ({
          id: node.id + '|' + port.id,
          source: node.id,
          target: port.target,
          sourceHandle: port.id,
          type: 'smoothstep',
          animated: false,
        })),
    ) ?? [],
)
api.onUnauthorized = () => {
  session.value = null
}
watch(
  uiLocale,
  (value) => {
    window.document.documentElement.lang = value
    window.document.title = t('title') + ' · Manashelper'
  },
  { immediate: true },
)
watch(
  () => JSON.stringify(document.value),
  () => {
    issues.value = []
    notice.value = null
  },
)

function report(error: unknown) {
  notice.value = error instanceof ApiError && error.status === 409 ? 'conflict' : 'requestFailed'
  issues.value = error instanceof ApiError ? error.issues : []
  isError.value = true
}
function focusIssue(issue: Issue) {
  if (document.value) selected.value = issueNode(document.value, issue) ?? selected.value
  panel.value = 'settings'
}
async function task(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  try {
    await action()
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
function ask(key: CopyKey, detail?: string): Promise<boolean> {
  return new Promise((resolve) => (confirmation.value = { message: t(key), detail, resolve }))
}
function answer(value: boolean) {
  const current = confirmation.value
  confirmation.value = null
  current?.resolve(value)
}
async function discard(): Promise<boolean> {
  return !dirty.value || (await ask('discardChanges'))
}
function validInputs(): boolean {
  if (panel.value === 'preview') return true
  const invalid = window.document.querySelector<HTMLInputElement>(
    'input:invalid,textarea:invalid,select:invalid',
  )
  if (invalid) {
    invalid.reportValidity()
    return false
  }
  return true
}
function touch() {
  if (panel.value !== 'preview')
    rawDirty.value = !!window.document.querySelector('input:invalid,textarea:invalid,select:invalid')
}
async function refreshList() {
  flows.value = await api.all<Schemas['FlowSummary']>('/flows')
}
function setDraft(draft: Schemas['FlowDraft'], pointer: number | null) {
  document.value = clone(draft.document)
  revision.value = draft.revision
  published.value = pointer
  snapshot.value = JSON.stringify(document.value)
  rawDirty.value = false
  selected.value = document.value.nodes.some((node) => node.id === selected.value)
    ? selected.value
    : document.value.entry
  issues.value = []
  notice.value = null
}
async function load(id: string) {
  const [draft, summary] = await Promise.all([
    api.request<Schemas['FlowDraft']>(`/flows/${id}/draft`),
    api.request<Schemas['FlowSummary']>(`/flows/${id}`),
  ])
  setDraft(draft, summary.published_version)
  panel.value = 'settings'
  showVersions.value = false
}
function choose(id: string) {
  void task(async () => {
    if (document.value?.id !== id && (await discard())) await load(id)
  })
}
function save() {
  void task(async () => {
    if (!document.value || !validInputs()) return
    const draft = await api.request<Schemas['FlowDraft']>(`/flows/${document.value.id}/draft`, 'PUT', {
      document: clone(document.value),
      expected_revision: revision.value,
    })
    setDraft(draft, published.value)
    await refreshList()
    notice.value = 'saved'
    isError.value = false
  })
}
function validate() {
  void task(async () => {
    if (!document.value || !validInputs()) return
    const report = await api.request<Schemas['ValidationReport']>(
      `/flows/${document.value.id}/validate`,
      'POST',
      { document: clone(document.value) },
    )
    issues.value = report.issues
    notice.value = report.issues.length ? 'issues' : 'valid'
    isError.value = !!report.issues.length
  })
}
function publish() {
  void task(async () => {
    if (!document.value || dirty.value || !(await ask('confirmPublish', document.value.id))) return
    const version = await api.request<Schemas['FlowVersion']>(`/flows/${document.value.id}/publish`, 'POST', {
      expected_revision: revision.value,
    })
    published.value = version.version
    await refreshList()
    notice.value = 'published'
    isError.value = false
  })
}
function history() {
  void task(async () => {
    versions.value = await api.all<Schemas['FlowVersion']>(`/flows/${document.value!.id}/versions`)
    showVersions.value = !showVersions.value
  })
}
function activate(version: number) {
  void task(async () => {
    if (!document.value || !(await ask('confirmActivate', `${document.value.id} · v${version}`))) return
    const result = await api.request<Schemas['FlowSummary']>(`/flows/${document.value.id}/activate`, 'POST', {
      version,
      expected_published_version: published.value,
    })
    published.value = result.published_version
    await refreshList()
    showVersions.value = false
    notice.value = 'published'
    isError.value = false
  })
}
function create() {
  void task(async () => {
    if (!identifier.test(newId.value) || !(await discard())) return
    const draft = await api.request<Schemas['FlowDraft']>('/flows', 'POST', {
      document: newDocument(newId.value),
    })
    setDraft(draft, null)
    newModal.value = false
    newId.value = ''
    await refreshList()
  })
}
function add(kind: FlowNode['kind']) {
  if (!document.value || document.value.nodes.length >= 200) return
  const node = newNode(document.value, kind)
  const index = document.value.nodes.length
  ;(document.value.layout ??= {})[node.id] = {
    x: 80 + (index % 3) * 330,
    y: 80 + Math.floor(index / 3) * 350,
  }
  document.value.nodes.push(node)
  selected.value = node.id
  panel.value = 'settings'
}
function connected(connection: Connection) {
  const node = document.value?.nodes.find((node) => node.id === connection.source)
  if (node && connection.sourceHandle && connection.target)
    connect(node, connection.sourceHandle, connection.target)
}
function dragged(event: NodeDragEvent) {
  if (!document.value) return
  for (const node of event.nodes)
    (document.value.layout ??= {})[node.id] = { x: node.position.x, y: node.position.y }
}
function rename(id: string) {
  if (document.value && node.value && renameNode(document.value, node.value.id, id)) selected.value = id
  else {
    notice.value = 'invalidId'
    isError.value = true
  }
}
function removeNode() {
  void task(async () => {
    if (!document.value || !node.value || !(await ask('confirmDelete', node.value.id))) return
    const id = node.value.id
    document.value.nodes = document.value.nodes.filter((node) => node.id !== id)
    delete document.value.layout?.[id]
    selected.value = null
  })
}
function reload() {
  void task(async () => {
    if (document.value && (await discard())) await load(document.value.id)
  })
}
function signOut() {
  void task(async () => {
    if (await discard()) {
      await api.request('/auth/logout', 'POST')
      session.value = null
      document.value = null
      api.csrf = ''
    }
  })
}
function exportJson() {
  if (!document.value) return
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(document.value, null, 2)], { type: 'application/json' }),
  )
  const anchor = window.document.createElement('a')
  anchor.href = url
  anchor.download = document.value.id + '.json'
  anchor.click()
  URL.revokeObjectURL(url)
}
function importJson(event: Event) {
  const element = event.target as HTMLInputElement,
    file = element.files?.[0]
  element.value = ''
  if (!file || !document.value) return
  void task(async () => {
    if (!(await ask('importHint'))) return
    const value = JSON.parse(await file.text()) as Document
    if (value.id !== document.value?.id)
      throw new ApiError(422, [{ code: 'id_mismatch', path: '/id', message: 'id_mismatch' }])
    const report = await api.request<Schemas['ValidationReport']>(`/flows/${value.id}/validate`, 'POST', {
      document: value,
    })
    document.value = value
    rawDirty.value = true
    selected.value = value.entry
    issues.value = report.issues
    panel.value = 'settings'
  })
}
function unload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onMounted(async () => {
  window.addEventListener('beforeunload', unload)
  await task(async () => {
    session.value = await api.login(props.ticket)
    const [texts, actions] = await Promise.all([
      api.request<Schemas['EditorCatalog']>('/catalog'),
      api.request<Schemas['DelegateCatalog']>('/delegates'),
    ])
    catalog.value = texts
    delegates.value = actions.items
    await refreshList()
    if (flows.value.length) await load(flows.value[0].id)
  })
  ready.value = true
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', unload))
</script>

<template>
  <div v-if="!ready || !session" class="login-shell">
    <div class="login-card">
      <span class="brand-mark">M</span>
      <h1>Manashelper</h1>
      <h2>{{ ready ? t('sessionExpired') : t('loading') }}</h2>
      <p>{{ ready ? t('signInHint') : '' }}</p>
    </div>
  </div>
  <div v-else class="app-shell">
    <header class="app-header">
      <div class="brand">
        <span class="brand-mark">M</span><strong>Manashelper</strong><span class="header-divider" /><span>{{
          t('title')
        }}</span>
      </div>
      <div class="row">
        <nav class="header-modes">
          <button
            type="button"
            :class="{ active: mode === 'editor' }"
            :disabled="busy"
            @click="mode = 'editor'"
          >
            {{ t('editorMode') }}</button
          ><button
            type="button"
            :class="{ active: mode === 'users' }"
            :disabled="busy"
            @click="mode = 'users'"
          >
            {{ t('users') }}
          </button>
        </nav>
        <ReleaseControl :api="api" @failure="report" />
        <span v-if="dirty && mode === 'users'" class="pill">{{ t('unsaved') }}</span
        ><span class="admin-id">#{{ session.user_id }}</span
        ><button type="button" class="text-button" :disabled="busy" @click="signOut">
          {{ t('logout') }}
        </button>
      </div>
    </header>
    <UserMonitor v-if="mode === 'users'" :api="api" :catalog="catalog" @failure="report" />
    <div v-else class="workspace">
      <aside class="sidebar">
        <div class="row between sidebar-heading">
          <span class="eyebrow">{{ t('flows') }}</span
          ><button
            type="button"
            class="sidebar-add"
            :aria-label="t('newFlow')"
            :disabled="busy"
            @click="newModal = true"
          >
            ＋
          </button>
        </div>
        <div class="flow-list">
          <button
            v-for="flow in flows"
            :key="flow.id"
            type="button"
            :disabled="busy"
            class="flow-item"
            :class="{ active: document?.id === flow.id }"
            @click="choose(flow.id)"
          >
            <span class="flow-list-icon">▤</span
            ><span
              ><strong>{{ flow.id }}</strong
              ><small
                ><span :class="['status-dot', { 'is-published': flow.published_version }]" />{{
                  flow.published_version ? 'v' + flow.published_version : t('draft')
                }}</small
              ></span
            >
          </button>
        </div>
        <div class="sidebar-footer">
          <span class="online-dot" />{{ t('title') }}<small>Vue Flow · v1</small>
        </div>
      </aside>
      <main class="editor-main">
        <template v-if="document">
          <div class="editor-toolbar">
            <div class="flow-heading">
              <div class="row">
                <h1>{{ document.id }}</h1>
                <span class="pill">{{ t('draft') }} · r{{ revision }}</span>
              </div>
              <span class="save-state" :class="{ dirty }"
                ><span class="status-dot" />{{ dirty ? t('unsaved') : t('saved')
                }}<span v-if="published" class="published-label">
                  · {{ t('published') }} v{{ published }}</span
                ></span
              >
            </div>
            <div class="toolbar-actions">
              <button type="button" :disabled="busy" @click="history">{{ t('versions') }}</button
              ><button type="button" :disabled="busy" @click="validate">✓ {{ t('validate') }}</button
              ><button type="button" class="secondary" :disabled="busy || !dirty" @click="save">
                {{ t('save') }}</button
              ><button type="button" class="primary" :disabled="busy || dirty" @click="publish">
                ↥ {{ t('publish') }}
              </button>
            </div>
          </div>
          <div v-if="notice" class="notice-bar" :class="{ error: isError }" role="status">
            <span>{{ t(notice) }}</span
            ><button v-if="notice === 'conflict'" type="button" :disabled="busy" @click="reload">
              {{ t('reload') }}</button
            ><button type="button" class="icon-button" :aria-label="t('close')" @click="notice = null">
              ×
            </button>
          </div>
          <div v-if="showVersions" class="versions-panel">
            <div class="row between">
              <strong>{{ t('versions') }}</strong
              ><button
                type="button"
                class="icon-button"
                :aria-label="t('close')"
                @click="showVersions = false"
              >
                ×
              </button>
            </div>
            <div v-for="version in versions" :key="version.version" class="version-row">
              <strong>v{{ version.version }}</strong
              ><span
                >r{{ version.draft_revision }} ·
                {{ new Date(version.published_at).toLocaleString(uiLocale) }}</span
              ><span v-if="version.version === published" class="pill success">{{ t('published') }}</span
              ><button v-else type="button" class="small" :disabled="busy" @click="activate(version.version)">
                {{ t('activate') }}
              </button>
            </div>
          </div>
          <div class="editor-body">
            <section class="graph-area" :aria-label="t('flows')">
              <div class="palette">
                <button
                  v-for="kind in kinds"
                  :key="kind"
                  type="button"
                  :class="kind"
                  :disabled="busy || document.nodes.length >= 200"
                  @click="add(kind)"
                >
                  <span class="palette-dot" />＋ {{ t(kind) }}
                </button>
              </div>
              <VueFlow
                :key="document.id"
                :nodes="graphNodes"
                :edges="graphEdges"
                :nodes-draggable="!busy"
                :nodes-connectable="!busy"
                :delete-key-code="null"
                :min-zoom="0.15"
                :max-zoom="2"
                fit-view-on-init
                @node-click="selected = $event.node.id"
                @pane-click="selected = null"
                @connect="connected"
                @node-drag-stop="dragged"
              >
                <template #node-flow="nodeProps"><FlowGraphNode v-bind="nodeProps" /></template
                ><Background pattern-color="#dce1ea" :gap="22" :size="1" /><Controls
                  :show-interactive="false"
                />
              </VueFlow>
              <div class="graph-caption">{{ t('connectHint') }}</div>
              <span class="node-count">{{ document.nodes.length }} / 200</span>
            </section>
            <aside class="properties-panel">
              <div class="panel-tabs">
                <button
                  v-for="tab in ['settings', 'preview', 'fields'] as const"
                  :key="tab"
                  type="button"
                  :class="{ active: panel === tab }"
                  @click="panel = tab"
                >
                  {{ t(tab) }}
                </button>
              </div>
              <fieldset :disabled="busy" class="properties-form" @input="touch">
                <NodeInspector
                  v-if="panel === 'settings' && node"
                  :key="node.id"
                  :node="node"
                  :document="document"
                  :catalog="catalog"
                  :delegates="delegates"
                  @rename="rename"
                  @delete="removeNode"
                  @entry="document!.entry = node!.id"
                />
                <div v-else-if="panel === 'settings'" class="empty-inspector">
                  <span>◇</span>
                  <p>{{ t('noNode') }}</p>
                </div>
                <FieldsEditor v-else-if="panel === 'fields'" :document="document" />
                <PreviewPane
                  v-else
                  :document="document"
                  :api="api"
                  :catalog="catalog"
                  :delegates="delegates"
                  @failure="report"
                  @select="selected = $event"
                />
              </fieldset>
            </aside>
          </div>
          <div v-if="issues.length" class="issues-panel">
            <strong>{{ t('issues') }} · {{ issues.length }}</strong
            ><button v-for="(issue, index) in issues" :key="index" type="button" @click="focusIssue(issue)">
              <span class="error-dot">!</span><code>{{ issue.code }}</code
              ><span>{{ issue.path }}</span>
            </button>
          </div>
          <footer class="editor-footer">
            <div class="row">
              <button type="button" class="text-button" :disabled="busy" @click="exportJson">
                {{ t('exportFlow') }}</button
              ><label class="import-button"
                >{{ t('importFlow')
                }}<input type="file" accept=".json,application/json" :disabled="busy" @change="importJson"
              /></label>
            </div>
            <code :title="t('telegramHint')">/flow_demo {{ document.id }}</code>
          </footer>
        </template>
        <div v-else class="onboarding">
          <p v-if="notice" class="notice error" role="status">{{ t(notice) }}</p>
          <span class="onboarding-icon">◇</span><span class="eyebrow">{{ t('noFlows') }}</span>
          <h1>{{ t('startHere') }}</h1>
          <p>{{ t('newHint') }}</p>
          <button type="button" class="primary" :disabled="busy" @click="newModal = true">
            ＋ {{ t('newFlow') }}
          </button>
        </div>
      </main>
    </div>
    <div v-if="newModal" class="modal-backdrop" @click.self="newModal = false">
      <form class="modal" role="dialog" aria-modal="true" :aria-label="t('newFlow')" @submit.prevent="create">
        <h2>{{ t('newFlow') }}</h2>
        <p v-if="notice && isError" class="notice error" role="status">{{ t(notice) }}</p>
        <label
          >{{ t('flowId')
          }}<input
            v-model="newId"
            autofocus
            required
            pattern="[a-z][a-z0-9_]{0,31}"
            :placeholder="'student_form'"
        /></label>
        <p class="hint">{{ t('invalidId') }}</p>
        <div class="row end">
          <button type="button" :disabled="busy" @click="newModal = false">{{ t('cancel') }}</button
          ><button type="submit" class="primary" :disabled="busy || !identifier.test(newId)">
            {{ t('create') }}
          </button>
        </div>
      </form>
    </div>
    <ConfirmDialog
      v-if="confirmation"
      :message="confirmation.message"
      :detail="confirmation.detail"
      @answer="answer"
    />
  </div>
</template>
