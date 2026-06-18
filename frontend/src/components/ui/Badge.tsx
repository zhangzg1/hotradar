import { cn } from '@/lib/utils'
import { BilibiliIcon } from '@/components/icons/BilibiliIcon'
import { DouyinIcon } from '@/components/icons/DouyinIcon'
import { YouTubeIcon } from '@/components/icons/YouTubeIcon'
import {
  AlertTriangle, Flame, Zap, Activity, Gauge,
  Twitter, Globe, Search, Target,
} from 'lucide-react'

interface BadgeProps {
  type: 'importance' | 'source' | 'keyword' | 'relevance'
  value: string | number
  size?: 'sm' | 'md'
}

export function Badge({ type, value, size = 'sm' }: BadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1 text-xs'

  if (type === 'importance') {
    const config = {
      urgent: { icon: AlertTriangle, class: 'badge-urgent', label: '紧急' },
      high: { icon: Flame, class: 'badge-high', label: '高' },
      medium: { icon: Zap, class: 'badge-medium', label: '中' },
      low: { icon: Activity, class: 'badge-low', label: '低' },
    }
    const { icon: Icon, class: cls, label } = config[value as keyof typeof config] || config.low
    return (
      <span className={cn(sizeClasses, cls, 'inline-flex items-center gap-1 rounded-md')}>
        <Icon className="w-3 h-3" />
        {label}
      </span>
    )
  }

  if (type === 'source') {
    const sourceConfig: Record<string, { icon: typeof Twitter | typeof BilibiliIcon | typeof DouyinIcon | typeof YouTubeIcon; label: string }> = {
      twitter: { icon: Twitter, label: 'Twitter' },
      youtube: { icon: YouTubeIcon, label: 'YouTube' },
      bilibili: { icon: BilibiliIcon, label: 'Bilibili' },
      douyin: { icon: DouyinIcon, label: '抖音' },
      bing: { icon: Globe, label: 'Bing' },
      sogou: { icon: Search, label: '搜狗' },
    }
    const { icon: Icon, label } = sourceConfig[value] || { icon: Globe, label: value }
    return (
      <span className={cn(sizeClasses, 'badge-source inline-flex items-center gap-1 rounded-md')}>
        <Icon className="w-3 h-3" />
        <span>{label}</span>
      </span>
    )
  }

  if (type === 'keyword') {
    return (
      <span className={cn(sizeClasses, 'badge-keyword inline-flex items-center gap-1 rounded-md')}>
        <Target className="w-3 h-3" />
        <span className="truncate max-w-[100px]">{value}</span>
      </span>
    )
  }

  if (type === 'relevance') {
    const score = typeof value === 'number' ? value : parseInt(value, 10)
    const colorClass = score >= 80 ? 'badge-relevance-high' : score >= 50 ? 'badge-relevance-medium' : 'badge-relevance-low'
    return (
      <span className={cn(sizeClasses, colorClass, 'inline-flex items-center gap-1 rounded-md')}>
        <Gauge className="w-3 h-3" />
        {score}%
      </span>
    )
  }

  return null
}