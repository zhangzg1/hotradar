import { useState } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Edit3, Trash2, Check, X, Activity, Target } from 'lucide-react'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import type { Keyword } from '@/services/api'

interface KeywordCardProps {
  keyword: Keyword
  index: number
  onToggle: (id: string) => void
  onDelete: (id: string) => void
  onEdit?: (id: string, text: string) => void
}

export function KeywordCard({ keyword, index, onToggle, onDelete, onEdit }: KeywordCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState(keyword.text)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleSaveEdit = () => {
    if (editText.trim() && editText !== keyword.text) {
      onEdit?.(keyword.id, editText.trim())
    }
    setIsEditing(false)
  }

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = () => {
    setShowDeleteConfirm(false)
    onDelete(keyword.id)
  }

  return (
    <>
      <motion.div
        layout
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ delay: index * 0.03 }}
        className={cn(
          "group relative p-3 rounded-lg border transition-all duration-200 backdrop-blur-sm",
          keyword.isActive
            ? "accent-active hover:border-t-blue"
            : "bg-surface-alt border-line hover:border-surface-elevated opacity-60"
        )}
      >
        <div className="flex items-center justify-between gap-3">
          {/* 开关 */}
          <button
            onClick={() => onToggle(keyword.id)}
            className="relative w-10 h-5 rounded-full transition-all"
            style={{ backgroundColor: keyword.isActive ? 'var(--toggle-on-bg)' : 'var(--toggle-off-bg)' }}
          >
            <motion.div
              animate={{ x: keyword.isActive ? 18 : 2 }}
              className="absolute top-0.5 w-4 h-4 rounded-full shadow-sm bg-white"
            />
          </button>

          {/* 文本 */}
          <div className="flex-1 min-w-0">
            {isEditing ? (
              <input
                type="text"
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveEdit()
                  if (e.key === 'Escape') setIsEditing(false)
                }}
                className="w-full px-2 py-1 rounded bg-surface-alt border border-t-blue-line text-content focus:outline-none focus:border-t-blue"
                autoFocus
              />
            ) : (
              <span className={cn(
                "truncate",
                keyword.isActive ? "text-content" : "text-content-muted"
              )}>
                {keyword.text}
              </span>
            )}
          </div>

          {/* 热点数量 */}
          {keyword.hotspotCount && keyword.hotspotCount > 0 && (
            <div className="flex items-center gap-1 text-xs text-t-blue">
              <Activity className="w-3 h-3" />
              <span>{keyword.hotspotCount}</span>
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {isEditing ? (
              <>
                <button onClick={handleSaveEdit} className="p-1.5 rounded hover:bg-t-green-light text-t-green">
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => setIsEditing(false)} className="p-1.5 rounded hover:bg-t-red-light text-t-red">
                  <X className="w-3.5 h-3.5" />
                </button>
              </>
            ) : (
              <>
                {onEdit && (
                  <button onClick={() => setIsEditing(true)} className="p-1.5 rounded hover:bg-t-blue-light text-t-blue">
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                )}
                <button onClick={handleDeleteClick} className="p-1.5 rounded hover:bg-t-red-light text-t-red">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      </motion.div>

      {/* 删除确认对话框 */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="确认删除"
        message={`确定要删除监控词 "${keyword.text}" 吗？删除后无法恢复。`}
        confirmText="删除"
        cancelText="取消"
        onConfirm={handleConfirmDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </>
  )
}

interface KeywordAddFormProps {
  onAdd: (text: string) => void
}

export function KeywordAddForm({ onAdd }: KeywordAddFormProps) {
  const [text, setText] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim()) {
      onAdd(text.trim())
      setText('')
    }
  }

  const hasContent = text.trim().length > 0

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-content-subtle" />
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入监控关键词..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-surface-alt backdrop-blur-sm border border-line text-content placeholder-content-subtle focus:outline-none focus:border-t-blue focus:ring-2 focus:ring-t-blue/20"
          />
        </div>
        <motion.button
          type="submit"
          whileHover={hasContent ? { scale: 1.02 } : {}}
          whileTap={hasContent ? { scale: 0.98 } : {}}
          disabled={!hasContent}
          className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] text-white font-medium hover:shadow-lg hover:shadow-[#6366F1]/20 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          添加
        </motion.button>
      </div>
    </form>
  )
}
