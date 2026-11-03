<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Button, Document, FlowNode, Schemas, Scalar, Value } from '../types'
import { identifier, inline, uniqueId } from '../types'
import { t } from '../i18n'
import TextEditor from './TextEditor.vue'
import ButtonsEditor from './ButtonsEditor.vue'
import ConditionEditor from './ConditionEditor.vue'
import ValueEditor from './ValueEditor.vue'
import TargetSelect from './TargetSelect.vue'
import JsonField from './JsonField.vue'
import BindingsEditor from './BindingsEditor.vue'
import RichScreenEditor from './RichScreenEditor.vue'
const props = defineProps<{
  node: FlowNode
  document: Document
  catalog: Schemas['EditorCatalog']
  delegates: Schemas['DelegateDefinition'][]
}>()
const emit = defineEmits<{ rename: [string]; delete: []; entry: [] }>()
const id = ref(props.node.id)
const resultName = ref('')
const outcomeName = ref('')
watch(
  () => props.node.id,
  (value) => {
    id.value = value
    resultName.value = ''
    outcomeName.value = ''
  },
)
const nodes = computed(() => props.document.nodes.map((node) => node.id))
const fields = computed(() => Object.keys(props.document.fields ?? {}))
const definition = computed(() =>
  props.node.kind === 'action'
    ? props.delegates.find(
        (item) =>
          props.node.kind === 'action' &&
          item.id === props.node.delegate &&
          item.version === (props.node.contract_version ?? 1),
      )
    : undefined,
)
function setDelegate(delegate: string) {
  if (props.node.kind !== 'action') return
  const item = props.delegates.find((item) => item.id === delegate)
  if (!item) return
  const defaults: Record<string, Scalar> = {
    text: '',
    integer: 0,
    number: 0,
    boolean: false,
    list: [],
    object: {},
    secret: null,
  }
  props.node.delegate = delegate
  props.node.contract_version = item.version ?? 1
  props.node.arguments = Object.fromEntries(
    Object.entries(item.inputs ?? {}).map(([name, field]) => [
      name,
      name === 'user_id'
        ? { kind: 'ref', scope: 'user', field: 'id' }
        : { kind: 'literal', value: field.nullable ? null : defaults[field.type] },
    ]),
  )
  props.node.results = {}
  props.node.outcomes = Object.fromEntries(
    item.outcomes.map((outcome) => [
      outcome,
      nodes.value.find((id) => id !== props.node.id) ?? props.node.id,
    ]),
  )
}
function inputType(event: Event) {
  if (props.node.kind !== 'input') return
  props.node.input_type = (event.target as HTMLSelectElement).value as Extract<
    FlowNode,
    { kind: 'input' }
  >['input_type']
  if (['contact', 'media', 'secret'].includes(props.node.input_type)) props.document.schema_version = 2
  if (props.node.input_type !== 'media') props.node.multiple = false
  props.node.choices = props.node.input_type === 'choice' ? [''] : []
  if (props.node.input_type !== 'integer') {
    props.node.minimum = null
    props.node.maximum = null
  }
}
function endStatus(event: Event) {
  if (props.node.kind !== 'end') return
  props.node.status = (event.target as HTMLSelectElement).value as 'completed' | 'cancelled' | 'handed_off'
  props.node.feature =
    props.node.status === 'handed_off'
      ? (props.catalog.features?.find((item) => item.enabled)?.id ?? null)
      : null
  if (props.node.status === 'handed_off') props.node.return_flow = null
}
function addResult() {
  if (props.node.kind !== 'call' || !identifier.test(resultName.value)) return
  const results = (props.node.results ??= {})
  if (resultName.value in results || !fields.value.length) return
  results[resultName.value] = fields.value[0]
  resultName.value = ''
}
function addOutcome() {
  if (props.node.kind !== 'call' || !identifier.test(outcomeName.value)) return
  if (outcomeName.value in props.node.outcomes) return
  props.node.outcomes[outcomeName.value] = nodes.value.find((id) => id !== props.node.id) ?? props.node.id
  outcomeName.value = ''
}
function addRepeated() {
  if (props.node.kind !== 'menu' || (props.node.repeated?.length ?? 0) >= 20) return
  props.document.schema_version = 2
  const source =
    Object.entries(props.document.fields ?? {}).find(
      ([, field]) => field.type === 'list' && field.items?.type === 'object',
    )?.[0] ??
    fields.value[0] ??
    'items'
  const used = [
    ...props.node.buttons.flat(),
    ...(props.node.repeated ?? []).flatMap((group) => group.buttons),
  ].map((button) => button.id)
  ;(props.node.repeated ??= []).push({
    source: { kind: 'ref', scope: 'data', field: source },
    buttons: [
      {
        kind: 'transition',
        id: uniqueId('action', used),
        label: inline(t('continue')),
        target: nodes.value.find((id) => id !== props.node.id) ?? props.node.id,
        assignments: {},
      },
    ],
  })
}
function repeatedSource(index: number, value: Value) {
  if (props.node.kind !== 'menu' || value.kind !== 'ref') return
  props.node.repeated![index].source = { ...value, scope: 'data' }
}
function repeatedButtons(index: number, rows: Button[][]) {
  if (props.node.kind !== 'menu') return
  props.node.repeated![index].buttons = rows[0] ?? []
}
</script>
<template>
  <div class="inspector-content stack">
    <div class="row between">
      <span class="kind-badge" :class="node.kind">{{ t(node.kind) }}</span
      ><button
        class="icon-button danger"
        type="button"
        :aria-label="t('delete')"
        :disabled="document.nodes.length < 2"
        @click="emit('delete')"
      >
        ×
      </button>
    </div>
    <label
      >{{ t('nodeId') }}
      <div class="row">
        <input v-model="id" pattern="[a-z][a-z0-9_]{0,31}" required /><button
          type="button"
          class="small"
          :disabled="id === node.id"
          @click="emit('rename', id)"
        >
          {{ t('rename') }}
        </button>
      </div></label
    >
    <button v-if="document.entry !== node.id" class="text-button" type="button" @click="emit('entry')">
      ◎ {{ t('setEntry') }}</button
    ><span v-else class="hint">◎ {{ t('entry') }}</span>
    <template
      v-if="node.kind === 'menu' || node.kind === 'input' || node.kind === 'end' || node.kind === 'return'"
    >
      <div v-for="(_, index) in node.text ?? []" :key="index" class="stack text-block">
        <TextEditor v-model="node.text![index]" :catalog="catalog" :fields="fields" :label="t('text')" />
        <button
          v-if="(node.text?.length ?? 0) > 1 || node.kind === 'end' || node.kind === 'return'"
          type="button"
          class="text-button danger"
          @click="node.text?.splice(index, 1)"
        >
          {{ t('remove') }}
        </button>
      </div>
      <button
        type="button"
        class="small"
        :disabled="(node.text?.length ?? 0) >= 8"
        @click="(node.text ??= []).push(inline(t('text')))"
      >
        ＋ {{ t('addText') }}
      </button>
    </template>
    <label v-if="node.kind === 'menu'"
      >{{ t('keyboard')
      }}<select v-model="node.keyboard">
        <option value="inline">{{ t('inline') }}</option>
        <option value="reply">{{ t('reply') }}</option>
      </select></label
    >
    <template v-if="node.kind === 'input'">
      <label
        >{{ t('field')
        }}<select v-model="node.field">
          <option v-if="!fields.includes(node.field)">{{ node.field }}</option>
          <option v-for="field in fields" :key="field">{{ field }}</option>
        </select></label
      >
      <label
        >{{ t('type')
        }}<select :value="node.input_type" @change="inputType">
          <option>text</option>
          <option>integer</option>
          <option>choice</option>
          <option>contact</option>
          <option>media</option>
          <option>secret</option>
        </select></label
      >
      <label v-if="node.input_type === 'media'" class="check">
        <input v-model="node.multiple" type="checkbox" />{{ t('collectMedia') }}
      </label>
      <div class="row">
        <label
          >{{ t('minLength')
          }}<input v-model.number="node.min_length" type="number" min="0" required /></label
        ><label
          >{{ t('maxLength')
          }}<input v-model.number="node.max_length" type="number" min="1" max="4000" required
        /></label>
      </div>
      <div v-if="node.input_type === 'integer'" class="row">
        <label
          >{{ t('minimum')
          }}<input
            :value="node.minimum"
            type="number"
            @input="
              node.minimum =
                ($event.target as HTMLInputElement).value === ''
                  ? null
                  : Number(($event.target as HTMLInputElement).value)
            " /></label
        ><label
          >{{ t('maximum')
          }}<input
            :value="node.maximum"
            type="number"
            @input="
              node.maximum =
                ($event.target as HTMLInputElement).value === ''
                  ? null
                  : Number(($event.target as HTMLInputElement).value)
            "
        /></label>
      </div>
      <JsonField
        v-if="node.input_type === 'choice'"
        :model-value="node.choices ?? []"
        :label="t('choices')"
        @update:model-value="node.choices = $event as Scalar[]"
      />
      <TargetSelect v-model="node.next" :nodes="nodes" :label="t('next')" />
      <TextEditor v-model="node.error" :catalog="catalog" :fields="fields" :label="t('errorText')" />
    </template>
    <RichScreenEditor
      v-if="node.kind === 'menu' || node.kind === 'input'"
      :key="node.id"
      :node="node"
      :catalog="catalog"
      :fields="fields"
      @change="document.schema_version = 2"
    />
    <ButtonsEditor
      v-if="node.kind === 'menu' || node.kind === 'input'"
      :model-value="node.buttons ?? []"
      :nodes="nodes"
      :fields="fields"
      :catalog="catalog"
      :reply="node.kind === 'menu' && node.keyboard === 'reply'"
      @update:model-value="node.buttons = $event"
    />
    <section v-if="node.kind === 'menu'" class="stack">
      <div class="section-label">{{ t('repeatActions') }}</div>
      <div v-for="(group, index) in node.repeated ?? []" :key="index" class="binding stack">
        <div class="row between">
          <span class="section-label">#{{ index + 1 }}</span>
          <button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove') + ' ' + t('repeatActions') + ' ' + (index + 1)"
            @click="node.repeated!.splice(index, 1)"
          >
            ×
          </button>
        </div>
        <ValueEditor
          :model-value="group.source"
          :fields="fields"
          reference-only
          @update:model-value="repeatedSource(index, $event)"
        />
        <div :class="{ 'repeated-templates': group.buttons.length > 0 }">
          <ButtonsEditor
            :model-value="group.buttons.length ? [group.buttons] : []"
            :nodes="nodes"
            :fields="fields"
            :catalog="catalog"
            :reply="node.keyboard === 'reply'"
            @update:model-value="repeatedButtons(index, $event)"
          />
        </div>
      </div>
      <button type="button" class="small" :disabled="(node.repeated?.length ?? 0) >= 20" @click="addRepeated">
        ＋ {{ t('addRepeated') }}
      </button>
    </section>
    <template v-if="node.kind === 'condition'">
      <div v-for="(branch, index) in node.branches" :key="index" class="branch stack">
        <div class="row between">
          <span class="section-label">#{{ index + 1 }}</span
          ><button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove')"
            :disabled="node.branches.length < 2"
            @click="node.branches.splice(index, 1)"
          >
            ×
          </button>
        </div>
        <ConditionEditor v-model="branch.when" :fields="fields" /><TargetSelect
          v-model="branch.target"
          :nodes="nodes"
          :label="t('target')"
        />
      </div>
      <button
        type="button"
        class="small"
        :disabled="node.branches.length >= 16"
        @click="
          node.branches.push({
            when: { kind: 'exists', reference: { kind: 'ref', scope: 'user', field: 'id' } },
            target: document.entry,
          })
        "
      >
        ＋ {{ t('addBranch') }}
      </button>
      <TargetSelect v-model="node.default" :nodes="nodes" :label="t('otherwise')" />
    </template>
    <template v-if="node.kind === 'action'">
      <label
        >{{ t('delegate')
        }}<select :value="node.delegate" @change="setDelegate(($event.target as HTMLSelectElement).value)">
          <option v-if="!definition">{{ node.delegate }}</option>
          <option v-for="item in delegates" :key="item.id">{{ item.id }}</option>
        </select></label
      >
      <span class="hint">v{{ node.contract_version ?? 1 }} · {{ definition?.effect }}</span>
      <section v-if="definition?.effect === 'external' || node.waiting_text?.length" class="stack">
        <div class="section-label">{{ t('pendingText') }}</div>
        <div v-for="(_, index) in node.waiting_text ?? []" :key="index" class="stack text-block">
          <TextEditor
            v-model="node.waiting_text![index]"
            :catalog="catalog"
            :fields="fields"
            :label="t('pendingText')"
          />
          <button type="button" class="text-button danger" @click="node.waiting_text!.splice(index, 1)">
            {{ t('remove') }}
          </button>
        </div>
        <button
          type="button"
          class="small"
          :disabled="(node.waiting_text?.length ?? 0) >= 8"
          @click="(node.waiting_text ??= []).push(inline(t('pendingText')))"
        >
          ＋ {{ t('addText') }}
        </button>
      </section>
      <div class="section-label">{{ t('arguments') }}</div>
      <div v-for="(parameter, name) in definition?.inputs ?? {}" :key="name" class="binding">
        <code>{{ name }} · {{ parameter.type }}</code
        ><ValueEditor
          :model-value="node.arguments?.[name] ?? { kind: 'literal', value: null }"
          :fields="fields"
          @update:model-value="(node.arguments ??= {})[name] = $event"
        />
      </div>
      <div v-if="Object.keys(definition?.outputs ?? {}).length" class="section-label">{{ t('results') }}</div>
      <label v-for="(_, name) in definition?.outputs ?? {}" :key="name"
        >{{ name
        }}<select
          :value="node.results?.[name] ?? ''"
          @change="
            ($event.target as HTMLSelectElement).value
              ? ((node.results ??= {})[name] = ($event.target as HTMLSelectElement).value)
              : delete node.results?.[name]
          "
        >
          <option value="">—</option>
          <option v-for="field in fields" :key="field">{{ field }}</option>
        </select></label
      >
      <div class="section-label">{{ t('outcomes') }}</div>
      <TargetSelect
        v-for="(_, name) in node.outcomes"
        :key="name"
        v-model="node.outcomes[name]"
        :nodes="nodes"
        :label="name"
      />
    </template>
    <template v-if="node.kind === 'call' || node.kind === 'replace'">
      <label
        >{{ t('triggerTarget') }}<input v-model="node.flow" pattern="[a-z][a-z0-9_]{0,31}" required
      /></label>
      <BindingsEditor
        :model-value="node.arguments ?? {}"
        :fields="fields"
        :label="t('arguments')"
        @update:model-value="node.arguments = $event"
      />
    </template>
    <template v-if="node.kind === 'call'">
      <div class="section-label">{{ t('results') }}</div>
      <div v-for="(field, name) in node.results ?? {}" :key="name" class="binding">
        <div class="row">
          <label
            >{{ name
            }}<select v-model="node.results![name]" required>
              <option v-if="!fields.includes(field)">{{ field }}</option>
              <option v-for="candidate in fields" :key="candidate">{{ candidate }}</option>
            </select></label
          ><button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove') + ' ' + name"
            @click="delete node.results![name]"
          >
            ×
          </button>
        </div>
      </div>
      <div class="row">
        <input
          v-model="resultName"
          :aria-label="t('results')"
          :placeholder="t('field')"
          @keydown.enter.prevent="addResult"
        /><button
          type="button"
          class="small"
          :disabled="!identifier.test(resultName) || resultName in (node.results ?? {}) || !fields.length"
          :aria-label="t('addField')"
          @click="addResult"
        >
          ＋
        </button>
      </div>
      <div class="section-label">{{ t('outcomes') }}</div>
      <div v-for="(_, name) in node.outcomes" :key="name" class="row">
        <TargetSelect v-model="node.outcomes[name]" :nodes="nodes" :label="name" />
        <button
          type="button"
          class="icon-button danger"
          :aria-label="t('remove') + ' ' + name"
          :disabled="Object.keys(node.outcomes).length < 2"
          @click="delete node.outcomes[name]"
        >
          ×
        </button>
      </div>
      <div class="row">
        <input
          v-model="outcomeName"
          :aria-label="t('outcome')"
          :placeholder="t('outcome')"
          @keydown.enter.prevent="addOutcome"
        /><button
          type="button"
          class="small"
          :disabled="!identifier.test(outcomeName) || outcomeName in node.outcomes"
          :aria-label="t('addBranch')"
          @click="addOutcome"
        >
          ＋
        </button>
      </div>
    </template>
    <template v-if="node.kind === 'return'">
      <label
        >{{ t('outcome')
        }}<select v-model="node.outcome">
          <option v-if="!(document.outcomes ?? ['completed']).includes(node.outcome)">
            {{ node.outcome }}
          </option>
          <option v-for="outcome in document.outcomes ?? ['completed']" :key="outcome">{{ outcome }}</option>
        </select></label
      >
      <BindingsEditor
        :model-value="node.values ?? {}"
        :fields="fields"
        :label="t('returnValues')"
        @update:model-value="node.values = $event"
      />
    </template>
    <template v-if="node.kind === 'end'">
      <label
        >{{ t('status')
        }}<select :value="node.status" @change="endStatus">
          <option value="completed">{{ t('completed') }}</option>
          <option value="cancelled">{{ t('cancelled') }}</option>
          <option value="handed_off">{{ t('handoff') }}</option>
        </select></label
      >
      <label v-if="node.status !== 'handed_off'"
        >{{ t('returnFlow')
        }}<input
          v-model="node.return_flow"
          placeholder="main_menu"
          @change="node.return_flow ||= null" /></label
      ><label v-if="node.status === 'handed_off'"
        >{{ t('feature')
        }}<select v-model="node.feature" required>
          <option
            v-for="feature in catalog.features ?? []"
            :key="feature.id"
            :disabled="!feature.enabled"
            :value="feature.id"
          >
            {{ feature.id }}
          </option>
        </select></label
      >
    </template>
  </div>
</template>
<style scoped>
.repeated-templates :deep(section > button.secondary) {
  display: none;
}
</style>
