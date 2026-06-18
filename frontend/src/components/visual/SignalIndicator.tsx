import { cn } from '@/lib/utils'

interface ConnectionStatusProps {
  connected: boolean
}

export function ConnectionStatus({ connected }: ConnectionStatusProps) {
  return (
    <div className={cn(
      "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs",
      connected ? "bg-[#30d158]/10 text-[#30d158]" : "bg-[#ff453a]/10 text-[#ff453a]"
    )}>
      <div className={cn(
        "w-2 h-2 rounded-full",
        connected ? "bg-[#30d158]" : "bg-[#ff453a]"
      )} />
      {connected ? '已连接' : '断开'}
    </div>
  )
}