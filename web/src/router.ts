import { createRouter, createWebHistory } from 'vue-router'

import PlatformHome from './views/PlatformHome.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'home', component: PlatformHome }],
})

