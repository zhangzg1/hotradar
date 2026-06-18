import { cn } from '@/lib/utils'

interface YouTubeIconProps {
  className?: string
}

export function YouTubeIcon({ className }: YouTubeIconProps) {
  return (
    <svg
      viewBox="0 0 1024 1024"
      fill="currentColor"
      className={cn('w-4 h-4', className)}
    >
      <path d="M941.3 296.1c-10.3-38.6-40.7-69-79.2-79.3C792.5 200 512 200 512 200s-280.5 0-350.1 16.8c-38.6 10.3-69 40.7-79.3 79.3C66 365.6 66 512 66 512s0 146.4 16.6 215.9c10.3 38.6 40.7 69 79.3 79.3C231.5 824 512 824 512 824s280.5 0 350.1-16.8c38.6-10.3 69-40.7 79.2-79.3C958 658.4 958 512 958 512s0-146.4-16.7-215.9zM423 646V378l232 134-232 134z" />
    </svg>
  )
}
