import apiClient, { getCsrfToken, setCsrfToken, clearCsrfToken } from '../api/client'

export const authService = {
  /**
   * Authenticate with email & password.
   * On success, backend sets HttpOnly session cookie and returns { user, csrf_token }.
   */
  async login(email, password) {
    // Obtain initial CSRF token for the login session if needed
    await getCsrfToken()
    const response = await apiClient.post('/auth/login', {
      email: email.trim().toLowerCase(),
      password,
    })

    if (response.data?.csrf_token) {
      setCsrfToken(response.data.csrf_token)
    }

    return response.data
  },

  /**
   * Securely terminate active session on the backend.
   */
  async logout() {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      clearCsrfToken()
    }
  },

  /**
   * Retrieve active authenticated user profile & verify session validity.
   */
  async getCurrentUser() {
    const response = await apiClient.get('/auth/me')
    if (response.data?.csrf_token) {
      setCsrfToken(response.data.csrf_token)
    }
    return response.data
  },

  /**
   * Probe backend health check endpoint.
   */
  async checkHealth() {
    const response = await apiClient.get('/health')
    return response.data
  },

  /**
   * Update authorized profile fields on the backend.
   */
  async updateProfile(payload) {
    const response = await apiClient.patch('/auth/profile', payload)
    return response.data
  },
}

export default authService
