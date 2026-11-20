import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './shared/styles/base.css'
import './shared/styles/theme.css'
import './shared/styles/controls.css'

createApp(App).use(router).mount('#app')
