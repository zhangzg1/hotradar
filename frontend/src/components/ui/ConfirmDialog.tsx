import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, X } from 'lucide-react'

interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          {/* 背景遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onCancel}
          />

          {/* 对话框 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-sm mx-4 p-6 rounded-xl bg-surface-alt border border-line shadow-xl"
          >
            {/* 关闭按钮 */}
            <button
              onClick={onCancel}
              className="absolute top-3 right-3 p-1 rounded-lg hover:bg-surface-dim/50 text-content-muted hover:text-content-alt transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            {/* 图标 */}
            <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-[var(--accent-red-cta-bg)] flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-[var(--accent-red)]" />
            </div>

            {/* 标题 */}
            <h3 className="text-lg font-semibold text-content text-center mb-2">{title}</h3>

            {/* 消息 */}
            <p className="text-sm text-content-muted text-center mb-6">{message}</p>

            {/* 按钮 */}
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 px-4 py-2.5 rounded-lg bg-surface-dim border border-line text-content-alt hover:bg-surface-elevated hover:text-content transition-colors"
              >
                {cancelText}
              </button>
              <button
                onClick={onConfirm}
                className="flex-1 px-4 py-2.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}