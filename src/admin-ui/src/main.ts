import { createApp } from 'vue'
import App from './App.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import './style.css'

const ticket = new URLSearchParams(location.hash.slice(1)).get('ticket')
history.replaceState(null, '', location.pathname)
createApp(App, { ticket }).mount('#app')
