import { useState, useRef, useEffect, type ComponentType } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { Keyword } from '@/services/api'
import { BilibiliIcon } from '@/components/icons/BilibiliIcon'
import { DouyinIcon } from '@/components/icons/DouyinIcon'
import { YouTubeIcon } from '@/components/icons/YouTubeIcon'
import {
  ArrowUpDown,
  ChevronDown,
  Check,
  Filter,
  Clock,
  Flame,
  Target,
  Globe,
  Twitter,
  Search,
  RefreshCw,
} from 'lucide-react'

export interface FilterState {
  sources: string[]
  importances: string[]
  keywordIds: string[]
  timeRange: string
  sortBy: string
  sortOrder: string
}

export const defaultFilterState: FilterState = {
  sources: [],
  importances: [],
  keywordIds: [],
  timeRange: '',
  sortBy: 'createdAt',
  sortOrder: 'desc',
}

interface FilterBarProps {
  filters: FilterState
  onChange: (filters: FilterState) => void
  keywords: Keyword[]
}

const SORT_OPTIONS = [
  { value: 'createdAt', label: '最新抓取', icon: Clock },
  { value: 'publishedAt', label: '最新发布', icon: Clock },
  { value: 'importance', label: '重要程度', icon: Flame },
  { value: 'relevance', label: '相关性', icon: Target },
]

const SOURCE_OPTIONS = [
  { value: 'twitter', label: 'Twitter', icon: Twitter },
  { value: 'youtube', label: 'YouTube', icon: YouTubeIcon },
  { value: 'bilibili', label: 'Bilibili', icon: BilibiliIcon },
  { value: 'douyin', label: '抖音', icon: DouyinIcon },
  { value: 'bing', label: 'Bing', icon: Globe },
  { value: 'sogou', label: '搜狗', icon: Search },
]

const IMPORTANCE_OPTIONS = [
  { value: 'urgent', label: '紧急', color: 'text-t-pink' },
  { value: 'high', label: '高', color: 'text-t-orange' },
  { value: 'medium', label: '中', color: 'text-t-purple' },
  { value: 'low', label: '低', color: 'text-t-green' },
]

const TIME_OPTIONS = [
  { value: '', label: '全部时间' },
  { value: '12h', label: '最近 12 小时' },
  { value: '24h', label: '最近 24 小时' },
  { value: '7d', label: '最近 7 天' },
  { value: '14d', label: '最近 14 天' },
]

interface MultiSelectDropdownProps {
  label: string
  options: { value: string; label: string; color?: string; icon?: ComponentType<{ className?: string }> }[]
  selected: string[]
  onChange: (selected: string[]) => void
  single?: boolean
  height?: string
}

function MultiSelectDropdown({ label, options, selected, onChange, single = false, height = 'h-9' }: MultiSelectDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (value: string) => {
    if (single) {
      onChange(value === selected[0] ? [] : [value])
    } else {
      if (selected.includes(value)) {
        onChange(selected.filter((v) => v !== value))
      } else {
        onChange([...selected, value])
      }
    }
    if (single) setOpen(false)
  }

  const isActive = selected.length > 0
  const selectedLabels = selected.map((v) => options.find((o) => o.value === v)?.label || v)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          `flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs transition-all ${height}`,
          isActive
            ? "accent-active"
            : "border border-line text-content-muted hover:bg-surface-dim hover:text-content-alt"
        )}
      >
        <span>{isActive ? selectedLabels.join(', ') : label}</span>
        <ChevronDown className={cn("w-3 h-3 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute left-0 top-full mt-1 z-50 min-w-[160px] bg-surface-alt rounded-lg border border-line shadow-xl p-1"
          >
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleSelect(opt.value)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-colors",
                  selected.includes(opt.value)
                    ? "accent-active bg-[var(--active-bg)] text-[var(--active-text)]"
                    : "text-content-muted hover:bg-surface-dim hover:text-content-alt"
                )}
              >
                {opt.icon && <opt.icon className="w-3.5 h-3.5" />}
                <span className={cn(opt.color)}>{opt.label}</span>
                {selected.includes(opt.value) && <Check className="w-3.5 h-3.5 ml-auto" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function FilterBar({ filters, onChange, keywords }: FilterBarProps) {
  const [showFilters, setShowFilters] = useState(false)

  const update = (key: keyof FilterState, value: string[] | string) => {
    onChange({ ...filters, [key]: value })
  }

  const reset = () => {
    onChange({
      ...defaultFilterState,
      sortBy: filters.sortBy,
      sortOrder: filters.sortOrder,
    })
  }

  const hasActiveFilters = filters.sources.length > 0 || filters.importances.length > 0 || filters.keywordIds.length > 0 || filters.timeRange

  const keywordOptions = keywords.map((k) => ({ value: k.id, label: k.text }))

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* 排序按钮组 */}
      <div className="flex items-center gap-1 rounded-lg border p-1 bg-surface-alt border-line">
        <ArrowUpDown className="w-3.5 h-3.5 text-content-subtle ml-1" />
        {SORT_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => update('sortBy', opt.value)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-all h-8",
              filters.sortBy === opt.value
                ? "accent-active font-medium bg-[var(--active-bg)] text-[var(--active-text)]"
                : "text-content-muted hover:text-content-alt"
            )}
          >
            <opt.icon className="w-3.5 h-3.5" />
            {opt.label}
          </button>
        ))}
      </div>

      {/* 筛选按钮 */}
      <button
        onClick={() => setShowFilters(!showFilters)}
        className={cn(
          "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs transition-all h-9",
          showFilters || hasActiveFilters
            ? "accent-active"
            : "border border-line text-content-muted hover:bg-surface-dim hover:text-content-alt"
        )}
      >
        <Filter className="w-3.5 h-3.5" />
        筛选
        {hasActiveFilters && (
          <span className="w-4 h-4 rounded-full bg-blue-500 text-white text-[10px] flex items-center justify-center font-bold">
            {filters.sources.length + filters.importances.length + filters.keywordIds.length + (filters.timeRange ? 1 : 0)}
          </span>
        )}
      </button>

      {/* 筛选条件下拉 - 只在点击筛选按钮后显示 */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 flex-wrap"
          >
            <MultiSelectDropdown
              label="来源"
              options={SOURCE_OPTIONS}
              selected={filters.sources}
              onChange={(v) => update('sources', v)}
            />
            <MultiSelectDropdown
              label="重要程度"
              options={IMPORTANCE_OPTIONS}
              selected={filters.importances}
              onChange={(v) => update('importances', v)}
            />
            {keywordOptions.length > 0 && (
              <MultiSelectDropdown
                label="关键词"
                options={keywordOptions}
                selected={filters.keywordIds}
                onChange={(v) => update('keywordIds', v)}
              />
            )}
            <MultiSelectDropdown
              label="时间"
              options={TIME_OPTIONS}
              selected={filters.timeRange ? [filters.timeRange] : []}
              onChange={(v) => update('timeRange', v[0] || '')}
              single
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* 重置按钮 - 只在筛选展开且有筛选条件时显示 */}
      {showFilters && hasActiveFilters && (
        <button
          onClick={reset}
          className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs text-content-subtle hover:text-content-alt transition-colors h-9 border border-line"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          重置
        </button>
      )}
    </div>
  )
}