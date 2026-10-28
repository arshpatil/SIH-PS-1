import { initialProfile } from '../data/mock/mockProfile'

export const profileService = {
  getInitialProfile: () => {
    return { ...initialProfile }
  },
}
