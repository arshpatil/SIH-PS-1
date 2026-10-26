import { initialRequests } from '../data/mock/mockRequests'

export const requestService = {
  getInitialRequests: () => {
    return [...initialRequests]
  },

  calculatePendingRequests: (requests) => {
    return requests.filter(r => r.status === 'Under Review' || r.status === 'Submitted').length
  },
}
