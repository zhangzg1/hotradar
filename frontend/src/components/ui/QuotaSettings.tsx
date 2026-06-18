import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Settings2, Smartphone } from 'lucide-react'
import { cn } from '@/lib/utils'
import { fetchQuotaApi, settingsApi, douyinCookieApi, type FetchQuotaResponse, type DouyinCookieStatusResponse } from '@/services/api'

const DEFAULT_QUOTAS: FetchQuotaResponse = {
  twitter: 8,
  youtube: 8,
  bilibili: 3,
  douyin: 3,
  bing: 2,
  sogou: 1,
  twitterEnabled: true,
  youtubeEnabled: true,
  bilibiliEnabled: true,
  douyinEnabled: true,
  bingEnabled: true,
  sogouEnabled: true,
  douyinCookieActive: false,
}

const SOURCE_META: { key: keyof FetchQuotaResponse; label: string; color: string; max: number }[] = [
  { key: 'twitter', label: 'Twitter', color: 'text-t-sky', max: 20 },
  { key: 'youtube', label: 'YouTube', color: 'text-t-red', max: 20 },
  { key: 'bilibili', label: 'Bilibili', color: 'text-t-pink', max: 20 },
  { key: 'douyin', label: '抖音', color: 'text-content-alt', max: 20 },
  { key: 'bing', label: 'Bing', color: 'text-t-cyan', max: 10 },
  { key: 'sogou', label: '搜狗', color: 'text-t-orange', max: 10 },
]

interface QuotaSettingsProps {
  onQuotasLoaded?: (quotas: FetchQuotaResponse) => void
  onToast?: (message: string, type: 'success' | 'error' | 'info') => void
  onDouyinLoginClick?: () => void
}

