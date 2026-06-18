import { Activity, Clock, Calendar, Target } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: number | string
  icon: typeof Activity
  color: 'blue' | 'amber' | 'purple' | 'green' | 'violet'
  delay?: number
}

export function StatCard({ label, value, icon: Icon, color }: StatCardProps) {
  const colorConfig = {
    blue: { bg: 'accent-blue', text: 'text-[var(--accent-blue-cta-text)]' },
    amber: { bg: 'accent-orange', text: 'text-[var(--accent-orange-cta-text)]' },
    purple: { bg: 'accent-purple', text: 'text-[var(--accent-purple-cta-text)]' },
    green: { bg: 'accent-green', text: 'text-[var(--accent-green-cta-text)]' },
    violet: { bg: 'accent-green', text: 'text-[var(--accent-green-cta-text)]' },
  }
  const config = colorConfig[color]

  return (
    <div
      className={cn(
        "relative p-4 rounded-lg overflow-hidden shadow-sm transition-all duration-200 hover:scale-[1.02]",
        config.bg, "border"
      )}
    >
      <div className={cn("absolute top-3 right-3 opacity-40", config.text)}>
        <Icon className="w-5 h-5" />
      </div>

      <div className="relative">
        <div className="flex items-center gap-2 text-xs text-content-muted mb-2">
          <Icon className="w-3.5 h-3.5" />
          {label}
        </div>
        <div className={cn("text-2xl font-semibold", config.text)}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
      </div>
    </div>
  )
}

interface StatsGridProps {
  stats: { total: number; todayNew: number; weekNew: number; activeKeywords: number }
}

export function StatsGrid({ stats }: StatsGridProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard label="总热点" value={stats.total} icon={Activity} color="blue" />
      <StatCard label="今日新增" value={stats.todayNew} icon={Clock} color="amber" />
      <StatCard label="本周新增" value={stats.weekNew} icon={Calendar} color="purple" />
      <StatCard label="监控词" value={stats.activeKeywords} icon={Target} color="violet" />
    </div>
  )
}
