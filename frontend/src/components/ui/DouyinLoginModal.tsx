import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, QrCode, Loader2, CheckCircle2, XCircle, RefreshCw, LogOut } from 'lucide-react'
import { douyinCookieApi, type DouyinCookieStatusResponse } from '@/services/api'

interface DouyinLoginModalProps {
  open: boolean
  onClose: () => void
  onLoginSuccess?: () => void
  onToast?: (message: string, type: 'success' | 'error' | 'info') => void
}

type LoginPhase = 'idle' | 'loading_qr' | 'showing_qr' | 'success' | 'timeout' | 'failed'

export function DouyinLoginModal({ open, onClose, onLoginSuccess, onToast }: DouyinLoginModalProps) {
  const [phase, setPhase] = useState<LoginPhase>('idle')
  const [qrBase64, setQrBase64] = useState('')
  const [countdown, setCountdown] = useState(180)
  const [cookieStatus, setCookieStatus] = useState<DouyinCookieStatusResponse | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (open) {
      loadCookieStatus()
    }
    return () => {
      clearTimers()
    }
  }, [open])

  const clearTimers = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null }
  }, [])

  const loadCookieStatus = async () => {
    try {
      const status = await douyinCookieApi.getCookieStatus()
      setCookieStatus(status)
      if (status.hasCookie && status.status === 'active') {
        setPhase('success')
      } else {
        setPhase('idle')
      }
    } catch {
      setPhase('idle')
    }
  }

  const handleStartLogin = async () => {
    setPhase('loading_qr')
    try {
      const result = await douyinCookieApi.startLogin()
      if (result.error) {
        setPhase('failed')
        onToast?.(result.error, 'error')
        return
      }

      // 浏览器已有登录态，自动提取 Cookie 完成
      if (result.autoLogin) {
        await loadCookieStatus()
        setPhase('success')
        onLoginSuccess?.()
        onToast?.('检测到已有登录状态，自动登录成功', 'success')
        return
      }

      setQrBase64(result.qrCodeBase64)
      setPhase('showing_qr')
      setCountdown(180)
      startPolling(result.sessionId)
      startCountdown()
    } catch (e) {
      setPhase('failed')
      onToast?.('启动登录失败，请检查 Playwright 是否已安装', 'error')
    }
  }

  const startPolling = (sid: string) => {
    clearTimers()
    pollRef.current = setInterval(async () => {
      try {
        const result = await douyinCookieApi.getLoginStatus(sid)
        if (result.status === 'success') {
          clearTimers()
          setPhase('success')
          await loadCookieStatus()
          onLoginSuccess?.()
          onToast?.('抖音登录成功', 'success')
        } else if (result.status === 'timeout') {
          clearTimers()
          setPhase('timeout')
        } else if (result.status === 'failed' || result.status === 'not_found') {
          clearTimers()
          setPhase('failed')
        }
      } catch {
        // 轮询异常不中断
      }
    }, 3000)
  }

  const startCountdown = () => {
    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearTimers()
          setPhase('timeout')
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleRetry = () => {
    clearTimers()
    handleStartLogin()
  }

  const handleLogout = async () => {
    try {
      await douyinCookieApi.deleteCookie()
      setCookieStatus(null)
      setPhase('idle')
      onLoginSuccess?.()
      onToast?.('已退出抖音登录', 'info')
    } catch {
      onToast?.('退出登录失败', 'error')
    }
  }

  const formatCountdown = (s: number) => {
    const min = Math.floor(s / 60)
    const sec = s % 60
    return `${min}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            className="relative z-10 w-full max-w-sm mx-4 bg-surface-alt rounded-xl border border-line shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-line/50">
              <h2 className="text-base font-semibold text-content">抖音登录</h2>
              <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-dim text-content-muted hover:text-content-alt transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-6 flex flex-col items-center">
              {/* 已登录状态 */}
              {phase === 'success' && cookieStatus?.hasCookie && cookieStatus.status === 'active' && (
                <div className="text-center space-y-4 w-full">
                  <div className="w-16 h-16 rounded-full accent-green flex items-center justify-center mx-auto">
                    <CheckCircle2 className="w-8 h-8 text-t-green" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-t-green">抖音已连接</p>
                    {cookieStatus.expiresAt && (
                      <p className="text-xs text-content-subtle mt-1">
                        预计过期：{new Date(cookieStatus.expiresAt).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-1.5 mx-auto px-4 py-2 text-xs rounded-lg accent-red transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    退出登录
                  </button>
                </div>
              )}

              {/* 加载二维码中 */}
              {phase === 'loading_qr' && (
                <div className="text-center space-y-3 py-4">
                  <Loader2 className="w-10 h-10 text-t-indigo animate-spin mx-auto" />
                  <p className="text-sm text-content-muted">正在启动浏览器获取二维码...</p>
                </div>
              )}

              {/* 显示二维码 */}
              {phase === 'showing_qr' && qrBase64 && (
                <div className="text-center space-y-3 w-full">
                  <div className="w-48 h-48 mx-auto rounded-lg overflow-hidden border border-line bg-white">
                    <img
                      src={`data:image/png;base64,${qrBase64}`}
                      alt="抖音登录二维码"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <div className="flex items-center justify-center gap-2">
                    <QrCode className="w-4 h-4 text-t-indigo" />
                    <p className="text-sm text-content-alt">请使用抖音 App 扫码登录</p>
                  </div>
                  <div className="flex items-center justify-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 text-content-subtle animate-spin" />
                    <p className="text-xs text-content-subtle">
                      等待扫码... {formatCountdown(countdown)}
                    </p>
                  </div>
                </div>
              )}

              {/* 超时 */}
              {phase === 'timeout' && (
                <div className="text-center space-y-3 py-4">
                  <div className="w-14 h-14 rounded-full accent-orange flex items-center justify-center mx-auto">
                    <XCircle className="w-7 h-7 text-t-orange" />
                  </div>
                  <p className="text-sm text-t-orange">二维码已过期</p>
                  <button
                    onClick={handleRetry}
                    className="flex items-center gap-1.5 mx-auto px-4 py-2 text-xs rounded-lg accent-indigo transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    重新获取
                  </button>
                </div>
              )}

              {/* 失败 */}
              {phase === 'failed' && (
                <div className="text-center space-y-3 py-4">
                  <div className="w-14 h-14 rounded-full accent-red flex items-center justify-center mx-auto">
                    <XCircle className="w-7 h-7 text-t-red" />
                  </div>
                  <p className="text-sm text-t-red">登录失败</p>
                  <p className="text-xs text-content-subtle">请确保 Playwright 已正确安装</p>
                  <button
                    onClick={handleRetry}
                    className="flex items-center gap-1.5 mx-auto px-4 py-2 text-xs rounded-lg accent-indigo transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    重试
                  </button>
                </div>
              )}

              {/* 初始状态 */}
              {(phase === 'idle' || (phase === 'success' && (!cookieStatus?.hasCookie || cookieStatus.status !== 'active'))) && (
                <div className="text-center space-y-4 py-2">
                  <div className="w-16 h-16 rounded-full bg-surface-dim border border-line flex items-center justify-center mx-auto">
                    <QrCode className="w-8 h-8 text-content-muted" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-content">抖音数据源</p>
                    <p className="text-xs text-content-subtle mt-1">登录抖音后可启用抖音数据源</p>
                  </div>
                  <button
                    onClick={handleStartLogin}
                    className="px-5 py-2.5 text-sm font-medium rounded-lg accent-indigo transition-colors"
                  >
                    登录抖音
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
