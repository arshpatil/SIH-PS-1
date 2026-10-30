import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react'
import { authService } from '../services/authService'
import { fdrService } from '../services/fdrService'
import { dashboardService } from '../services/dashboardService'
import { notificationService } from '../services/notificationService'
import { requestService } from '../services/requestService'
import { profileService } from '../services/profileService'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)
  const [currentUser, setCurrentUser] = useState(null)

  // Data states
  const [fdrs, setFdrs] = useState(() => fdrService.getInitialFDRs())
  const [fdrLoading, setFdrLoading] = useState(false)
  const [dashboardStats, setDashboardStats] = useState(null)
  const [dashboardCharts, setDashboardCharts] = useState(null)
  const [notifications, setNotifications] = useState(() => notificationService.getInitialNotifications())
  const [unreadCount, setUnreadCount] = useState(0)
  const [requests, setRequests] = useState(() => requestService.getInitialRequests())
  const [profile, setProfile] = useState(() => profileService.getInitialProfile())

  // Toast notifications state
  const [toasts, setToasts] = useState([])

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4500)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // -----------------------------------------------------------
  // Data Fetching Functions
  // -----------------------------------------------------------

  const refreshFDRs = useCallback(async (showLoading = false) => {
    if (showLoading) setFdrLoading(true)
    try {
      const res = await fdrService.listFDRs({ per_page: 50 })
      if (res && Array.isArray(res.data) && res.data.length > 0) {
        setFdrs(res.data)
      }
    } catch {
      // Keep existing FDRs if fetch fails
    } finally {
      if (showLoading) setFdrLoading(false)
    }
  }, [])

  const refreshDashboard = useCallback(async () => {
    try {
      const [statsData, chartsData] = await Promise.allSettled([
        dashboardService.getStats(),
        dashboardService.getCharts(),
      ])

      if (statsData.status === 'fulfilled' && statsData.value) {
        setDashboardStats(statsData.value)
      }
      if (chartsData.status === 'fulfilled' && chartsData.value) {
        setDashboardCharts(chartsData.value)
      }
    } catch {
      // Silent error fallback
    }
  }, [])

  const refreshNotifications = useCallback(async () => {
    try {
      const [listRes, countRes] = await Promise.allSettled([
        notificationService.listNotifications({ per_page: 30 }),
        notificationService.fetchUnreadCount(),
      ])

      if (listRes.status === 'fulfilled' && listRes.value?.notifications?.length > 0) {
        setNotifications(listRes.value.notifications)
      }
      if (countRes.status === 'fulfilled') {
        setUnreadCount(countRes.value)
      }
    } catch {
      // Silent error fallback
    }
  }, [])

  const refreshRequests = useCallback(async () => {
    try {
      const data = await requestService.listRequests()
      if (Array.isArray(data)) {
        setRequests(data)
      }
    } catch {
      // Silent error fallback
    }
  }, [])

  // -----------------------------------------------------------
  // Check Existing Session on Mount
  // -----------------------------------------------------------

  useEffect(() => {
    let isMounted = true

    async function checkAuthSession() {
      try {
        const data = await authService.getCurrentUser()
        if (isMounted && data?.user) {
          setIsAuthenticated(true)
          setCurrentUser(data.user)

          // Update profile based on backend user
          if (data.user.institution_name) {
            setProfile((prev) => ({
              ...prev,
              collegeName: data.user.institution_name,
              aictePermanentId: data.user.institution_code || prev.aictePermanentId,
              adminName: data.user.full_name || prev.adminName,
              email: data.user.email || prev.email,
              address: data.user.institution_address || prev.address,
              contactNumber: data.user.institution_contact_phone || prev.contactNumber,
              alternateEmail: data.user.institution_contact_email || prev.alternateEmail,
            }))
          }
        }
      } catch {
        if (isMounted) {
          setIsAuthenticated(false)
          setCurrentUser(null)
        }
      } finally {
        if (isMounted) {
          setAuthLoading(false)
        }
      }
    }

    checkAuthSession()

    // Listen for 401 unauthorized events
    const handleUnauthorized = () => {
      setIsAuthenticated(false)
      setCurrentUser(null)
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)

    return () => {
      isMounted = false
      window.removeEventListener('auth:unauthorized', handleUnauthorized)
    }
  }, [])

  // Fetch authenticated data once logged in
  useEffect(() => {
    if (!isAuthenticated) return

    let isMounted = true
    const loadAuthData = async () => {
      try {
        const [fdrRes] = await Promise.allSettled([
          fdrService.listFDRs({ per_page: 50 }),
        ])
        if (isMounted && fdrRes.status === 'fulfilled' && fdrRes.value?.data?.length > 0) {
          setFdrs(fdrRes.value.data)
        }
      } catch {
        // Fallback
      }

      if (isMounted) {
        refreshDashboard()
        refreshNotifications()
        refreshRequests()
      }
    }

    loadAuthData()

    return () => {
      isMounted = false
    }
  }, [isAuthenticated, refreshDashboard, refreshNotifications, refreshRequests])

  // -----------------------------------------------------------
  // Auth Operations
  // -----------------------------------------------------------

  const login = async (email, password) => {
    try {
      const data = await authService.login(email, password)
      if (data?.user) {
        setIsAuthenticated(true)
        setCurrentUser(data.user)

        if (data.user.institution_name) {
          setProfile((prev) => ({
            ...prev,
            collegeName: data.user.institution_name,
            aictePermanentId: data.user.institution_code || prev.aictePermanentId,
            adminName: data.user.full_name || prev.adminName,
            email: data.user.email || prev.email,
          }))
        }

        showToast(`Welcome back, ${data.user.full_name}!`, 'success')
        return { success: true, user: data.user }
      }
      return { success: false, error: 'Login failed' }
    } catch (err) {
      const errMsg = err.response?.data?.error || err.response?.data?.message || err.message || 'Invalid credentials'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  const logout = async () => {
    try {
      await authService.logout()
    } catch {
      // Ignore network errors on logout
    } finally {
      setIsAuthenticated(false)
      setCurrentUser(null)
      showToast('Signed out of session', 'info')
    }
  }

  // -----------------------------------------------------------
  // FDR Operations
  // -----------------------------------------------------------

  const addFDR = async (newFDRData, file = null) => {
    try {
      // 1. Create FDR record in backend
      const createdRecord = await fdrService.createFDR(newFDRData)

      // 2. Upload file if attached
      let ocrDiscrepancies = null
      if (file && createdRecord.id) {
        try {
          const uploadRes = await fdrService.uploadDocument(createdRecord.id, file)
          ocrDiscrepancies = uploadRes?.discrepancy_report
        } catch (uploadErr) {
          console.warn('Document upload error:', uploadErr)
          showToast('FDR created, but document upload failed.', 'warning')
        }
      }

      // 3. Update local state & refresh
      setFdrs((prev) => [createdRecord, ...prev])
      refreshDashboard()
      refreshNotifications()

      showToast(`FDR ${createdRecord.fdrNumber} created successfully!`, 'success')
      return { record: createdRecord, ocrDiscrepancies }
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Failed to create FDR'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  const updateFDR = async (id, updatedFields) => {
    try {
      const updated = await fdrService.updateFDR(id, updatedFields)
      setFdrs((prev) => prev.map((item) => (item.id === id ? updated : item)))
      showToast(`FDR ${updated.fdrNumber} updated`, 'success')
      return updated
    } catch (err) {
      const errMsg = err.response?.data?.error || err.message || 'Failed to update FDR'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  const getFDRById = (id) => {
    // Check local list first
    const found = fdrs.find((f) => String(f.id) === String(id))
    return found || null
  }

  // -----------------------------------------------------------
  // Request Operations
  // -----------------------------------------------------------

  const addRequest = async (requestData) => {
    try {
      const created = await requestService.createRequest(requestData)
      setRequests((prev) => [created, ...prev])
      refreshDashboard()
      refreshRequests()
      refreshNotifications()
      showToast(`Petition ${created.id} submitted successfully!`, 'success')
      return created
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Failed to submit petition'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  const submitRenewalDetails = async (requestId, payload) => {
    try {
      const data = await requestService.submitRenewalDetails(requestId, payload)
      await Promise.allSettled([refreshDashboard(), refreshRequests(), refreshNotifications(), refreshFDRs()])
      showToast('Renewed FDR receipt submitted successfully!', 'success')
      return data
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Failed to submit renewal receipt'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  const verifyRenewal = async (requestId, payload) => {
    try {
      const data = await requestService.verifyRenewal(requestId, payload)
      await Promise.allSettled([refreshDashboard(), refreshRequests(), refreshNotifications(), refreshFDRs()])
      showToast('Renewal decision recorded successfully!', 'success')
      return data
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Failed to record renewal verification'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  // -----------------------------------------------------------
  // Notifications Operations
  // -----------------------------------------------------------

  const markAsRead = async (id) => {
    try {
      await notificationService.markAsRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, isRead: true, is_read: true } : n))
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    } catch {
      // Local fallback
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, isRead: true, is_read: true } : n))
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    }
  }

  const markAllAsRead = async () => {
    try {
      await notificationService.markAllAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true, is_read: true })))
      setUnreadCount(0)
      showToast('All notifications marked as read', 'info')
    } catch {
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true, is_read: true })))
      setUnreadCount(0)
      showToast('All notifications marked as read', 'info')
    }
  }

  // -----------------------------------------------------------
  // Profile Operations
  // -----------------------------------------------------------

  const updateProfile = async (updatedData) => {
    try {
      const res = await authService.updateProfile(updatedData)
      if (res?.user) {
        setCurrentUser(res.user)
        setProfile((prev) => ({
          ...prev,
          collegeName: res.user.institution_name || updatedData.collegeName || prev.collegeName,
          aictePermanentId: res.user.institution_code || prev.aictePermanentId,
          adminName: res.user.full_name || updatedData.adminName || prev.adminName,
          email: res.user.email || updatedData.email || prev.email,
          address: res.user.institution_address || updatedData.address || prev.address,
          contactNumber: res.user.institution_contact_phone || updatedData.contactNumber || prev.contactNumber,
          alternateEmail: res.user.institution_contact_email || updatedData.alternateEmail || prev.alternateEmail,
          lastUpdated: new Date().toISOString(),
        }))
        showToast('Profile updated successfully!', 'success')
        return res.user
      }
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Failed to save profile'
      showToast(errMsg, 'error')
      throw new Error(errMsg, { cause: err })
    }
  }

  // -----------------------------------------------------------
  // Derived Statistics (Unified backend + fallback)
  // -----------------------------------------------------------

  const stats = useMemo(() => {
    if (dashboardStats) {
      const activeCount =
        dashboardStats.validity_counts?.ACTIVE ??
        dashboardStats.status_counts?.VERIFIED ??
        0
      const maturingSoonCount =
        dashboardStats.validity_counts?.EXPIRING_SOON ?? 0
      const pendingCount =
        (dashboardStats.status_counts?.SUBMITTED ?? 0) +
        (dashboardStats.status_counts?.PENDING_VERIFICATION ?? 0)

      return {
        totalFdrs: dashboardStats.total_fdrs ?? fdrs.length,
        totalValue: dashboardStats.total_value ?? 0,
        totalValueFormatted: dashboardStats.total_value_formatted ?? '0.00',
        activeFdrs: activeCount,
        maturingSoon: maturingSoonCount,
        pendingRequests: pendingCount || requests.length,
        statusCounts: dashboardStats.status_counts || {},
        validityCounts: dashboardStats.validity_counts || {},
        statusBreakdown: dashboardStats.status_breakdown || [],
      }
    }

    // Fallback to local calculation
    const fdrStats = fdrService.calculateStats(fdrs)
    const pendingRequestsCount = requestService.calculatePendingRequests(requests)
    return {
      totalFdrs: fdrStats.total,
      totalValue: fdrs.reduce((sum, f) => sum + (parseFloat(f.amount || f.depositAmount) || 0), 0),
      totalValueFormatted: '0.00',
      activeFdrs: fdrStats.active,
      maturingSoon: fdrStats.maturingSoon,
      pendingRequests: pendingRequestsCount,
      statusCounts: {},
      validityCounts: {},
      statusBreakdown: [],
    }
  }, [dashboardStats, fdrs, requests])

  const upcomingMaturities = useMemo(() => {
    return fdrService.getUpcomingMaturities(fdrs, 5)
  }, [fdrs])

  const statusDistribution = useMemo(() => {
    if (dashboardCharts?.workflow_distribution?.length > 0) {
      const statusColors = {
        VERIFIED: '#10B981',
        ACTIVE: '#10B981',
        PENDING_VERIFICATION: '#F59E0B',
        SUBMITTED: '#3B82F6',
        DRAFT: '#94A3B8',
        RETURNED: '#E11D48',
        REJECTED: '#EF4444',
      }
      return dashboardCharts.workflow_distribution.map((item) => ({
        name: item.status,
        value: item.count,
        color: statusColors[item.status] || '#94A3B8',
        percentage: item.percentage,
      }))
    }
    return fdrService.getStatusDistribution(fdrs)
  }, [dashboardCharts, fdrs])

  const value = {
    // Data
    fdrs,
    fdrLoading,
    requests,
    notifications,
    profile,
    currentUser,
    isAuthenticated,
    authLoading,
    toasts,
    stats,
    dashboardStats,
    dashboardCharts,
    unreadCount,
    upcomingMaturities,
    statusDistribution,

    // Refreshers
    refreshFDRs,
    refreshRequests,
    refreshDashboard,
    refreshNotifications,

    // Actions
    addFDR,
    updateFDR,
    getFDRById,
    addRequest,
    submitRenewalDetails,
    verifyRenewal,
    markAsRead,
    markAllAsRead,
    updateProfile,

    // Auth Actions
    login,
    logout,

    // Toast Actions
    showToast,
    removeToast,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within an AppProvider')
  }
  return context
}
