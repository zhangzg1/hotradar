import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { useTheme } from '@/contexts/ThemeContext'
import { ThemeSwitcher } from '@/components/ui/ThemeSwitcher'
import { Toast } from '@/components/ui/Toast'
import { SplitButton } from '@/components/ui/SplitButton'
import { QuotaSettings } from '@/components/ui/QuotaSettings'
import { SettingsModal } from '@/components/ui/SettingsModal'
import { DouyinLoginModal } from '@/components/ui/DouyinLoginModal'
import { HotspotCard } from '@/components/hotspot/HotspotCard'
import { KeywordCard, KeywordAddForm } from '@/components/keyword/KeywordCard'
import { FilterBar, defaultFilterState, type FilterState } from '@/components/filter/FilterBar'
import { StatsGrid } from '@/components/stats/StatCard'
import { HotspotChat } from '@/components/chat/HotspotChat'
import { LoginPage } from '@/components/auth/LoginPage'
import {
  keywordsApi,
  hotspotsApi,
  collectionApi,
  emailApi,
  schedulerApi,
  settingsApi,
  getUser,
  clearAuth,
  isAuthenticated,
  type Keyword,
  type Hotspot,
} from '@/services/api'
import {
  connectWebSocket,
  disconnectWebSocket,
  onNewHotspot,
  onStatusChange,
  onBatchHotspot,
  onError,
  onDouyinCookieChange,
  subscribeToTask,
  unsubscribeTask,
} from '@/services/socket'
import {
  Flame,
  Radio,
  Search,
  ChevronLeft,
  ChevronRight,
  Target,
  Mail,
  Clock,
  Timer,
  Settings,
  LogOut,
} from 'lucide-react'

type TabType = 'radar' | 'keywords' | 'search'

export default function App() {
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated())
  const [currentUser, setCurrentUser] = useState(() => getUser())

  const handleLogin = (_token: string, user: { userId: string; username: string }) => {
    setAuthenticated(true)
    setCurrentUser(user)
  }

  const handleLogout = () => {
    clearAuth()
    setAuthenticated(false)
    setCurrentUser(null)
  }

  return (
    <ThemeProvider>
      {!authenticated ? <LoginPage onLogin={handleLogin} /> : <MainApp currentUser={currentUser} onLogout={handleLogout} />}
    </ThemeProvider>
  )
}

