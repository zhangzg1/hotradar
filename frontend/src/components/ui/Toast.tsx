import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { X, Check, AlertCircle } from 'lucide-react'

interface ToastProps {
  message: string
  type: 'success' | 'error' | 'info'
  onClose?: () => void
}

export function Toast({ message, type, onClose }: ToastProps) {
  const config = {
    success: { icon: Check, bg: 'bg-t-green-light', border: 'border-t-green-line', text: 'text-t-green' },
    error: { icon: AlertCircle, bg: 'bg-t-red-light', border: 'border-t-red-line', text: 'text-t-red' },
    info: { icon: AlertCircle, bg: 'bg-t-blue-light', border: 'border-t-blue-line', text: 'text-t-blue' },
  }
  const { icon: Icon, bg, border, text } = config[type]

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, x: '-50%' }}
      animate={{ opacity: 1, y: 0, x: '-50%' }}
      exit={{ opacity: 0, y: -20 }}
      className={cn(
        'fixed top-6 left-1/2 z-[60] px-4 py-3 rounded-lg backdrop-blur-xl flex items-center gap-3 shadow-lg',
        bg, border, text, 'border'
      )}
    >
      <Icon className="w-4 h-4" />
      <span className="text-sm">{message}</span>
      {onClose && (
        <button onClick={onClose} className="p-1 hover:opacity-70">
          <X className="w-3 h-3" />
        </button>
      )}
    </motion.div>
  )
}

export function ToastContainer({ toasts }: { toasts: { id: string; message: string; type: 'success' | 'error' | 'info' }[] }) {
  return (
    <motion.div>
      {toasts.map((toast) => (
        <Toast key={toast.id} message={toast.message} type={toast.type} />
      ))}
    </motion.div>
  )
}