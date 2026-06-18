import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn, relativeTime } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import {
  ChevronDown,
  ChevronUp,
  Clock,
  Target,
  Eye,
  MessageCircle,
  Repeat2,
  Zap,
  User,
  FileText,
  Trash2,
  MessageSquarePlus,
} from 'lucide-react'
import type { Hotspot } from '@/services/api'

interface HotspotCardProps {
  hotspot: Hotspot
  keywordText?: string
  onDelete: (id: string) => void
  onOpenChat?: (hotspot: Hotspot) => void
  llmReady?: boolean
  onToast?: (message: string, type: 'success' | 'error' | 'info') => void
}

export function HotspotCard({ hotspot, keywordText, onDelete, onOpenChat, llmReady, onToast }: HotspotCardProps) {
  const [expandedReason, setExpandedReason] = useState(false)
  const [expandedContent, setExpandedContent] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const engagement = hotspot.engagement

  const handleDelete = () => {
    setShowDeleteConfirm(false)
    onDelete(hotspot.id)
  }

  return (
    <div className="group relative">
      <div className={cn(
        "relative p-4 rounded-lg",
        "bg-gradient-to-br from-surface-alt/50 to-surface/50 backdrop-blur-sm",
        "border border-line/50 hover:border-t-blue-line",
        "transition-all duration-200 overflow-hidden"
      )}>
        {/* 第一行：重要程度 + 来源 + 关键词 + 相关性 + 删除按钮 */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <Badge type="importance" value={hotspot.importance} />
          <Badge type="source" value={hotspot.source} />
          <Badge type="relevance" value={hotspot.relevance} />
          {keywordText && <Badge type="keyword" value={keywordText} />}

          {/* 删除按钮 */}
          <div className="ml-auto relative flex items-center gap-1">
            {onOpenChat && (
              <button
                onClick={() => {
                  if (!llmReady) {
                    onToast?.('请先在设置中配置并测试 LLM', 'error')
                    return
                  }
                  onOpenChat(hotspot)
                }}
                className="p-2 rounded-lg bg-t-blue-light text-t-blue hover:bg-t-blue-line hover:text-t-blue transition-colors"
                title="对话探索"
              >
                <MessageSquarePlus className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="p-2 rounded-lg bg-surface-dim text-content-subtle hover:bg-t-red-light hover:text-t-red transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>

            <AnimatePresence>
              {showDeleteConfirm && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="absolute right-0 top-full mt-2 z-50 bg-surface-alt/90 backdrop-blur-sm rounded-lg border border-line/50 shadow-lg p-3 w-48"
                >
                  <p className="text-sm text-content-muted mb-3">确认删除这条热点？</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="flex-1 px-3 py-1.5 rounded-md bg-surface-dim text-content-muted text-xs hover:bg-surface-dim"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleDelete}
                      className="flex-1 px-3 py-1.5 rounded-md bg-t-red-light text-t-red text-xs hover:bg-t-red-line"
                    >
                      删除
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* 标题 - 可点击链接 */}
        <a
          href={hotspot.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-base font-medium text-content mb-2 line-clamp-2 hover:text-t-blue transition-colors block"
        >
          {hotspot.title}
        </a>

        {/* AI摘要 */}
        {hotspot.summary && (
          <div className="mb-3 pl-3 border-l-2 border-t-blue-line">
            <span className="text-[10px] text-t-blue mr-2">AI摘要</span>
            <span className="text-sm text-content-muted">{hotspot.summary}</span>
          </div>
        )}

        {/* 作者信息 */}
        {hotspot.author?.name && (
          <div className="flex items-center gap-2 mb-3 text-xs text-content-muted">
            {hotspot.author.avatar ? (
              <img src={hotspot.author.avatar} alt="" className="w-5 h-5 rounded-full object-cover" />
            ) : (
              <User className="w-4 h-4 text-content-subtle" />
            )}
            <span>{hotspot.author.name}</span>
            {hotspot.author.username && (
              <span className="text-content-subtle">@{hotspot.author.username}</span>
            )}
            {hotspot.author.verified && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-t-blue-light text-t-blue">✓</span>
            )}
          </div>
        )}

        {/* 互动数据 */}
        {engagement && (
          <div className="flex flex-wrap items-center gap-3 mb-3 text-xs text-content-subtle">
            <span className="flex items-center gap-1">
              <Target className="w-3 h-3" />
              <span>{hotspot.relevance}% 相关</span>
            </span>
            {engagement.likeCount && engagement.likeCount > 0 && (
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3" />
                <span>{engagement.likeCount.toLocaleString()}</span>
              </span>
            )}
            {engagement.retweetCount && engagement.retweetCount > 0 && (
              <span className="flex items-center gap-1">
                <Repeat2 className="w-3 h-3" />
                <span>{engagement.retweetCount.toLocaleString()}</span>
              </span>
            )}
            {engagement.viewCount && engagement.viewCount > 0 && (
              <span className="flex items-center gap-1">
                <Eye className="w-3 h-3" />
                <span>{engagement.viewCount.toLocaleString()}</span>
              </span>
            )}
            {engagement.commentCount && engagement.commentCount > 0 && (
              <span className="flex items-center gap-1">
                <MessageCircle className="w-3 h-3" />
                <span>{engagement.commentCount.toLocaleString()}</span>
              </span>
            )}
          </div>
        )}

        {/* 时间 */}
        <div className="flex items-center gap-4 text-[11px] text-content-subtle">
          {hotspot.publishedAt && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              发布 {relativeTime(hotspot.publishedAt)}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            抓取 {relativeTime(hotspot.createdAt)}
          </span>
        </div>

        {/* AI分析 */}
        {hotspot.relevanceReason && (
          <div className="mt-2">
            <button
              onClick={() => setExpandedReason(!expandedReason)}
              className="flex items-center gap-1 text-[11px] text-t-blue hover:text-t-blue transition-colors"
            >
              {expandedReason ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              AI 分析
            </button>
            <AnimatePresence>
              {expandedReason && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <p className="text-xs text-content-muted mt-2 pl-3 border-l-2 border-t-blue-line">
                    {hotspot.relevanceReason}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* 原文内容 */}
        {hotspot.content && hotspot.content !== hotspot.summary && (
          <div className="mt-2">
            <button
              onClick={() => setExpandedContent(!expandedContent)}
              className="flex items-center gap-1 text-[11px] text-content-subtle hover:text-content-alt transition-colors"
            >
              {expandedContent ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              <FileText className="w-3 h-3" />
              原文内容
            </button>
            <AnimatePresence>
              {expandedContent && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <p className="text-xs text-content-muted mt-2 pl-3 border-l-2 border-linewhitespace-pre-wrap max-h-32 overflow-y-auto">
                    {hotspot.content}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}