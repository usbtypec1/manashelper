<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { t } from '../i18n'
defineProps<{ message: string; detail?: string }>()
const emit = defineEmits<{ answer: [boolean] }>()
const dialog = ref<HTMLDialogElement>()
onMounted(() => dialog.value?.showModal())
</script>
<template>
  <dialog ref="dialog" class="modal confirm-modal" @cancel.prevent="emit('answer', false)">
    <h2>{{ message }}</h2>
    <p v-if="detail" class="hint">{{ detail }}</p>
    <div class="row end">
      <button type="button" autofocus @click="emit('answer', false)">{{ t('cancel') }}</button
      ><button type="button" class="primary" @click="emit('answer', true)">{{ t('confirm') }}</button>
    </div>
  </dialog>
</template>
