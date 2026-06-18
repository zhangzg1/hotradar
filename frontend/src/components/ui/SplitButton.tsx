import { useState, useRef, useEffect, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { ChevronDown, Check } from 'lucide-react'

interface SplitButtonOption<T extends string | boolean> {
  value: T
  label: string
}

interface SplitButtonProps<T extends string | boolean> {
  options: SplitButtonOption<T>[]
  selectedValue: T
  onSelect: (value: T) => void
  onExecute: () => void
  isExecuting: boolean
  executeLabel: string
  executingLabel: string
  icon?: ReactNode
  primaryClassName?: string
  dropdownClassName?: string
  disabled?: boolean
  showCheck?: boolean
  variant?: 'primary' | 'secondary'
  progress?: { completed: number; total: number } | null
}

export function SplitButton<T extends string | boolean>({
  options,
  selectedValue,
  onSelect,
  onExecute,
  isExecuting,
  executeLabel,
  executingLabel,
  icon,
  primaryClassName,
  dropdownClassName,
  disabled = false,
  showCheck = true,
  variant = 'primary',
  progress,
}: SplitButtonProps<T>) {
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 基础样式 - 靛蓝半透明玻璃态
  const baseGradient = "accent-indigo hover:shadow-lg hover:shadow-t-indigo/10"
  // 次要样式 - 青色半透明玻璃态
  const secondaryStyle = "accent-cyan"

  const primaryStyle = variant === 'secondary' ? secondaryStyle : baseGradient
  const separatorColor = variant === 'secondary' ? "border-[var(--accent-cyan-border)]" : "border-[var(--accent-indigo-border)]"
  const dropdownActiveColor = variant === 'secondary' ? "bg-[var(--accent-cyan-hover-bg)]" : "bg-[var(--accent-indigo-hover-bg)]"
  const selectedOptionStyle = variant === 'secondary' ? "accent-cyan" : "accent-indigo"

  return (
    <div className="relative flex" ref={dropdownRef}>
      {/* 主按钮 */}
      <motion.button
        onClick={onExecute}
        disabled={disabled || isExecuting}
        whileHover={!isExecuting ? { scale: 1.02 } : {}}
        whileTap={!isExecuting ? { scale: 0.98 } : {}}
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-l-lg text-sm font-medium transition-all",
          isExecuting
            ? "bg-surface-dim/50 text-content-muted cursor-default border border-line/50"
            : primaryClassName || primaryStyle,
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        {isExecuting ? (
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-4 h-4 border-2 border-content-muted border-t-content-alt rounded-full"
          />
        ) : icon}
        {isExecuting
          ? (progress && progress.total > 0
              ? `${executingLabel} (${progress.completed}/${progress.total})`
              : executingLabel)
          : executeLabel}
      </motion.button>

      {/* 下拉按钮 - 无缝连接 */}
      <motion.button
        onClick={() => !isExecuting && setShowDropdown(!showDropdown)}
        disabled={isExecuting}
        whileHover={!isExecuting ? { scale: 1.02 } : {}}
        whileTap={!isExecuting ? { scale: 0.98 } : {}}
        className={cn(
          "flex items-center justify-center px-2 py-2 rounded-r-lg text-sm font-medium transition-all border-l",
          isExecuting
            ? "bg-surface-dim/50 text-content-muted cursor-default border border-line/50"
            : cn(separatorColor, dropdownClassName || primaryStyle),
          showDropdown && !isExecuting && dropdownActiveColor
        )}
      >
        <motion.div
          animate={{ rotate: showDropdown ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="w-4 h-4" />
        </motion.div>
      </motion.button>

      {/* 下拉菜单 */}
      <AnimatePresence>
        {showDropdown && !isExecuting && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute right-0 top-full mt-2 z-50 w-44 bg-surface-alt rounded-lg border border-line shadow-xl p-1"
          >
            {options.map((opt) => (
              <button
                key={String(opt.value)}
                onClick={() => {
                  onSelect(opt.value)
                  setShowDropdown(false)
                }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors",
                  selectedValue === opt.value
                    ? selectedOptionStyle
                    : "text-content-muted hover:bg-surface-dim hover:text-content-alt"
                )}
              >
                {showCheck && selectedValue === opt.value && <Check className="w-4 h-4" />}
                <span className={cn(!showCheck && "pl-4")}>{opt.label}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}