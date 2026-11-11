import {
  backButton, init, initData, isTMA, miniApp, retrieveLaunchParamsFp, themeParams, useSignal, viewport,
} from '@tma.js/sdk-vue'
import {
  computed, inject, onMounted, onScopeDispose, provide, shallowRef, watch, watchEffect,
  type InjectionKey, type Ref,
} from 'vue'
import { useRouter } from 'vue-router'

function useTelegramState() {
  const rawInitData = useSignal(initData.raw)
  const user = useSignal(initData.user)
  return {
    rawInitData,
    languageCode: computed(() => user.value?.language_code?.split('-')[0] ?? 'en'),
    dialogBack: shallowRef<(() => void) | undefined>(),
  }
}

const telegramKey: InjectionKey<ReturnType<typeof useTelegramState>> = Symbol('telegram')

export function useTelegramProvider() {
  const router = useRouter()
  const cleanups: (() => void)[] = []
  const available = isTMA() && retrieveLaunchParamsFp()._tag === 'Right'
  if (available) {
    cleanups.push(init({ acceptCustomStyles: false }))
    initData.restore()
    themeParams.mount()
    cleanups.push(themeParams.unmount)
    backButton.mount.ifAvailable()
    cleanups.push(() => { backButton.hide.ifAvailable(); backButton.unmount() })
    viewport.expand.ifAvailable()
  }

  const context = useTelegramState()
  const dark = useSignal(themeParams.isDark)
  const parentRoute = computed(() => {
    const route = router.currentRoute.value
    const backTo = route.meta.backTo
    return typeof backTo === 'function' ? backTo(route) : backTo
  })
  watchEffect(() => {
    document.documentElement.dataset.theme = available && dark.value ? 'dark' : 'light'
    if (available) {
      if (context.dialogBack.value || parentRoute.value) backButton.show.ifAvailable()
      else backButton.hide.ifAvailable()
    }
  })
  if (available && backButton.onClick.isAvailable()) {
    cleanups.push(backButton.onClick(() => {
      if (context.dialogBack.value) context.dialogBack.value()
      else if (parentRoute.value) {
        const previous = router.options.history.state.back
        if (typeof previous === 'string' && previous.startsWith('/') && !previous.startsWith('//')) router.back()
        else void router.replace({ name: parentRoute.value })
      }
    }))
  }
  provide(telegramKey, context)

  let disposed = false
  const controller = new AbortController()
  if (available) {
    void viewport.mount({ timeout: 2000, abortSignal: controller.signal }).then(() => {
      if (!disposed) cleanups.push(viewport.bindCssVars())
    }).catch(() => {
      // Missing viewport support must not prevent authentication or public terms.
    })
  }
  onMounted(() => { if (available) miniApp.ready.ifAvailable() })
  onScopeDispose(() => {
    disposed = true
    controller.abort()
    cleanups.reverse().forEach(cleanup => cleanup())
  })
}

export function useTelegram() {
  const context = inject(telegramKey)
  if (!context) throw new Error('Telegram integration is not initialized')
  return context
}

export function useTelegramDialogBack(active: Readonly<Ref<boolean>>, close: () => void) {
  const { dialogBack } = useTelegram()
  const clear = () => { if (dialogBack.value === close) dialogBack.value = undefined }
  watch(active, value => { if (value) dialogBack.value = close; else clear() }, { immediate: true, flush: 'sync' })
  onScopeDispose(clear)
}
