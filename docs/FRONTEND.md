# NEYEN Frontend Architecture

**Version:** 1.0.0
**Last Updated:** March 2026
**Tech Stack:** TypeScript, Vue 3, Vite, Supabase Client, TailwindCSS

---

## Overview

The NEYEN frontend is a Progressive Web Application (PWA) that provides the user interface for the NEYEN methodology platform. It consumes the REST API documented in `API-ENDPOINTS.md` and interacts directly with Supabase for real-time features and authentication.

**Key Characteristics:**
- Single Page Application (SPA) architecture
- TypeScript-first development
- Reactive state management with Pinia
- Direct Supabase client integration for auth and realtime
- Offline-capable PWA with service workers
- Multi-language support (ES/EN) via i18n

---

## Tech Stack

### Core Framework
- **Vue 3** (Composition API)
- **TypeScript 5.x**
- **Vite 5.x** (build tool, dev server, HMR)

### State Management
- **Pinia** - Centralized state store
  - `authStore` - User session, OAuth tokens
  - `diagnosticStore` - E'A diagnostic data, temporal cycles
  - `workroomStore` - Active workroom state, collaboration
  - `notificationStore` - Real-time notifications

### Supabase Client Integration

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)
```

**Used for:**
- OAuth authentication (GitHub, Google)
- Real-time subscriptions (workroom updates, notifications)
- Direct database queries (user profiles, diagnostics)
- Storage access (file uploads, avatars)

### UI & Styling
- **TailwindCSS 3.x** - Utility-first CSS
- **Headless UI** - Accessible components
- **Heroicons** - Icon system
- **Custom design tokens** aligned with TSW brand (spiral motifs, Valencia palette)

### HTTP Client
- **Axios** - REST API calls to `api.neyen.app`
  - Interceptors for auth tokens
  - Request/response logging
  - Error handling middleware

### PWA & Offline
- **Vite PWA Plugin** - Service worker generation
- **Workbox** - Offline caching strategies
  - Cache-first for static assets
  - Network-first for API calls
  - Background sync for diagnostic submissions

### i18n
- **Vue I18n** - Multi-language support
  - Spanish (primary)
  - English (secondary)
  - Locale files in `/src/locales/`

---

## Project Structure

```
src/
├── assets/              # Static assets (images, fonts, SVG)
├── components/          # Reusable Vue components
│   ├── auth/            # Login, OAuth callbacks
│   ├── diagnostic/      # E'A framework forms, visualizations
│   ├── workroom/        # Collaborative workspace UI
│   └── shared/          # Buttons, modals, alerts
├── composables/         # Vue 3 composition functions
│   ├── useAuth.ts
│   ├── useDiagnostic.ts
│   └── useRealtime.ts
├── layouts/             # App layouts (authenticated, public)
├── locales/             # i18n translation files (es.json, en.json)
├── router/              # Vue Router configuration
├── stores/              # Pinia stores
├── utils/               # Helper functions, constants
├── views/               # Page-level components
│   ├── Dashboard.vue
│   ├── DiagnosticFlow.vue
│   ├── Workroom.vue
│   └── Settings.vue
├── App.vue              # Root component
└── main.ts              # Application entry point
```

---

## Authentication Flow

### GitHub OAuth
1. User clicks "Sign in with GitHub"
2. Frontend redirects to Supabase Auth URL:

```typescript
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'github',
  options: {
    redirectTo: 'https://thespiralwithin.ai/auth/callback'
  }
})
```

3. Supabase handles OAuth flow with GitHub
4. User redirected to `/auth/callback` with session token
5. Frontend stores session in Pinia `authStore` + localStorage
6. Access token attached to all API requests via Axios interceptor

### Google OAuth
Same flow as GitHub, provider = `'google'`

### Session Management

```typescript
// composables/useAuth.ts
export function useAuth() {
  const authStore = useAuthStore()

  const checkSession = async () => {
    const { data: { session } } = await supabase.auth.getSession()
    if (session) {
      authStore.setUser(session.user)
      authStore.setToken(session.access_token)
    }
  }

  supabase.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_IN') authStore.setUser(session.user)
    if (event === 'SIGNED_OUT') authStore.clearUser()
  })

  return { checkSession }
}
```

---

## API Integration

### Axios Instance Configuration

```typescript
// utils/api.ts
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL, // https://api.neyen.app/v1
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - attach auth token
api.interceptors.request.use(config => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// Response interceptor - handle errors
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Token expired, redirect to login
      useAuthStore().clearUser()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default api
```

### Example API Calls

```typescript
// Store: diagnosticStore
import api from '@/utils/api'

export const useDiagnosticStore = defineStore('diagnostic', {
  actions: {
    async createDiagnostic(payload: DiagnosticPayload) {
      const { data } = await api.post('/diagnostics', payload)
      this.currentDiagnostic = data
      return data
    },
    async fetchDiagnostics() {
      const { data } = await api.get('/diagnostics')
      this.diagnostics = data
    }
  }
})
```

---

## Real-time Features (Supabase)

### Workroom Collaboration

```typescript
// composables/useRealtime.ts
export function useWorkroomRealtime(workroomId: string) {
  const workroomStore = useWorkroomStore()

  const channel = supabase
    .channel(`workroom:${workroomId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'workroom_messages',
        filter: `workroom_id=eq.${workroomId}`
      },
      (payload) => {
        workroomStore.addMessage(payload.new)
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'workrooms',
        filter: `id=eq.${workroomId}`
      },
      (payload) => {
        workroomStore.updateWorkroom(payload.new)
      }
    )
    .subscribe()

  onUnmounted(() => {
    supabase.removeChannel(channel)
  })
}
```

### Notification System

```typescript
// Real-time notifications
const notificationChannel = supabase
  .channel('user-notifications')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'notifications',
      filter: `user_id=eq.${userId}`
    },
    (payload) => {
      notificationStore.addNotification(payload.new)
      // Show toast notification
      toast.info(payload.new.message)
    }
  )
  .subscribe()
```

---

## State Management (Pinia)

### authStore

```typescript
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: null as string | null,
    isAuthenticated: false
  }),
  actions: {
    setUser(user: User) {
      this.user = user
      this.isAuthenticated = true
      localStorage.setItem('user', JSON.stringify(user))
    },
    setToken(token: string) {
      this.token = token
      localStorage.setItem('token', token)
    },
    clearUser() {
      this.user = null
      this.token = null
      this.isAuthenticated = false
      localStorage.removeItem('user')
      localStorage.removeItem('token')
    }
  }
})
```

### diagnosticStore

```typescript
export const useDiagnosticStore = defineStore('diagnostic', {
  state: () => ({
    diagnostics: [] as Diagnostic[],
    currentDiagnostic: null as Diagnostic | null,
    temporalCycles: [] as TemporalCycle[]
  }),
  getters: {
    activeDiagnostic: (state) =>
      state.diagnostics.find(d => d.status === 'active')
  },
  actions: {
    async fetchDiagnostics() { /* ... */ },
    async createDiagnostic(payload: DiagnosticPayload) { /* ... */ },
    async calculateEA(diagnosticId: string) { /* ... */ }
  }
})
```

---

## Routing

### Route Configuration

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/PublicLayout.vue'),
    children: [
      { path: '', component: () => import('@/views/Landing.vue') },
      { path: 'login', component: () => import('@/views/Login.vue') }
    ]
  },
  {
    path: '/app',
    component: () => import('@/layouts/AuthenticatedLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'diagnostic', component: () => import('@/views/DiagnosticFlow.vue') },
      { path: 'workroom/:id', component: () => import('@/views/Workroom.vue') },
      { path: 'settings', component: () => import('@/views/Settings.vue') }
    ]
  },
  {
    path: '/auth/callback',
    component: () => import('@/views/AuthCallback.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

---

## Environment Variables

```bash
# .env.production
VITE_API_BASE_URL=https://api.neyen.app/v1
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_SENTRY_DSN=https://...@sentry.io/...
VITE_APP_ENV=production
```

---

## Build & Deployment

### Development
```bash
npm run dev          # Vite dev server at http://localhost:5173
```

### Production Build
```bash
npm run build        # TypeScript compilation + Vite build
npm run preview      # Preview production build locally
```

### PWA Assets Generation
```bash
npm run generate-pwa-assets   # Generate icons, splash screens
```

### Deployment to Hostinger
```bash
# Build generates dist/ folder
npm run build
# Upload dist/ to Hostinger via FTP or SSH
# Configure .htaccess for SPA routing
```

**`.htaccess` example:**
```apache
RewriteEngine On
RewriteBase /
RewriteRule ^index\.html$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.html [L]
```

---

## Testing Strategy

### Unit Tests (Vitest)
- Component logic testing
- Store actions/getters testing
- Utility function testing

### E2E Tests (Playwright)
- Critical user flows (login, diagnostic submission)
- OAuth callback handling
- Real-time collaboration scenarios

---

## Performance Optimization

1. **Code Splitting:** Route-based lazy loading
2. **Asset Optimization:** Image compression, SVG inlining
3. **Caching Strategy:**
   - Static assets cached for 1 year
   - API responses cached for 5 minutes (stale-while-revalidate)
4. **Bundle Analysis:** `npm run build -- --analyze`

---

## Error Handling

### Global Error Handler

```typescript
// main.ts
app.config.errorHandler = (err, instance, info) => {
  console.error('Global error:', err, info)
  // Send to Sentry
  Sentry.captureException(err)
}
```

### API Error Display

```typescript
// composables/useErrorHandler.ts
export function useErrorHandler() {
  const toast = useToast()

  const handleApiError = (error: AxiosError) => {
    if (error.response?.status === 400) {
      toast.error('Datos invalidos. Por favor revisa el formulario.')
    } else if (error.response?.status === 500) {
      toast.error('Error del servidor. Intenta de nuevo mas tarde.')
    } else {
      toast.error('Error de conexion. Verifica tu internet.')
    }
  }

  return { handleApiError }
}
```

---

## Accessibility (a11y)

- Semantic HTML5 elements
- ARIA labels on interactive elements
- Keyboard navigation support
- Screen reader testing with NVDA/JAWS
- Color contrast compliance (WCAG AA)

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [API-ENDPOINTS.md](./API-ENDPOINTS.md) - Backend API reference
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Infrastructure and deployment
- [openapi-neyen-mvp.yaml](../openapi-neyen-mvp.yaml) - OpenAPI specification

---

**Maintained by:** TSW Engineering Team
**Contact:** Ana Ballesteros Benavent (CSO)
**Last Review:** March 2026
