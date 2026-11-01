<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Text, Schemas, Locale, Theme, Value } from '../types'
import { clone, inline, locales } from '../types'
import { t, uiLocale } from '../i18n'
import BindingsEditor from './BindingsEditor.vue'
const props = defineProps<{
  modelValue: Text
  catalog: Schemas['EditorCatalog']
  fields: string[]
  label: string
}>()
const emit = defineEmits<{ 'update:modelValue': [Text] }>()
const locale = ref<Locale>(uiLocale.value)
const theme = ref<Theme>('basic')
const variant = computed(() => {
  const text = props.modelValue
  if (text.kind === 'catalog') {
    const item = props.catalog.texts.find((item) => item.key === text.key)
    return (
      (theme.value === 'halloween'
        ? item?.themes.halloween?.[locale.value]
        : item?.translations[locale.value]) ?? ''
    )
  }
  return (
    (theme.value === 'halloween'
      ? text.themes?.halloween?.[locale.value]
      : text.translations[locale.value]) ?? ''
  )
})
function setVariant(value: string) {
  if (props.modelValue.kind !== 'inline') return
  const text = clone(props.modelValue)
  text.themes ??= {}
  text.themes.halloween ??= {}
  const destination = theme.value === 'halloween' ? text.themes.halloween : text.translations
  if (value || (locale.value === 'en' && theme.value === 'basic')) destination[locale.value] = value
  else delete destination[locale.value]
  const expected = [...(text.translations.en ?? '').matchAll(/\{([a-z][a-z0-9_]*)\}/g)].map(
    (match) => match[1],
  )
  text.parameters = Object.fromEntries(
    expected.map((name) => [name, text.parameters?.[name] ?? { kind: 'literal', value: '' }]),
  )
  emit('update:modelValue', text)
}
function selectCatalog(key: string) {
  const template = props.catalog.texts.find((item) => item.key === key)?.translations.en ?? ''
  const parameters: Record<string, Value> = {}
  for (const match of template.matchAll(/\{([a-z][a-z0-9_]*)\}/g))
    parameters[match[1]] = { kind: 'literal', value: '' }
  emit('update:modelValue', { kind: 'catalog', key, parameters })
}
function custom() {
  const text = props.modelValue
  const item = text.kind === 'catalog' ? props.catalog.texts.find((item) => item.key === text.key) : null
  emit(
    'update:modelValue',
    item
      ? {
          kind: 'inline',
          translations: clone(item.translations),
          themes: clone(item.themes),
          parameters: clone(text.parameters ?? {}),
        }
      : inline(t('text')),
  )
}
</script>
<template>
  <div class="text-editor">
    <div class="row between">
      <span class="section-label">{{ label }}</span
      ><select
        class="compact"
        :aria-label="label + ' ' + t('type')"
        :value="modelValue.kind"
        @change="
          ($event.target as HTMLSelectElement).value === 'inline'
            ? custom()
            : selectCatalog(catalog.texts[0]?.key ?? '')
        "
      >
        <option value="inline">{{ t('customText') }}</option>
        <option value="catalog">{{ t('catalogText') }}</option>
      </select>
    </div>
    <select
      v-if="modelValue.kind === 'catalog'"
      :aria-label="t('catalogKey')"
      :value="modelValue.key"
      @change="selectCatalog(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="item in catalog.texts" :key="item.key" :value="item.key">{{ item.key }}</option>
    </select>
    <div class="row">
      <select v-model="locale" :aria-label="label + ' ' + t('locale')">
        <option v-for="code in locales" :key="code">{{ code }}</option></select
      ><select v-model="theme" :aria-label="label + ' ' + t('theme')">
        <option value="basic">{{ t('basic') }}</option>
        <option value="halloween">{{ t('halloween') }}</option>
      </select>
    </div>
    <textarea
      :aria-label="label"
      :value="variant"
      :readonly="modelValue.kind === 'catalog'"
      rows="4"
      @input="setVariant(($event.target as HTMLTextAreaElement).value)"
    />
    <p class="hint">{{ t('fallbackHint') }}</p>
    <BindingsEditor
      v-if="Object.keys(modelValue.parameters ?? {}).length"
      :model-value="modelValue.parameters ?? {}"
      :fields="fields"
      :label="t('parameters')"
      @update:model-value="emit('update:modelValue', { ...modelValue, parameters: $event })"
    />
  </div>
</template>
