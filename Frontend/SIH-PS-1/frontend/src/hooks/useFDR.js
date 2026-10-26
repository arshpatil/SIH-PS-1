import { useApp } from '../context/AppContext'

export function useFDR() {
  const {
    fdrs,
    stats,
    upcomingMaturities,
    statusDistribution,
    addFDR,
    updateFDR,
    getFDRById,
  } = useApp()

  return {
    fdrs,
    stats,
    upcomingMaturities,
    statusDistribution,
    addFDR,
    updateFDR,
    getFDRById,
  }
}
