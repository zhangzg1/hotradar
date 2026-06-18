import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sun, Moon, Monitor } from 'lucide-react'
import { useTheme, type ThemeMode } from '@/contexts/ThemeContext'

const themeOptions: { mode: ThemeMode; icon: typeof Sun; label: string; description: string }[] = [
  { mode: 'light', icon: Sun, label: '浅色模式', description: '始终使用浅色主题' },
  { mode: 'dark', icon: Moon, label: '深色模式', description: '始终使用深色主题' },
  { mode: 'auto', icon: Monitor, label: '自动模式', description: '跟随系统主题设置' },
]

export function ThemeSwitcher() {
  const { mode, resolvedTheme, setMode } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const ActiveIcon = resolvedTheme === 'dark' ? Moon : Sun

  return (
    <div className="relative" ref={ref}>
      <motion.button
        onClick={() => setOpen(!open)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="flex items-center justify-center w-9 h-9 rounded-full
          bg-surface-alt border border-line
          text-content-alt hover:bg-surface-dim hover:text-content
          transition-colors"
        title="切换主题"
      >
        <ActiveIcon className="w-4 h-4" />
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-64
              bg-surface-alt rounded-xl border border-line shadow-lg
              py-1.5 z-50 overflow-hidden"
          >
            {themeOptions.map(({ mode: optMode, icon: Icon, label, description }) => {
              const isActive = mode === optMode
              return (
                <button
                  key={optMode}
                  onClick={() => { setMode(optMode); setOpen(false) }}
                  className={`w-full flex items-center gap-3 px-4 py-3 transition-colors
                    ${isActive
                      ? 'bg-[var(--active-bg)] text-[var(--active-text)]'
                      : 'text-content-alt hover:bg-surface-dim'
                    }`}
                >
                  <div className={`flex items-center justify-center w-8 h-8 rounded-lg
                    ${isActive ? 'bg-[var(--accent-blue-soft)] text-[var(--accent-blue)]' : 'bg-surface-dim text-content-muted'}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-semibold leading-tight">{label}</div>
                    <div className="text-xs text-content-muted mt-0.5">{description}</div>
                  </div>
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
