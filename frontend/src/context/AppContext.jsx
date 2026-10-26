import React, { createContext, useContext, useState, useMemo } from 'react'
import { fdrService } from '../services/fdrService'
import { requestService } from '../services/requestService'
import { notificationService } from '../services/notificationService'
import { profileService } from '../services/profileService'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // State initialization from services
  const [fdrs, setFdrs] = useState(() => fdrService.getInitialFDRs())
  const [requests, setRequests] = useState(() => requestService.getInitialRequests())
  const [notifications, setNotifications] = useState(() => notificationService.getInitialNotifications())
  const [profile, setProfile] = useState(() => profileService.getInitialProfile())
  
  // Demo Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(true)
  const [currentUser, setCurrentUser] = useState({
    name: 'Dr. K. S. Ramanathan',
    role: 'College Administrator',
    email: 'principal@abcite.edu.in',
  })

  // Toast notifications state
  const [toasts, setToasts] = useState([])

  const showToast = (message, type = 'success') => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  // Derived statistics
  const stats = useMemo(() => {
    const fdrStats = fdrService.calculateStats(fdrs)
    const pendingRequestsCount = requestService.calculatePendingRequests(requests)
    return {
      totalFdrs: fdrStats.total,
      activeFdrs: fdrStats.active,
      maturingSoon: fdrStats.maturingSoon,
      pendingRequests: pendingRequestsCount,
    }
  }, [fdrs, requests])

  const unreadCount = useMemo(() => {
    return notificationService.getUnreadCount(notifications)
  }, [notifications])

  const upcomingMaturities = useMemo(() => {
    return fdrService.getUpcomingMaturities(fdrs, 5)
  }, [fdrs])

  const statusDistribution = useMemo(() => {
    return fdrService.getStatusDistribution(fdrs)
  }, [fdrs])

  // FDR operations
  const addFDR = (newFDRData) => {
    const newId = `fdr-${Date.now()}`
    const record = {
      ...newFDRData,
      id: newId,
      status: 'Pending Verification',
      activityHistory: [
        {
          id: `act-${Date.now()}`,
          date: new Date().toISOString(),
          title: 'FDR Submitted by College',
          description: `Uploaded FDR receipt under reference ${newFDRData.fdrNumber}. Pending AICTE verification.`,
          actor: currentUser.name,
        },
      ],
    }

    setFdrs(prev => [record, ...prev])

    // Generate automated notification
    const newNotif = {
      id: `notif-${Date.now()}`,
      title: 'New FDR Submitted for Scrutiny',
      message: `${newFDRData.fdrNumber} (${newFDRData.bankName}) uploaded successfully. AICTE desk review scheduled.`,
      type: 'Verification',
      category: 'info',
      timestamp: new Date().toISOString(),
      isRead: false,
      relatedFdrId: newId,
      relatedFdrNumber: newFDRData.fdrNumber,
      link: `/fdrs/${newId}`,
      linkText: 'View FDR Details',
    }
    setNotifications(prev => [newNotif, ...prev])

    showToast(`FDR ${newFDRData.fdrNumber} submitted successfully!`, 'success')
    return record
  }

  const updateFDR = (id, updatedFields) => {
    setFdrs(prev =>
      prev.map(item => {
        if (item.id === id) {
          const updated = { ...item, ...updatedFields }
          return updated
        }
        return item
      })
    )
  }

  const getFDRById = (id) => {
    return fdrs.find(f => f.id === id)
  }

  // Request operations
  const addRequest = (requestData) => {
    const reqId = `REQ-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`
    const newRequest = {
      ...requestData,
      id: reqId,
      submissionDate: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
      status: 'Under Review',
      stage: 'Desk Scrutiny in Progress',
    }

    setRequests(prev => [newRequest, ...prev])

    // If it's a renewal request, update the related FDR's status if active
    if (requestData.fdrId) {
      setFdrs(prev =>
        prev.map(f => {
          if (f.id === requestData.fdrId) {
            const newHistory = [
              {
                id: `act-${Date.now()}`,
                date: new Date().toISOString(),
                title: `${requestData.requestType} Request Filed (${reqId})`,
                description: requestData.reason,
                actor: currentUser.name,
              },
              ...(f.activityHistory || []),
            ]
            return {
              ...f,
              status: requestData.requestType === 'Renewal' ? 'Renewal Pending' : f.status,
              activityHistory: newHistory,
            }
          }
          return f
        })
      )
    }

    // Add notification
    const newNotif = {
      id: `notif-${Date.now()}`,
      title: `${requestData.requestType} Request Initiated`,
      message: `Request ${reqId} for ${requestData.fdrNumber || 'FDR'} has been logged and forwarded to AICTE finance section.`,
      type: 'Request Update',
      category: 'info',
      timestamp: new Date().toISOString(),
      isRead: false,
      relatedRequestId: reqId,
      link: '/requests',
      linkText: 'Track Requests',
    }
    setNotifications(prev => [newNotif, ...prev])

    showToast(`Request ${reqId} submitted successfully!`, 'success')
    return newRequest
  }

  // Notifications operations
  const markAsRead = (id) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, isRead: true } : n))
    )
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, isRead: true })))
    showToast('All notifications marked as read', 'info')
  }

  // Profile operations
  const updateProfile = (updatedData) => {
    setProfile(prev => ({
      ...prev,
      ...updatedData,
      lastUpdated: new Date().toISOString(),
    }))
    setCurrentUser(prev => ({
      ...prev,
      name: updatedData.adminName || prev.name,
      email: updatedData.email || prev.email,
    }))
    showToast('College profile and settings saved successfully!', 'success')
  }

  // Demo Auth operations
  const login = (email, password) => {
    setIsAuthenticated(true)
    showToast('Welcome back, College Administrator!', 'success')
    return true
  }

  const logout = () => {
    setIsAuthenticated(false)
    showToast('Signed out of demonstration session', 'info')
  }

  const value = {
    // Data
    fdrs,
    requests,
    notifications,
    profile,
    currentUser,
    isAuthenticated,
    toasts,
    stats,
    unreadCount,
    upcomingMaturities,
    statusDistribution,

    // FDR Actions
    addFDR,
    updateFDR,
    getFDRById,

    // Request Actions
    addRequest,

    // Notification Actions
    markAsRead,
    markAllAsRead,

    // Profile Actions
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
