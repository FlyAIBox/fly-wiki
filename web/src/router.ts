import { createRouter, createWebHistory } from 'vue-router'

import EditableNoteEditor from './views/EditableNoteEditor.vue'
import PlatformHome from './views/PlatformHome.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: PlatformHome },
    { path: '/notes/:noteId', name: 'note', component: EditableNoteEditor },
  ],
})

