import { useApp } from '../context/AppContext'

export function useProfile() {
  const { profile, updateProfile } = useApp()

  return {
    profile,
    updateProfile,
  }
}
