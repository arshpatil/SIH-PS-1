import { useApp } from '../context/AppContext'

export function useAuth() {
  const { isAuthenticated, authLoading, currentUser, login, logout } = useApp()

  return {
    isAuthenticated,
    authLoading,
    currentUser,
    login,
    logout,
  }
}