function MainApp({
  currentUser,
  onLogout,
}: {
  currentUser: { userId: string; username: string } | null
  onLogout: () => void
}) {
  const [showUserMenu, setShowUserMenu] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  // Data state
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [hotspots, setHotspots] = useState<Hotspot[]>([])
  const [stats, setStats] = useState({
    total: 0,
    todayNew: 0,
    weekNew: 0,
    activeKeywords: 0,
  })

  // UI state
  const [activeTab, setActiveTab] = useState<TabType>('radar')
  const [isLoading, setIsLoading] = useState(false)
  const [isCollecting, setIsCollecting] = useState(false)
  const currentTaskIdRef = useRef<string | null>(null)
  const [collectProgress, setCollectProgress] = useState<{ completed: number; total: number } | null>(null)
  const [filters, setFilters] = useState<FilterState>(defaultFilterState)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const pageSize = 15
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Hotspot[]>([])
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null)

  // 采集设置状态
  const [collectWithEmail, setCollectWithEmail] = useState(false)

  // 邮件推送状态
  const [emailTimeRange, setEmailTimeRange] = useState('12h')
  const [isSendingEmail, setIsSendingEmail] = useState(false)

  // 定时推送状态
  const [schedulerEnabled, setSchedulerEnabled] = useState(false)
  const [schedulerInterval, setSchedulerInterval] = useState(2)
  const [schedulerStatus, setSchedulerStatus] = useState<{
    lastRunAt: string | null
    lastRunStatus: string | null
    nextRunAt: string | null
    isCollecting: boolean
  } | null>(null)

  // 聊天面板状态
  const [chatHotspot, setChatHotspot] = useState<Hotspot | null>(null)
  useTheme()

  // 设置弹窗状态
  const [showSettings, setShowSettings] = useState(false)
  const [showDouyinLogin, setShowDouyinLogin] = useState(false)
  const [llmReady, setLlmReady] = useState(false)
  const [emailValid, setEmailValid] = useState(false)

  // Close user menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const showToast = (msg: string, type: 'success' | 'error' | 'info') => {
    setToast({ message: msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // 加载设置状态
  const loadSettingsStatus = useCallback(async () => {
    try {
      const data = await settingsApi.get()
      setLlmReady(data.llmTested && !!data.llmBaseUrl && !!data.llmApiKey && !!data.llmModelName)
      const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      setEmailValid(!!data.notifyEmail && emailRe.test(data.notifyEmail))
    } catch {
      // 设置未配置
    }
  }, [])

  // Load data
  const loadData = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true)
    try {
      const [keywordsRes, hotspotsRes, statsRes] = await Promise.all([
        keywordsApi.getAll({ pageSize: 100 }),
        hotspotsApi.getAll({
          page,
          pageSize,
          keywordIds: filters.keywordIds.length > 0 ? filters.keywordIds : undefined,
          sources: filters.sources.length > 0 ? filters.sources : undefined,
          importance: filters.importances.length > 0 ? filters.importances : undefined,
          timeRange: filters.timeRange || undefined,
          sortBy: filters.sortBy,
          sortOrder: filters.sortOrder,
        }),
        hotspotsApi.getStats(),
      ])

      const currentHotspots = hotspotsRes.data || []
      if (currentHotspots.length === 0 && page > 1) {
        setPage(1)
        return
      }

      setKeywords(keywordsRes.data || [])
      setHotspots(currentHotspots)
      setTotalPages(Math.ceil((hotspotsRes.total || 0) / pageSize))
      const activeKwCount = keywordsRes.data?.filter((k) => k.isActive).length || 0
      setStats({
        total: statsRes.total || 0,
        todayNew: statsRes.todayNew || 0,
        weekNew: statsRes.weekNew || 0,
        activeKeywords: activeKwCount,
      })
    } catch (err) {
      if (showLoading) showToast('数据加载失败', 'error')
    } finally {
      if (showLoading) setIsLoading(false)
    }
  }, [page, filters])

  // Load scheduler status
  const loadSchedulerStatus = useCallback(async () => {
    try {
      const [configRes, statusRes] = await Promise.all([
        schedulerApi.getConfig(),
        schedulerApi.getStatus(),
      ])
      setSchedulerEnabled(configRes.isEnabled)
      setSchedulerInterval(configRes.intervalHours)
      setSchedulerStatus({
        lastRunAt: statusRes.lastRunAt,
        lastRunStatus: statusRes.lastRunStatus,
        nextRunAt: statusRes.nextRunAt,
        isCollecting: statusRes.isCollecting,
      })
    } catch {
      // 调度状态加载失败不影响主流程
    }
  }, [])

  // WebSocket setup
  useEffect(() => {
    connectWebSocket()

    const unsub1 = onNewHotspot((h) => {
      setHotspots((prev) => {
        if (prev.some(p => p.id === h.id)) return prev
        return [h, ...prev.slice(0, 14)]
      })
    })

    const unsubBatch = onBatchHotspot((data) => {
      console.log('[App] 收到批量热点:', data.stats.total, '条')
      setHotspots((prev) => {
        const newHotspots = data.hotspots.filter(h => !prev.some(p => p.id === h.id))
        if (newHotspots.length === 0) return prev
        return [...newHotspots, ...prev.slice(0, 14 - newHotspots.length)]
      })
    })

    const unsub2 = onStatusChange((s) => {
      if (currentTaskIdRef.current && s.taskId !== currentTaskIdRef.current) return

      if (s.status === 'started') {
        setCollectProgress({ completed: 0, total: s.totalKeywords || 0 })
        showToast('采集任务已启动', 'info')
      } else if (s.status === 'keyword_completed') {
        setCollectProgress((prev) => prev ? { ...prev, completed: prev.completed + 1 } : null)
        showToast(`${s.keyword} 采集完成，获取 ${s.hotspotsCount || 0} 条热点`, 'success')
      } else if (s.status === 'completed') {
        setIsCollecting(false)
        setCollectProgress(null)
        const totalHotspots = s.totalHotspots || 0
        showToast(`采集完成！共采集 ${totalHotspots} 条热点数据`, 'success')
        unsubscribeTask()
        currentTaskIdRef.current = null
        loadData()
      }
    })

    const unsubError = onError((e) => {
      if (currentTaskIdRef.current && e.taskId !== currentTaskIdRef.current) return
      console.error('[App] 采集错误:', e.error)
      setIsCollecting(false)
      setCollectProgress(null)
      unsubscribeTask()
      currentTaskIdRef.current = null
      showToast(`采集失败: ${e.error}`, 'error')
    })

    const unsubDouyin = onDouyinCookieChange((data) => {
      if (data.type === 'douyin_cookie_expired') {
        showToast('抖音 Cookie 已过期，请重新登录', 'error')
        setShowDouyinLogin(true)
      } else if (data.type === 'douyin_cookie_updated') {
        showToast(data.message || '抖音登录成功', 'success')
      }
    })

    return () => {
      unsub1()
      unsubBatch()
      unsub2()
      unsubError()
      unsubDouyin()
      disconnectWebSocket()
    }
  }, [loadData])

  // Initial load
  useEffect(() => {
    loadData()
    loadSchedulerStatus()
    loadSettingsStatus()
  }, [loadData, loadSchedulerStatus, loadSettingsStatus])

  // Reset page on filter change
  useEffect(() => {
    setPage(1)
  }, [filters])

  // Keyword actions
  const handleAddKeyword = async (text: string) => {
    try {
      await keywordsApi.create({ text })
      loadData()
      showToast('关键词已添加', 'success')
    } catch {
      showToast('添加失败', 'error')
    }
  }

  const handleToggleKeyword = async (id: string) => {
    try {
      await keywordsApi.toggle(id)
      setKeywords((prev) => {
        const newKeywords = prev.map((k) => (k.id === id ? { ...k, isActive: !k.isActive } : k))
        const newActiveCount = newKeywords.filter(k => k.isActive).length
        setStats((prevStats) => ({ ...prevStats, activeKeywords: newActiveCount }))
        return newKeywords
      })
    } catch {
      showToast('操作失败', 'error')
    }
  }

  const handleDeleteKeyword = async (id: string) => {
    try {
      await keywordsApi.delete(id)
      setKeywords((prev) => {
        const newKeywords = prev.filter((k) => k.id !== id)
        const newActiveCount = newKeywords.filter(k => k.isActive).length
        setStats((prevStats) => ({ ...prevStats, activeKeywords: newActiveCount }))
        return newKeywords
      })
      setHotspots((prev) => prev.filter((h) => h.keywordId !== id))
      setSearchResults((prev) => prev.filter((h) => h.keywordId !== id))
      showToast('已删除', 'success')
      loadData(false)
    } catch {
      showToast('删除失败', 'error')
    }
  }

  // Collection trigger
  const handleCollect = async () => {
    if (!llmReady) {
      showToast('请先在设置中配置并测试 LLM', 'error')
      return
    }
    if (collectWithEmail && !emailValid) {
      showToast('请先在设置中配置有效的邮箱地址', 'error')
      return
    }
    const activeIds = keywords.filter((k) => k.isActive).map((k) => k.id)
    if (activeIds.length === 0) {
      showToast('请先激活关键词', 'error')
      return
    }

    setIsCollecting(true)
    setCollectProgress(null)
    try {
      const res = await (collectWithEmail ? collectionApi.createWithAutoEmail(activeIds) : collectionApi.create(activeIds))
      currentTaskIdRef.current = res.taskId
      subscribeToTask(res.taskId)
      showToast(res.message || '采集任务已启动', 'info')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '启动失败'
      showToast(errorMsg, 'error')
      setIsCollecting(false)
      currentTaskIdRef.current = null
    }
  }

  // Email push
  const handleEmailPush = async () => {
    if (!emailValid) {
      showToast('请先在设置中配置有效的邮箱地址', 'error')
      return
    }
    setIsSendingEmail(true)
    try {
      const res = await emailApi.sendRecent(emailTimeRange)
      showToast(res.message || '邮件推送完成', 'success')
    } catch {
      showToast('发送失败', 'error')
    } finally {
      setIsSendingEmail(false)
    }
  }

  // Scheduler toggle
  const handleSchedulerToggle = async (enabled: boolean) => {
    if (enabled && !llmReady) {
      showToast('请先在设置中配置并测试 LLM', 'error')
      return
    }
    if (enabled && !emailValid) {
      showToast('请先在设置中配置有效的邮箱地址', 'error')
      return
    }
    try {
      await schedulerApi.updateConfig({ isEnabled: enabled, intervalHours: schedulerInterval })
      setSchedulerEnabled(enabled)
      showToast(enabled ? `定时推送已开启，每 ${schedulerInterval} 小时执行` : '定时推送已关闭', 'success')
      loadSchedulerStatus()
    } catch {
      showToast('操作失败', 'error')
    }
  }

  // Scheduler interval change
  const handleSchedulerIntervalChange = async (hours: number) => {
    if (hours < 1 || hours > 72) return
    try {
      await schedulerApi.updateConfig({ isEnabled: schedulerEnabled, intervalHours: hours })
      setSchedulerInterval(hours)
      showToast(`间隔已更新为 ${hours} 小时`, 'info')
      loadSchedulerStatus()
    } catch {
      showToast('更新间隔失败', 'error')
    }
  }

  // Poll scheduler status when enabled
  useEffect(() => {
    if (!schedulerEnabled) return
    const timer = setInterval(loadSchedulerStatus, 30000)
    return () => clearInterval(timer)
  }, [schedulerEnabled, loadSchedulerStatus])

  // Delete hotspot
  const handleDeleteHotspot = async (id: string) => {
    try {
      await hotspotsApi.delete(id)
      setHotspots((prev) => prev.filter((h) => h.id !== id))
      setSearchResults((prev) => prev.filter((h) => h.id !== id))
      showToast('热点已删除', 'success')
      loadData(false)
    } catch {
      showToast('删除失败', 'error')
    }
  }

  // Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setIsLoading(true)
    try {
      const res = await hotspotsApi.search(searchQuery.trim())
      setSearchResults(res.data || [])
      showToast(`找到 ${res.total || 0} 条结果`, 'success')
    } catch {
      showToast('搜索失败', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const tabs = [
    { key: 'radar', label: '热点雷达', icon: Radio },
    { key: 'keywords', label: '监控词', icon: Target },
    { key: 'search', label: '搜索', icon: Search },
  ]

  const collectTimeOptions = [
    { value: false, label: '仅采集' },
    { value: true, label: '采集并推送邮件' },
  ]

  const emailTimeOptions = [
    { value: '12h', label: '最近 12 小时' },
    { value: '24h', label: '最近 24 小时' },
    { value: '7d', label: '最近 7 天' },
    { value: '14d', label: '最近 14 天' },
  ]

  return (
    <div className="min-h-screen bg-surface relative">
      {/* 背景效果 */}
      <div className="fixed inset-0 bg-tech pointer-events-none" />
      <div className="fixed inset-0 bg-grid-pattern opacity-50 pointer-events-none" />

      {/* Toast */}
      <AnimatePresence>
        {toast && <Toast key={toast.message + toast.type} message={toast.message} type={toast.type} />}
      </AnimatePresence>

      {/* Settings Modal */}
      <SettingsModal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        onSettingsChanged={loadSettingsStatus}
        onToast={showToast}
      />

      {/* Douyin Login Modal */}
      <DouyinLoginModal
        open={showDouyinLogin}
        onClose={() => setShowDouyinLogin(false)}
        onLoginSuccess={() => setShowDouyinLogin(false)}
        onToast={showToast}
      />

      {/* Header */}
      <header className="sticky top-0 z-40 bg-surface/85 border-b border-line/50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <img src="/hotradar.png" alt="HotRadar" className="w-9 h-9 rounded-xl shadow-lg" />
              <div>
                <h1 className="text-lg font-semibold text-content">HotRadar</h1>
                <p className="text-xs text-content-muted">AI 热点监控助手</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {/* 设置 */}
              <motion.button
                onClick={() => setShowSettings(true)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-sm font-medium accent-rose transition-all"
              >
                <Settings className="w-4 h-4" />
                <span className="hidden sm:inline">设置</span>
              </motion.button>

              {/* 配额设置 */}
              <QuotaSettings onToast={showToast} onDouyinLoginClick={() => setShowDouyinLogin(true)} />

              {/* 热点采集按钮 */}
              <SplitButton<boolean>
                options={collectTimeOptions}
                selectedValue={collectWithEmail}
                onSelect={(v: boolean) => { if (v && !emailValid) { showToast('请先在设置中配置有效的邮箱地址', 'error'); return } setCollectWithEmail(v) }}
                onExecute={handleCollect}
                isExecuting={isCollecting}
                executeLabel="热点采集"
                executingLabel="采集中"
                icon={<Flame className="w-4 h-4" />}
                progress={collectProgress}
              />

              {/* 邮件推送按钮 */}
              <SplitButton<string>
                options={emailTimeOptions}
                selectedValue={emailTimeRange}
                onSelect={setEmailTimeRange}
                onExecute={handleEmailPush}
                isExecuting={isSendingEmail}
                executeLabel="邮件推送"
                executingLabel="推送中"
                icon={<Mail className="w-4 h-4" />}
                showCheck={false}
                variant="secondary"
              />

              {/* 主题切换 */}
              <ThemeSwitcher />

              {/* 用户菜单 */}
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-alt/50 border border-line/50 text-content-alt hover:bg-surface-dim/50 transition-all"
                >
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-medium">
                    {currentUser?.username?.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm hidden sm:inline">{currentUser?.username}</span>
                </button>
                <AnimatePresence>
                  {showUserMenu && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 top-full mt-2 min-w-[160px] bg-surface-alt/95 backdrop-blur-md rounded-lg border border-line/50 shadow-xl py-1 z-50"
                    >
                      <button
                        onClick={onLogout}
                        className="flex items-center gap-2 w-full px-4 py-2 text-sm text-t-red hover:bg-t-red-light transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        退出登录
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-6">
        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as TabType)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm transition-all",
                activeTab === key
                  ? "accent-active"
                  : "border border-transparent text-content-muted hover:bg-surface-dim hover:text-content-alt"
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Radar Tab */}
        {activeTab === 'radar' && (
          <div className="space-y-6">
            <StatsGrid stats={stats} />

            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-base font-medium text-content">
                <Flame className="w-5 h-5 text-t-orange" />
                实时热点信息
              </h2>
              <div className="flex items-center gap-3">
                {/* 定时推送控件 */}
                <div className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors duration-200",
                  schedulerEnabled
                    ? "accent-indigo"
                    : "accent-cyan"
                )}>
                  <Timer className={cn(
                    "w-3.5 h-3.5",
                    schedulerEnabled ? "text-t-indigo" : "text-t-cyan"
                  )} />
                  <span className={cn(
                    "text-xs",
                    schedulerEnabled ? "text-t-indigo" : "text-t-cyan"
                  )}>定时推送</span>
                  {/* Toggle 开关 */}
                  <button
                    onClick={() => handleSchedulerToggle(!schedulerEnabled)}
                    className={cn(
                      "relative w-9 h-5 rounded-full transition-colors duration-200",
                      schedulerEnabled ? "bg-[var(--toggle-on-bg)]" : "bg-[var(--toggle-off-bg)]"
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200",
                        schedulerEnabled && "translate-x-4"
                      )}
                    />
                  </button>
                  {/* 间隔输入 */}
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min={1}
                      max={72}
                      value={schedulerInterval}
                      onChange={(e) => {
                        const v = parseInt(e.target.value)
                        if (!isNaN(v) && v >= 1 && v <= 72) handleSchedulerIntervalChange(v)
                      }}
                      className={cn(
                        "w-10 text-center text-xs rounded px-1 py-0.5 border outline-none transition-colors",
                        schedulerEnabled
                          ? "bg-t-indigo-light border-t-indigo-line text-t-indigo focus:border-t-indigo"
                          : "bg-t-cyan-light border-t-cyan-line text-t-cyan focus:border-t-cyan"
                      )}
                    />
                    <span className={cn(
                      "text-xs",
                      schedulerEnabled ? "text-t-indigo" : "text-t-cyan"
                    )}>h</span>
                  </div>
                  {/* 运行状态指示灯 */}
                  {schedulerEnabled && (
                    <span className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      schedulerStatus?.isCollecting
                        ? "bg-t-orange animate-pulse"
                        : "bg-t-green"
                    )} />
                  )}
                </div>
                {/* 调度详情 */}
                {schedulerEnabled && schedulerStatus && (
                  <div className="flex items-center gap-2 text-xs text-content-subtle">
                    {schedulerStatus.nextRunAt && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        下次 {new Date(schedulerStatus.nextRunAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                    {schedulerStatus.lastRunAt && (
                      <span className={cn(
                        "px-1.5 py-0.5 rounded",
                        schedulerStatus.lastRunStatus === 'success' ? "accent-green" :
                        schedulerStatus.lastRunStatus === 'failed' ? "accent-red" :
                        "accent-orange"
                      )}>
                        {schedulerStatus.lastRunStatus === 'success' ? '上次成功' :
                         schedulerStatus.lastRunStatus === 'failed' ? '上次失败' : '上次跳过'}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>

            <FilterBar
              filters={filters}
              onChange={setFilters}
              keywords={keywords}
            />

            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <div className="w-6 h-6 border-2 border-line border-t-t-blue rounded-full animate-spin" />
              </div>
            ) : hotspots.length === 0 ? (
              <div className="text-center py-16 rounded-xl border border-line/50 bg-surface-alt shadow-sm">
                <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-surface-dim/30 flex items-center justify-center">
                  <Radio className="w-6 h-6 text-content-subtle" />
                </div>
                <p className="text-content-muted">暂无热点数据</p>
                <p className="text-xs text-content-subtle mt-1">添加关键词开始监控</p>
              </div>
            ) : (
              <div className="space-y-3">
                {hotspots.map((h) => (
                  <HotspotCard
                    key={h.id}
                    hotspot={h}
                    keywordText={keywords.find((k) => k.id === h.keywordId)?.text}
                    onDelete={handleDeleteHotspot}
                    onOpenChat={setChatHotspot}
                    llmReady={llmReady}
                    onToast={showToast}
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && !isLoading && (
              <div className="flex items-center justify-center gap-3 pt-4">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-2 rounded-lg bg-surface-alt/50 border border-line/50 text-content-muted disabled:opacity-30 hover:border-line"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-content-muted">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-2 rounded-lg bg-surface-alt/50 border border-line/50 text-content-muted disabled:opacity-30 hover:border-line"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Keywords Tab */}
        {activeTab === 'keywords' && (
          <div className="space-y-6">
            <KeywordAddForm onAdd={handleAddKeyword} />

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence>
                {keywords.map((k, i) => (
                  <KeywordCard
                    key={k.id}
                    keyword={k}
                    index={i}
                    onToggle={handleToggleKeyword}
                    onDelete={handleDeleteKeyword}
                  />
                ))}
              </AnimatePresence>
            </div>

            {keywords.length === 0 && (
              <div className="text-center py-16 rounded-xl border border-line/50 bg-surface-alt shadow-sm">
                <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-surface-dim/30 flex items-center justify-center">
                  <Target className="w-6 h-6 text-content-subtle" />
                </div>
                <p className="text-content-muted">尚未设置监控词</p>
              </div>
            )}
          </div>
        )}

        {/* Search Tab */}
        {activeTab === 'search' && (
          <div className="space-y-6">
            <form onSubmit={handleSearch} className="relative flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-content-muted pointer-events-none z-10" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索热点内容..."
                  className="w-full pl-12 pr-4 py-2.5 rounded-lg bg-surface-alt backdrop-blur-sm border border-line text-content placeholder-content-subtle focus:outline-none focus:border-t-blue focus:ring-2 focus:ring-t-blue/20"
                />
              </div>
              <button
                type="submit"
                disabled={!searchQuery.trim() || isLoading}
                className="px-6 py-2.5 rounded-lg bg-[var(--accent-blue)] text-white font-medium hover:opacity-90 hover:shadow-lg hover:shadow-t-blue/10 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                搜索
              </button>
            </form>

            {isLoading ? (
              <div className="flex justify-center py-8">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="w-6 h-6 border-2 border-line border-t-t-blue rounded-full"
                />
              </div>
            ) : searchResults.length > 0 ? (
              <div className="space-y-3">
                {searchResults.map((h) => (
                  <HotspotCard
                    key={h.id}
                    hotspot={h}
                    keywordText={keywords.find((k) => k.id === h.keywordId)?.text}
                    onDelete={handleDeleteHotspot}
                    onOpenChat={setChatHotspot}
                    llmReady={llmReady}
                    onToast={showToast}
                  />
                ))}
              </div>
            ) : searchQuery && (
              <div className="text-center py-8 text-content-muted">
                输入关键词后点击搜索
              </div>
            )}
          </div>
        )}
      </main>

      {/* 聊天面板 */}
      <AnimatePresence>
        {chatHotspot && (
          <HotspotChat
            hotspot={chatHotspot}
            onClose={() => setChatHotspot(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
