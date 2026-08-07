<template>
  <t-layout class="app-shell">
    <t-header class="app-header">
      <router-link class="brand" to="/" aria-label="FlyWiki 首页">
        <span class="brand-mark">F</span>
        <span>FlyWiki</span>
      </router-link>
      <span class="stage-label">M0 · 自托管知识工作台</span>
    </t-header>
    <t-content class="app-content">
      <router-view />
    </t-content>
  </t-layout>
</template>

