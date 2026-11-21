import { createRouter, createWebHistory, type RouteLocationNormalizedLoaded } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    backTo?: string | ((route: RouteLocationNormalizedLoaded) => string)
  }
}

const achievements = () => import('./pages/AchievementsPage.vue')
const preferences = () => import('./pages/PreferencesPage.vue')

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: to => {
        const { view, ...query } = to.query
        const name = view === 'settings' || view === 'courses' || view === 'terms' ? view : 'achievements'
        return { name, query, hash: to.hash }
      },
    },
    { path: '/achievements', name: 'achievements', component: achievements, props: { tab: 'collection' } },
    { path: '/leaderboard', name: 'leaderboard', component: achievements, props: { tab: 'leaderboard' }, meta: { backTo: 'achievements' } },
    { path: '/settings', name: 'settings', component: preferences, props: { tab: 'settings' } },
    { path: '/courses', name: 'courses', component: preferences, props: { tab: 'courses' }, meta: { backTo: 'settings' } },
    { path: '/free-time', name: 'free-time', component: () => import('./pages/FreeTimePage.vue') },
    { path: '/admin', name: 'admin', component: () => import('./pages/admin/AdminUsersPage.vue') },
    { path: '/admin/achievements', name: 'admin-achievements', component: () => import('./pages/admin/AdminAchievementsPage.vue') },
    { path: '/admin/broadcasts', name: 'admin-broadcasts', component: () => import('./pages/admin/AdminBroadcastsPage.vue') },
    {
      path: '/admin/broadcasts/new', name: 'admin-broadcast-new',
      component: () => import('./pages/admin/AdminBroadcastComposePage.vue'), meta: { backTo: 'admin-broadcasts' },
    },
    {
      path: '/admin/broadcasts/:id', name: 'admin-broadcast',
      component: () => import('./pages/admin/AdminBroadcastDetailPage.vue'), meta: { backTo: 'admin-broadcasts' },
    },
    {
      path: '/terms', name: 'terms', component: () => import('./pages/TermsPage.vue'),
      meta: {
        backTo: route => {
          const from = route.query.from
          return from === 'achievements' || from === 'leaderboard' || from === 'courses' || from === 'free-time'
            ? from
            : 'settings'
        },
      },
    },
    { path: '/:pathMatch(.*)*', redirect: { name: 'achievements' } },
  ],
  scrollBehavior: (_to, _from, savedPosition) => savedPosition ?? { top: 0 },
})
