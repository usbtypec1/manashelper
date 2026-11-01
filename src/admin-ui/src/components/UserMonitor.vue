<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { AdminApi } from '../api'
import type { Document, Schemas } from '../types'
import { ports, textLabel } from '../types'
import { t, uiLocale, type CopyKey } from '../i18n'
import FlowGraphNode from './FlowGraphNode.vue'

const props = defineProps<{ api: AdminApi; catalog: Schemas['EditorCatalog'] }>()
const emit = defineEmits<{ failure: [unknown] }>()
type Location = Schemas['UserLocation']
type Transition = Schemas['UserTransition']
const locations = ref<Location[]>([]),
  selected = ref<Location | null>(null),
  transitions = ref<Transition[]>([])
const document = ref<Document | null>(null),
  version = ref<number | null>(null),
  historical = ref<Transition | null>(null)
const cursor = ref<string | null>(null),
  next = ref<string | null>(null),
  previous = ref<(string | null)[]>([])
const historyCursor = ref<string | null>(null),
  historyNext = ref<string | null>(null),
  historyPrevious = ref<(string | null)[]>([])
const search = ref(''),
  busy = ref(false),
  error = ref(false)
let timer: ReturnType<typeof setInterval> | undefined,
  alive = true
const ownerKey: Record<Location['owner'], CopyKey> = {
  runtime: 'ownerRuntime',
  legacy: 'ownerLegacy',
  unknown: 'ownerUnknown',
}
const deliveryKey: Record<string, CopyKey> = {
  pending: 'deliveryPending',
  sent: 'deliverySent',
  failed: 'deliveryFailed',
  unknown: 'deliveryUnknown',
}
const statusKey: Record<string, CopyKey> = {
  running: 'running',
  waiting_button: 'waitingButton',
  waiting_input: 'waitingInput',
  completed: 'completed',
  cancelled: 'cancelled',
  handed_off: 'handoffCompleted',
  failed: 'failed',
}
const marker = computed(() => historical.value?.to_step ?? selected.value?.node_id ?? null)
const step = computed(() => marker.value ?? selected.value?.legacy_state ?? selected.value?.handler ?? '—')
const graphNodes = computed(
  () =>
    document.value?.nodes.map((node, index) => ({
      id: node.id,
      type: 'flow',
      position: document.value?.layout?.[node.id] ?? {
        x: 80 + (index % 3) * 330,
        y: 80 + Math.floor(index / 3) * 350,
      },
      data: {
        kind: node.kind,
        title:
          'text' in node
            ? textLabel(node.text?.[0], uiLocale.value, props.catalog)
            : node.kind === 'action'
              ? node.delegate
              : '',
        ports: ports(node),
        entry: document.value?.entry === node.id,
        invalid: false,
        current: node.id === marker.value,
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
        })),
    ) ?? [],
)
function date(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString(uiLocale.value) : '—'
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = false
  try {
    await action()
  } catch (failure) {
    if (alive) {
      error.value = true
      emit('failure', failure)
    }
  } finally {
    if (alive) busy.value = false
  }
}
async function graph(flowId: string | null | undefined, number: number | null | undefined) {
  if (!flowId || !number) {
    document.value = null
    version.value = null
    return
  }
  if (document.value?.id === flowId && version.value === number) return
  const response = await props.api.request<Schemas['VersionContent']>(`/flows/${flowId}/versions/${number}`)
  if (alive) {
    document.value = response.document
    version.value = response.version
  }
}
async function history() {
  if (!selected.value) return
  const response = await props.api.request<Schemas['TransitionPage']>(
    `/users/${selected.value.user_id}/transitions?limit=25` +
      (historyCursor.value ? '&cursor=' + encodeURIComponent(historyCursor.value) : ''),
  )
  if (alive) {
    transitions.value = response.items
    historyNext.value = response.next_cursor
  }
}
async function detail(location: Location, reset = false) {
  if (reset || location.user_id !== selected.value?.user_id) {
    historyCursor.value = null
    historyPrevious.value = []
    historical.value = null
  }
  selected.value = location
  await history()
  if (!historical.value) await graph(location.flow_id, location.flow_version)
}
function refresh(reset = false) {
  void perform(async () => {
    const response = await props.api.request<Schemas['LocationPage']>(
      '/users/locations?limit=25' + (cursor.value ? '&cursor=' + encodeURIComponent(cursor.value) : ''),
    )
    if (!alive) return
    locations.value = response.items
    next.value = response.next_cursor
    const current =
      !reset && selected.value
        ? (response.items.find((item) => item.user_id === selected.value?.user_id) ??
          (await props.api.request<Location>(`/users/${selected.value.user_id}/location`)))
        : response.items[0]
    if (current) await detail(current, reset)
  })
}
function choose(location: Location) {
  void perform(() => detail(location, true))
}
function find() {
  void perform(async () => {
    if (!/^\d+$/.test(search.value) || Number(search.value) <= 0) return
    await detail(await props.api.request<Location>(`/users/${search.value}/location`), true)
  })
}
function page(forward: boolean) {
  if (forward && next.value) {
    previous.value.push(cursor.value)
    cursor.value = next.value
  } else if (!forward && previous.value.length) cursor.value = previous.value.pop() ?? null
  refresh(true)
}
function historyPage(forward: boolean) {
  void perform(async () => {
    if (forward && historyNext.value) {
      historyPrevious.value.push(historyCursor.value)
      historyCursor.value = historyNext.value
    } else if (!forward && historyPrevious.value.length)
      historyCursor.value = historyPrevious.value.pop() ?? null
    await history()
  })
}
function showTransition(item: Transition) {
  void perform(async () => {
    historical.value = item
    await graph(item.flow_id, item.flow_version)
  })
}
function current() {
  void perform(async () => {
    historical.value = null
    if (selected.value) await graph(selected.value.flow_id, selected.value.flow_version)
  })
}
onMounted(() => {
  refresh()
  timer = setInterval(() => {
    if (window.document.visibilityState === 'visible') refresh()
  }, 5000)
})
onBeforeUnmount(() => {
  alive = false
  clearInterval(timer)
})
</script>
<template>
  <main class="monitor">
    <header class="monitor-toolbar">
      <div>
        <h1>{{ t('users') }}</h1>
        <p class="hint">{{ t('monitorHint') }}</p>
      </div>
      <form class="row" @submit.prevent="find">
        <input
          v-model="search"
          :aria-label="t('userSearch')"
          :placeholder="t('userSearch')"
          inputmode="numeric"
          pattern="[0-9]+"
        /><button type="submit" :disabled="busy">{{ t('search') }}</button
        ><button type="button" :disabled="busy" @click="refresh()">{{ t('refresh') }}</button>
      </form>
    </header>
    <p v-if="error" class="notice error" role="status">{{ t('requestFailed') }}</p>
    <div class="monitor-workspace">
      <section class="user-list">
        <div class="user-table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>{{ t('currentStep') }}</th>
                <th>{{ t('locationStatus') }}</th>
                <th>{{ t('lastSeen') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="location in locations"
                :key="location.user_id"
                :class="{ active: location.user_id === selected?.user_id }"
              >
                <td>
                  <button type="button" :disabled="busy" @click="choose(location)">
                    #{{ location.user_id }}
                  </button>
                </td>
                <td>
                  <code>{{ location.node_id ?? location.legacy_state ?? location.handler ?? '—' }}</code>
                </td>
                <td>
                  <span class="owner-chip" :class="location.owner">{{ t(ownerKey[location.owner]) }}</span>
                </td>
                <td>{{ date(location.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!locations.length && !busy" class="hint centered">{{ t('noUsers') }}</p>
        </div>
        <div class="row between pagination">
          <button type="button" class="small" :disabled="busy || !previous.length" @click="page(false)">
            {{ t('previousPage') }}</button
          ><button type="button" class="small" :disabled="busy || !next" @click="page(true)">
            {{ t('nextPage') }}
          </button>
        </div>
      </section>
      <section v-if="selected" class="user-detail">
        <div class="location-heading">
          <div class="row between">
            <h2>#{{ selected.user_id }}</h2>
            <span class="owner-chip" :class="selected.owner">{{ t(ownerKey[selected.owner]) }}</span>
          </div>
          <div class="location-step">
            <span class="eyebrow">{{
              historical || selected.owner !== 'runtime' ? t('lastObserved') : t('currentStep')
            }}</span
            ><strong>{{ step }}</strong>
          </div>
          <div class="location-meta">
            <span v-if="selected.status">{{ t(statusKey[selected.status] ?? 'status') }}</span
            ><span
              >{{ t('delivery') }}:
              {{ selected.delivery_status ? t(deliveryKey[selected.delivery_status]) : '—' }}</span
            ><span>{{ date(selected.updated_at) }}</span>
          </div>
        </div>
        <div class="monitor-graph-heading row between">
          <span
            >{{ t('readOnly') }}<code v-if="document"> · {{ document.id }} · v{{ version }}</code></span
          ><button v-if="historical" type="button" class="text-button" :disabled="busy" @click="current">
            {{ t('currentStep') }}
          </button>
        </div>
        <div class="monitor-graph">
          <VueFlow
            v-if="document"
            :key="document.id + ':' + version"
            id="monitor"
            :nodes="graphNodes"
            :edges="graphEdges"
            :nodes-draggable="false"
            :nodes-connectable="false"
            :elements-selectable="false"
            :delete-key-code="null"
            :min-zoom="0.1"
            fit-view-on-init
            ><template #node-flow="nodeProps"><FlowGraphNode v-bind="nodeProps" /></template
            ><Background :gap="22" pattern-color="#dce1ea" /><Controls :show-interactive="false"
          /></VueFlow>
          <div v-else class="empty-inspector">
            <span>◇</span>
            <p>{{ t('lastObserved') }}: {{ selected.legacy_state ?? selected.handler ?? '—' }}</p>
          </div>
        </div>
        <div class="history-heading row between">
          <strong>{{ t('history') }}</strong>
          <div class="row">
            <button
              type="button"
              class="small"
              :disabled="busy || !historyPrevious.length"
              @click="historyPage(false)"
            >
              {{ t('previousPage') }}</button
            ><button type="button" class="small" :disabled="busy || !historyNext" @click="historyPage(true)">
              {{ t('nextPage') }}
            </button>
          </div>
        </div>
        <div class="history-list">
          <button
            v-for="item in transitions"
            :key="item.id"
            type="button"
            :disabled="busy"
            :class="{ active: historical?.id === item.id }"
            @click="showTransition(item)"
          >
            <time>{{ date(item.occurred_at) }}</time
            ><code>{{ item.from_step ?? '—' }} → {{ item.to_step ?? '—' }}</code
            ><span>{{ item.outcome }}</span>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