export function QuotaSettings({ onQuotasLoaded, onToast, onDouyinLoginClick }: QuotaSettingsProps) {
  const [show, setShow] = useState(false)
  const [quotas, setQuotas] = useState<FetchQuotaResponse>(DEFAULT_QUOTAS)
  const [saved, setSaved] = useState<FetchQuotaResponse>(DEFAULT_QUOTAS)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [twitterConfigured, setTwitterConfigured] = useState(false)
  const [douyinCookieActive, setDouyinCookieActive] = useState(false)
  const [douyinCookieStatus, setDouyinCookieStatus] = useState<DouyinCookieStatusResponse | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        if (dirty) {
          setQuotas(saved)
          setDirty(false)
        }
        setShow(false)
      }
    }
    if (show) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [show, dirty, saved])

  const handleOpen = async () => {
    if (!show) {
      setLoading(true)
      setShow(true)
      try {
        const [data, settingsData, douyinStatus] = await Promise.all([
          fetchQuotaApi.get(),
          settingsApi.get().catch(() => ({ twitterConfigured: false })),
          douyinCookieApi.getCookieStatus().catch(() => null),
        ])
        setQuotas(data)
        setSaved(data)
        setTwitterConfigured(settingsData.twitterConfigured)
        setDouyinCookieActive(data.douyinCookieActive ?? false)
        setDouyinCookieStatus(douyinStatus)
        onQuotasLoaded?.(data)
      } catch {
        setQuotas(DEFAULT_QUOTAS)
        setSaved(DEFAULT_QUOTAS)
      } finally {
        setLoading(false)
      }
    } else {
      if (dirty) {
        setQuotas(saved)
        setDirty(false)
      }
      setShow(false)
    }
  }

  const handleChange = (key: keyof FetchQuotaResponse, value: number) => {
    const meta = SOURCE_META.find(m => m.key === key)
    const max = meta?.max ?? 20
    const clamped = Math.min(max, Math.max(1, value))
    const next = { ...quotas, [key]: clamped }
    setQuotas(next)
    setDirty(
      Object.keys(next).some(k => next[k as keyof FetchQuotaResponse] !== saved[k as keyof FetchQuotaResponse])
    )
  }

  const handleToggle = (key: keyof FetchQuotaResponse) => {
    if (key === 'twitter' && !twitterConfigured) {
      onToast?.('请先在设置中配置 Twitter API Key', 'error')
      return
    }
    if (key === 'douyin' && !douyinCookieActive) {
      onToast?.('请先登录抖音获取 Cookie', 'error')
      return
    }
    const enabledKey = `${key}Enabled` as keyof FetchQuotaResponse
    const next = { ...quotas, [enabledKey]: !quotas[enabledKey] }
    setQuotas(next)
    setDirty(
      Object.keys(next).some(k => next[k as keyof FetchQuotaResponse] !== saved[k as keyof FetchQuotaResponse])
    )
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const data = await fetchQuotaApi.update(quotas)
      setSaved(data)
      setDirty(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败'
      onToast?.(msg, 'error')
    } finally {
      setSaving(false)
    }
  }

  // 抖音 Cookie 状态指示
  const getDouyinStatusDot = () => {
    if (!douyinCookieStatus?.hasCookie) {
      return { color: 'bg-surface-dim', label: '未登录' }
    }
    if (douyinCookieStatus.status === 'expired') {
      return { color: 'bg-t-red', label: '已过期' }
    }
    return { color: 'bg-t-green', label: '有效' }
  }

  return (
    <div className="relative" ref={panelRef}>
      <motion.button
        onClick={handleOpen}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className={cn(
          "flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all",
          show
            ? "accent-indigo shadow-lg shadow-t-blue/10"
            : "accent-indigo"
        )}
      >
        <Settings2 className="w-4 h-4" />
        <span className="hidden sm:inline">配额</span>
      </motion.button>

      <AnimatePresence>
        {show && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 z-50 w-60 bg-surface-alt rounded-lg border border-line shadow-xl overflow-hidden"
          >
            {/* 标题 */}
            <div className="px-3 py-2 border-b border-line/50 flex items-center justify-between">
              <span className="text-xs font-medium text-content-alt">采集配额设置</span>
              <span className="text-[10px] text-content-subtle">各数据源上限</span>
            </div>

            {/* 配额列表 */}
            <div className="p-2 space-y-1">
              {loading ? (
                <div className="py-4 text-center text-xs text-content-subtle">加载中...</div>
              ) : (
                SOURCE_META.map(({ key, label, color, max }) => {
                  const enabledKey = `${key}Enabled` as keyof FetchQuotaResponse
                  const isEnabled = quotas[enabledKey] as boolean
                  const isTwitterDisabled = key === 'twitter' && !twitterConfigured
                  const isDouyinDisabled = key === 'douyin' && !douyinCookieActive
                  const isDisabled = isTwitterDisabled || isDouyinDisabled

                  // 抖音 Cookie 状态信息
                  const douyinStatus = key === 'douyin' ? getDouyinStatusDot() : null

                  return (
                    <div key={key} className="flex items-center justify-between px-1 py-1">
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleToggle(key)}
                            className={cn(
                              "w-7 h-4 rounded-full relative transition-colors flex-shrink-0",
                              isDisabled && "cursor-not-allowed opacity-40"
                            )}
                            style={{
                              backgroundColor: (isEnabled && !isDisabled)
                                ? 'var(--toggle-on-bg)'
                                : 'var(--toggle-off-bg)'
                            }}
                          >
                            <span className={cn(
                              "absolute top-0.5 w-3 h-3 rounded-full transition-transform",
                              (isEnabled && !isDisabled) ? "left-3.5" : "left-0.5"
                            )}
                            style={{ backgroundColor: '#fff' }}
                            />
                          </button>
                          <span className={cn("text-xs font-medium", color, (!isEnabled || isDisabled) && "opacity-40")}>{label}</span>
                          {/* 抖音 Cookie 状态指示 */}
                          {douyinStatus && (
                            <span className="relative flex items-center justify-center" title={douyinStatus.label}>
                              <span className={cn("w-1.5 h-1.5 rounded-full", douyinStatus.color)} />
                              {douyinStatus.color === 'bg-t-green' && (
                                <span className="absolute w-1.5 h-1.5 rounded-full bg-t-green animate-ping opacity-40" />
                              )}
                            </span>
                          )}
                          {/* 抖音未登录时的登录按钮 */}
                          {isDouyinDisabled && (
                            <button
                              onClick={(e) => { e.stopPropagation(); onDouyinLoginClick?.() }}
                              className="flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] rounded bg-t-indigo-light text-t-indigo hover:bg-t-indigo-light transition-colors"
                            >
                              <Smartphone className="w-2.5 h-2.5" />
                              登录
                            </button>
                          )}
                        </div>
                        <input
                          type="number"
                          min={1}
                          max={max}
                          value={quotas[key] as number}
                          disabled={!isEnabled || isDisabled}
                          onChange={e => handleChange(key, parseInt(e.target.value) || 1)}
                          className={cn(
                            "w-12 h-6 text-center text-xs rounded transition-colors",
                            isEnabled && !isDisabled
                              ? "bg-surface-alt border border-line text-content focus:border-t-blue focus:outline-none"
                              : "bg-surface-alt border border-line text-content-muted cursor-not-allowed"
                          )}
                        />
                      </div>
                  )
                })
              )}
            </div>

            {/* 抖音 Cookie 状态详情 */}
            {douyinCookieStatus?.hasCookie && (
              <div className={cn(
                "px-3 py-1.5 text-[10px] flex items-center justify-between",
                douyinCookieStatus.status === 'expired'
                  ? "bg-[var(--accent-red-cta-bg)] border-t border-[var(--accent-red-cta-border)] text-[var(--accent-red-cta-text)]"
                  : "bg-[var(--accent-green-cta-bg)] border-t border-line text-[var(--accent-green-cta-text)]"
              )}>
                <span className="flex items-center gap-1.5">
                  <span className={cn("w-1.5 h-1.5 rounded-full", getDouyinStatusDot().color)} />
                  抖音 Cookie {getDouyinStatusDot().label}
                </span>
                {douyinCookieStatus.expiresAt && douyinCookieStatus.status === 'active' && (
                  <span>过期 {new Date(douyinCookieStatus.expiresAt).toLocaleDateString()}</span>
                )}
                {douyinCookieStatus.status === 'expired' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onDouyinLoginClick?.() }}
                    className="text-t-indigo hover:text-t-indigo"
                  >
                    重新登录
                  </button>
                )}
              </div>
            )}

            {/* 底部操作 */}
            {dirty && (
              <div className="px-3 py-2 border-t border-line/50 flex justify-end gap-2">
                <button
                  onClick={() => { setQuotas(saved); setDirty(false) }}
                  className="px-2.5 py-1 text-[11px] rounded bg-surface-dim/50 text-content-muted hover:bg-surface-dim hover:text-content-alt transition-colors"
                >
                  重置
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className={cn(
                    "px-2.5 py-1 text-[11px] rounded font-medium transition-colors",
                    saving
                      ? "bg-surface-dim/50 text-content-subtle cursor-wait"
                      : "accent-indigo"
                  )}
                >
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
