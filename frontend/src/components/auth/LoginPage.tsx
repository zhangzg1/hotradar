import { useState } from 'react'
import { motion } from 'framer-motion'
import { authApi, setToken, setUser } from '@/services/api'
import { useTheme } from '@/contexts/ThemeContext'

interface LoginPageProps {
  onLogin: (token: string, user: { userId: string; username: string }) => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  useTheme()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [registerSuccess, setRegisterSuccess] = useState(false)

  const switchMode = (target: 'login' | 'register') => {
    setMode(target)
    setError('')
    setRegisterSuccess(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!username.trim()) {
      setError('请输入用户名')
      return
    }
    if (password.length < 6) {
      setError('密码至少 6 位')
      return
    }

    setLoading(true)
    try {
      if (mode === 'register') {
        const res = await authApi.register(username.trim(), password)
        if (!res.success) {
          setError(res.message || '注册失败')
          return
        }
        setRegisterSuccess(true)
        setUsername('')
        setPassword('')
        setTimeout(() => switchMode('login'), 1500)
        return
      }

      const loginRes = await authApi.login(username.trim(), password)
      if (!loginRes.success) {
        setError(loginRes.message || '登录失败')
        return
      }

      const { token, userId, username: name } = loginRes.data!
      setToken(token)
      setUser({ userId, username: name })
      onLogin(token, { userId, username: name })
    } catch (err: any) {
      setError(err.message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center relative overflow-hidden">
      {/* 背景装饰 */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-t-blue/5 rounded-full blur-3xl" />
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-t-purple/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-t-blue/3 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="bg-surface-alt rounded-xl border border-line shadow-2xl p-8">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <img src="/hotradar.png" alt="HotRadar" className="w-14 h-14 rounded-xl shadow-lg mb-4" />
            <h1 className="text-2xl font-bold text-content">HotRadar</h1>
            <p className="text-content-muted text-sm mt-1">
              {mode === 'login' ? '登录以继续使用' : '创建新账号'}
            </p>
          </div>

          {/* 注册成功提示 */}
          {registerSuccess && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-4 text-sm accent-green rounded-lg px-3 py-2 text-center"
            >
              注册成功，正在跳转登录...
            </motion.div>
          )}

          {/* 表单 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-content-alt mb-1.5">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="请输入用户名"
                className="w-full px-4 py-2.5 bg-surface border border-line rounded-lg text-content placeholder-content-subtle focus:border-t-blue focus:outline-none transition-colors"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-sm text-content-alt mb-1.5">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 位"
                className="w-full px-4 py-2.5 bg-surface border border-line rounded-lg text-content placeholder-content-subtle focus:border-t-blue focus:outline-none transition-colors"
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-sm accent-red rounded-lg px-3 py-2"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] hover:shadow-lg hover:shadow-[#6366F1]/20 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  处理中...
                </span>
              ) : mode === 'login' ? '登录' : '注册'}
            </button>
          </form>

          {/* 底部切换链接 */}
          <div className="mt-5 text-center text-sm text-content-muted">
            {mode === 'login' ? (
              <>
                还没有账号？
                <button
                  onClick={() => switchMode('register')}
                  className="text-t-blue hover:text-t-indigo ml-1 transition-colors"
                >
                  立即注册
                </button>
              </>
            ) : (
              <>
                已有账号？
                <button
                  onClick={() => switchMode('login')}
                  className="text-t-blue hover:text-t-indigo ml-1 transition-colors"
                >
                  返回登录
                </button>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}
