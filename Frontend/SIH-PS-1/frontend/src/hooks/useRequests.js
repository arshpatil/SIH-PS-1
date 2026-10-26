import { useApp } from '../context/AppContext'

export function useRequests() {
  const { requests, stats, addRequest } = useApp()

  const getRequestsForFDR = (fdrId) => {
    return requests.filter(r => r.fdrId === fdrId)
  }

  return {
    requests,
    pendingCount: stats.pendingRequests,
    addRequest,
    getRequestsForFDR,
  }
}
