import axios from 'axios'

// 1. Resolve API base URL: defaults to relative '/api' to leverage the Vite reverse proxy,
// preventing browser cross-site cookie blocking between localhost and 127.0.0.1.
function resolveApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (!envUrl || envUrl.trim() === '' || envUrl === '/api') {
    return '/api'
  }

  // If running in browser and the URL points to local loopback (127.0.0.1:5000 or localhost:5000),
  // prefer relative '/api' so requests are same-origin and cookies are never blocked.
  if (typeof window !== 'undefined' && window.location) {
    try {
      const parsed = new URL(envUrl, window.location.origin)
      if (
        (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost') &&
        (parsed.port === '5000' || parsed.port === '')
      ) {
        return '/api'
      }
    } catch {
      // Fall through to envUrl
    }
  }

  return envUrl.trim()
}

const API_BASE_URL = resolveApiBaseUrl()

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // CRITICAL: Ensures browser sends and receives HttpOnly session cookies
  headers: {
    'Accept': 'application/json',
  },
})

let csrfTokenCache = null

/**
 * Fetch or reuse CSRF token from the backend /api/auth/csrf-token endpoint.
 * Double-submit CSRF cookie is also placed on the session by the server.
 */
export async function getCsrfToken(forceRefresh = false) {
  if (!csrfTokenCache || forceRefresh) {
    try {
      const response = await apiClient.get('/auth/csrf-token')
      if (response.data && response.data.csrf_token) {
        csrfTokenCache = response.data.csrf_token
      }
    } catch {
      // Gracefully continue; if unauthenticated, mutating call will be caught by 401 handler
    }
  }
  return csrfTokenCache
}

export function setCsrfToken(token) {
  csrfTokenCache = token
}

export function clearCsrfToken() {
  csrfTokenCache = null
}

// Request interceptor: Attach X-CSRF-Token on all mutating HTTP methods
apiClient.interceptors.request.use(
  async (config) => {
    const mutatingMethods = ['post', 'put', 'patch', 'delete']
    const method = config.method?.toLowerCase() || ''
    if (mutatingMethods.includes(method)) {
      if (!config.headers['X-CSRF-Token'] && !config.headers['X-CSRFToken']) {
        const token = await getCsrfToken()
        if (token) {
          config.headers['X-CSRF-Token'] = token
        }
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: Handle 401, 403 CSRF_ERROR retry, and errors gracefully
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401) {
      clearCsrfToken()
      // Dispatch event for auth state sync (skip for login attempts to allow standard error display)
      if (!originalRequest?.url?.includes('/auth/login')) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
    } else if (
      error.response?.status === 403 &&
      error.response?.data?.code === 'CSRF_ERROR' &&
      originalRequest &&
      !originalRequest._retried
    ) {
      // Single retry attempt with fresh CSRF token to prevent infinite loops
      originalRequest._retried = true
      clearCsrfToken()
      const freshToken = await getCsrfToken(true)
      if (freshToken) {
        originalRequest.headers['X-CSRF-Token'] = freshToken
        return apiClient(originalRequest)
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
