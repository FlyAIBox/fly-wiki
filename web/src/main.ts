import TDesign from 'tdesign-vue-next'
import 'tdesign-vue-next/es/style/index.css'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import './style.css'

createApp(App).use(createPinia()).use(router).use(TDesign).mount('#app')

