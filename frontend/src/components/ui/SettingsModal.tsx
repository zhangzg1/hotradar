import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Cpu, Mail, Twitter, Loader2, AlertCircle, ExternalLink, Eye, EyeOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { settingsApi } from '@/services/api'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
  onSettingsChanged?: () => void
  onToast?: (message: string, type: 'success' | 'error' | 'info') => void
}

type TestState = 'idle' | 'testing' | 'success' | 'error'

export function SettingsModal({ open, onClose, onSettingsChanged, onToast }: SettingsModalProps) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // LLM
  const [llmBaseUrl, setLlmBaseUrl] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmModelName, setLlmModelName] = useState('')
  const [llmTestState, setLlmTestState] = useState<TestState>('idle')
  const [llmTestMsg, setLlmTestMsg] = useState('')

  // 邮箱
  const [notifyEmail, setNotifyEmail] = useState('')
  const [emailError, setEmailError] = useState('')

  // Twitter
  const [twitterApiKey, setTwitterApiKey] = useState('')
  const [twitterTestState, setTwitterTestState] = useState<TestState>('idle')
  const [twitterTestMsg, setTwitterTestMsg] = useState('')

  // 跟踪 Key 是否被修改
  const [llmKeyChanged, setLlmKeyChanged] = useState(false)
  const [twitterKeyChanged, setTwitterKeyChanged] = useState(false)

  // Key 显隐切换
  const [showLlmKey, setShowLlmKey] = useState(false)
  const [showTwitterKey, setShowTwitterKey] = useState(false)

  useEffect(() => {
    if (open) loadSettings()
  }, [open])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const data = await settingsApi.get()
      setLlmBaseUrl(data.llmBaseUrl || '')
      setLlmApiKey(data.llmApiKey || '')
      setLlmModelName(data.llmModelName || '')
      setLlmTestState('idle')
      setNotifyEmail(data.notifyEmail || '')
      setTwitterApiKey(data.twitterApiKey || '')
      setTwitterTestState('idle')
      setLlmKeyChanged(false)
      setTwitterKeyChanged(false)
    } catch {
      // 使用默认值
    } finally {
      setLoading(false)
    }
  }

  const validateEmail = (email: string) => {
    if (!email) { setEmailError(''); return true }
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    setEmailError(valid ? '' : '邮箱格式不正确')
    return valid
  }

  const handleTestLlm = async () => {
    if (!llmBaseUrl || !llmApiKey || !llmModelName) return
    setLlmTestState('testing')
    setLlmTestMsg('')
    try {
      const result = await settingsApi.testLlm(llmBaseUrl, llmApiKey, llmModelName)
      if (result.success) {
        setLlmTestState('success')
        onToast?.(result.message, 'success')
      } else {
        setLlmTestState('error')
        setLlmTestMsg(result.message)
      }
    } catch {
      setLlmTestState('error')
      setLlmTestMsg('测试请求失败')
    }
  }

  const handleTestTwitter = async () => {
    if (!twitterApiKey) return
    setTwitterTestState('testing')
    setTwitterTestMsg('')
    try {
      const result = await settingsApi.testTwitter(twitterApiKey)
      if (result.success) {
        setTwitterTestState('success')
        onToast?.(result.message, 'success')
      } else {
        setTwitterTestState('error')
        setTwitterTestMsg(result.message)
      }
    } catch {
      setTwitterTestState('error')
      setTwitterTestMsg('测试请求失败')
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const data: Record<string, unknown> = {
        llmBaseUrl: llmBaseUrl || null,
        llmModelName: llmModelName || null,
        notifyEmail: notifyEmail || null,
      }
      if (llmKeyChanged) {
        data.llmApiKey = llmApiKey || null
      }
      if (llmTestState === 'success') {
        data.llmTested = true
      }
      if (twitterKeyChanged) {
        data.twitterApiKey = twitterApiKey || null
      }
      if (twitterTestState === 'success') {
        data.twitterTested = true
      }
      await settingsApi.update(data)
      onSettingsChanged?.()
      onClose()
    } catch {
      // 保存失败
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full px-3 py-2 text-sm bg-surface border border-line rounded-lg text-content placeholder-content-subtle focus:border-t-blue focus:outline-none transition-colors"

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
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            className="relative z-10 w-full max-w-lg mx-4 bg-surface-alt rounded-xl border border-line shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-line/50">
              <h2 className="text-base font-semibold text-content">设置</h2>
              <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-dim/50 text-content-muted hover:text-content transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-5 max-h-[70vh] overflow-y-auto">
              {loading ? (
                <div className="py-8 text-center text-sm text-content-subtle">加载中...</div>
              ) : (
                <>
                  {/* LLM 配置 */}
                  <section>
                    <div className="flex items-center gap-2 mb-3">
                      <Cpu className="w-4 h-4 text-t-indigo" />
                      <h3 className="text-sm font-medium text-content">LLM配置</h3>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs text-content-muted mb-1">Base URL</label>
                        <input type="text" value={llmBaseUrl} onChange={e => { setLlmBaseUrl(e.target.value); setLlmTestState('idle') }} placeholder="例如：https://open.bigmodel.cn/api/paas/v4/" className={inputCls} />
                      </div>
                      <div>
                        <label className="block text-xs text-content-muted mb-1">API Key</label>
                        <div className="relative">
                          <input type={showLlmKey ? "text" : "password"} value={llmApiKey} onChange={e => { setLlmApiKey(e.target.value); setLlmKeyChanged(true); setLlmTestState('idle') }} placeholder="输入您的API密钥" className="w-full px-3 py-2 pr-9 text-sm bg-surface border border-line rounded-lg text-content placeholder-content-subtle focus:border-t-blue focus:outline-none transition-colors" />
                          <button type="button" onClick={() => setShowLlmKey(!showLlmKey)} className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-content-muted hover:text-content transition-colors">
                            {showLlmKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs text-content-muted mb-1">模型名称</label>
                        <input type="text" value={llmModelName} onChange={e => { setLlmModelName(e.target.value); setLlmTestState('idle') }} placeholder="例如：glm-4.7-flash" className={inputCls} />
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleTestLlm}
                          disabled={llmTestState === 'testing' || !llmBaseUrl || !llmApiKey || !llmModelName}
                          className={cn(
                            "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                            llmTestState === 'testing' || !llmBaseUrl || !llmApiKey || !llmModelName
                              ? "bg-surface-dim text-content-subtle cursor-default"
                              : "accent-indigo"
                          )}
                        >
                          {llmTestState === 'testing' ? (
                            <span className="flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" /> 测试中</span>
                          ) : '测试连接'}
                        </button>
                      </div>
                      {llmTestMsg && llmTestState === 'error' && (
                        <div className="flex items-start gap-1.5 text-xs p-2 rounded-lg bg-t-red-light text-[var(--accent-red)]">
                          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                          <span>{llmTestMsg}</span>
                        </div>
                      )}
                    </div>
                  </section>

                  {/* 通知邮箱 */}
                  <section>
                    <div className="flex items-center gap-2 mb-3">
                      <Mail className="w-4 h-4 text-t-sky" />
                      <h3 className="text-sm font-medium text-content">通知邮箱</h3>
                    </div>
                    <div>
                      <input
                        type="email"
                        value={notifyEmail}
                        onChange={e => { setNotifyEmail(e.target.value); validateEmail(e.target.value) }}
                        onBlur={() => validateEmail(notifyEmail)}
                        placeholder="接收通知的邮箱地址"
                        className={cn(
                          "w-full px-3 py-2 text-sm bg-surface/60 border rounded-lg text-content placeholder-content-subtle focus:outline-none transition-colors",
                          emailError
                            ? "border-t-red-line focus:border-t-red"
                            : "border-line/50 focus:border-t-indigo"
                        )}
                      />
                      {emailError && <p className="mt-1 text-xs text-t-red">{emailError}</p>}
                    </div>
                  </section>

                  {/* Twitter API 配置 */}
                  <section>
                    <div className="flex items-center gap-2 mb-3">
                      <Twitter className="w-4 h-4 text-t-sky" />
                      <h3 className="text-sm font-medium text-content">Twitter API</h3>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <div className="relative">
                          <input
                            type={showTwitterKey ? "text" : "password"}
                            value={twitterApiKey}
                            onChange={e => { setTwitterApiKey(e.target.value); setTwitterKeyChanged(true); setTwitterTestState('idle') }}
                            placeholder="请输入 Twitter API Key"
                            className="w-full px-3 py-2 pr-9 text-sm bg-surface border border-line rounded-lg text-content placeholder-content-subtle focus:border-t-blue focus:outline-none transition-colors"
                          />
                          <button type="button" onClick={() => setShowTwitterKey(!showTwitterKey)} className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-content-muted hover:text-content transition-colors">
                            {showTwitterKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleTestTwitter}
                          disabled={twitterTestState === 'testing' || !twitterApiKey}
                          className={cn(
                            "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                            twitterTestState === 'testing' || !twitterApiKey
                              ? "bg-surface-dim text-content-subtle cursor-default"
                              : "accent-indigo"
                          )}
                        >
                          {twitterTestState === 'testing' ? (
                            <span className="flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" /> 测试中</span>
                          ) : '测试连接'}
                        </button>
                      </div>
                      {twitterTestMsg && twitterTestState === 'error' && (
                        <div className="flex items-start gap-1.5 text-xs p-2 rounded-lg bg-t-red-light text-[var(--accent-red)]">
                          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                          <span>{twitterTestMsg}</span>
                        </div>
                      )}
                      <p className="text-[11px] text-content-subtle">
                        前往
                        <a
                          href="https://twitterapi.io/dashboard"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-t-indigo hover:text-t-indigo mx-1 inline-flex items-center gap-0.5"
                        >
                          twitterapi.io <ExternalLink className="w-3 h-3" />
                        </a>
                        获取 API Key
                      </p>
                    </div>
                  </section>
                </>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 px-5 py-4 border-t border-line/50">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm rounded-lg bg-surface-dim text-content-muted hover:bg-surface-elevated hover:text-content-alt transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className={cn(
                  "px-4 py-2 text-sm rounded-lg font-medium transition-colors",
                  saving
                    ? "bg-surface-dim text-content-subtle cursor-wait"
                    : "accent-indigo"
                )}
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
