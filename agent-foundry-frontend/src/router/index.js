import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const routes = [
  { path: '/', component: () => import('@/views/HomeView.vue'), name: 'home' },
  { path: '/marketplace', component: () => import('@/views/MarketplaceView.vue'), name: 'marketplace' },
  { path: '/marketplace/chains', component: () => import('@/views/ChainMarketplaceView.vue'), name: 'chain-marketplace' },
  { path: '/marketplace/chains/:id', component: () => import('@/views/ChainDetailView.vue'), name: 'chain-detail' },
  { path: '/agents/:id', component: () => import('@/views/AgentDetailView.vue'), name: 'agent-detail' },
  { path: '/purchase/success', component: () => import('@/views/PurchaseSuccessView.vue'), name: 'purchase-success' },
  { path: '/run/:id?', component: () => import('@/views/RunAgentView.vue'), name: 'run-agent', meta: { requiresAuth: true } },
  { path: '/runs', component: () => import('@/views/RunHistoryView.vue'), name: 'runs', meta: { requiresAuth: true } },
  { path: '/wizard', component: () => import('@/views/WizardView.vue'), name: 'wizard', meta: { requiresAuth: true } },
  { path: '/share/run/:token', component: () => import('@/views/SharedRunView.vue'), name: 'shared-run' },
  { path: '/chains', component: () => import('@/views/ChainsListView.vue'), name: 'chains', meta: { requiresAuth: true } },
  { path: '/chains/new', component: () => import('@/views/ChainBuilderView.vue'), name: 'chain-new', meta: { requiresAuth: true } },
  { path: '/chains/:id/edit', component: () => import('@/views/ChainBuilderView.vue'), name: 'chain-edit', meta: { requiresAuth: true } },
  { path: '/settings/keys', component: () => import('@/views/ApiKeysView.vue'), name: 'api-keys', meta: { requiresAuth: true } },
  { path: '/workspaces/:id/settings', component: () => import('@/views/WorkspaceSettingsView.vue'), name: 'workspace-settings', meta: { requiresAuth: true } },
  { path: '/login', component: () => import('@/views/LoginView.vue'), name: 'login' },
  { path: '/auth/callback', component: () => import('@/views/AuthCallbackView.vue'), name: 'auth-callback' },
  { path: '/register', component: () => import('@/views/RegisterView.vue'), name: 'register' },
  {
    path: '/admin',
    component: () => import('@/views/AdminPanelView.vue'),
    name: 'admin',
    meta: { requiresAuth: true, requiresAdminOrMod: true },
  },
  {
    path: '/admin/review/:id',
    component: () => import('@/views/AdminReviewAgentView.vue'),
    name: 'admin-review',
    meta: { requiresAuth: true, requiresAdminOrMod: true },
  },
  {
    path: '/admin/review-chain/:id',
    component: () => import('@/views/AdminReviewChainView.vue'),
    name: 'admin-review-chain',
    meta: { requiresAuth: true, requiresAdminOrMod: true },
  },
  {
    path: '/admin/accept-invite',
    component: () => import('@/views/AdminAcceptInviteView.vue'),
    name: 'admin-accept-invite',
  },
  {
    path: '/admin/wizard',
    component: () => import('@/views/AdminWizardUseCasesView.vue'),
    name: 'admin-wizard',
    meta: { requiresAuth: true, requiresAdminOrMod: true },
  },
  {
    path: '/dashboard',
    component: () => import('@/views/DashboardView.vue'),
    name: 'dashboard',
    meta: { requiresAuth: true },
    children: [
      { path: 'agents', component: () => import('@/views/AgentManagementView.vue'), name: 'dashboard-agents' },
      { path: 'agents/create', component: () => import('@/views/CreateAgentView.vue'), name: 'create-agent' },
      { path: 'agents/:id/edit', component: () => import('@/views/CreateAgentView.vue'), name: 'edit-agent' },
      { path: 'wallets', component: () => import('@/views/ActionWalletsView.vue'), name: 'dashboard-wallets' },
      { path: 'drafts', component: () => import('@/views/ContentDraftsView.vue'), name: 'dashboard-drafts' },
      { path: 'personality', component: () => import('@/views/PersonalityView.vue'), name: 'dashboard-personality' },
      { path: 'settings', component: () => import('@/views/ExpertSettingsView.vue'), name: 'dashboard-settings' }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login', query: to.fullPath ? { redirect: to.fullPath } : {} })
    return
  }
  if (to.meta.requiresAdminOrMod && authStore.isAuthenticated) {
    if (!authStore.user) await authStore.fetchUser()
    const role = authStore.user?.role
    if (role !== 'admin' && role !== 'moderator') {
      next({ name: 'home' })
    } else {
      next()
    }
    return
  }
  if (to.name === 'dashboard' && authStore.isAuthenticated) {
    try {
      const { data } = await api.get('/wizard/status')
      if (data?.runs_count === 0) {
        next({ name: 'wizard' })
        return
      }
    } catch (_) {
      // ignore; continue to dashboard
    }
  }
  next()
})

export default router
