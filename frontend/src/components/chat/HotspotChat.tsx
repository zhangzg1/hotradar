import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Send, Loader2, MessageSquarePlus, Clock, Trash2, Check, Pencil, FileSearch } from 'lucide-react'
import { cn } from '@/lib/utils'
import { chatApi, type ChatMessage, type ChatSession, type Hotspot } from '@/services/api'
import { Tooltip } from '@/components/ui/Tooltip'
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer'

interface HotspotChatProps {
  hotspot: Hotspot
  onClose: () => void
}

export function HotspotChat({ hotspot, onClose }: HotspotChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [showSessions, setShowSessions] = useState(false)
  const [editingSession, setEditingSession] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [deletingSession, setDeletingSession] = useState<string | null>(null)
  // 流式输出状态
  const [streamingContent, setStreamingContent] = useState('')
  const [toolCallStatus, setToolCallStatus] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // 滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // 加载历史会话列表
  useEffect(() => {
    loadSessions()
  }, [hotspot.id])

  const loadSessions = async () => {
    try {
      const result = await chatApi.getSessions(hotspot.id)
      setSessions(result.data)
    } catch (e) {
      console.error('加载会话列表失败:', e)
    }
  }

  const loadSessionMessages = async (sid: string) => {
    try {
      setIsLoading(true)
      const msgs = await chatApi.getSessionMessages(hotspot.id, sid)
      setMessages(msgs)
      setSessionId(sid)
      setShowSessions(false)
    } catch (e) {
      console.error('加载会话消息失败:', e)
    } finally {
      setIsLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage = inputValue.trim()
    setInputValue('')
    setError(null)
    setStreamingContent('')
    setToolCallStatus(null)

    // 添加用户消息到列表（乐观更新）
    const tempUserMsg: ChatMessage = {
      id: 'temp-user',
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMsg])
    setIsLoading(true)

    try {
      // 使用流式API
      let accumulatedContent = ''
      let loadedHotspots: string[] = []

      await chatApi.streamChat(
        hotspot.id,
        userMessage,
        sessionId,
        // onContent: 收到内容片段
        (content) => {
          accumulatedContent += content
          setStreamingContent(accumulatedContent)
        },
        // onSession: 收到会话ID
        (sid) => {
          setSessionId(sid)
        },
        // onToolCall: 开始处理 Tool Calling
        (count) => {
          setToolCallStatus(`正在加载 ${count} 条相关热点...`)
        },
        // onLoadingHotspot: 加载具体热点
        () => {
          setToolCallStatus(`正在加载热点详情...`)
        },
        // onDone: 完成
        (hotspots) => {
          loadedHotspots = hotspots
          setToolCallStatus(null)
        },
        // onError: 错误
        (errorMsg) => {
          setError(errorMsg)
          // 移除临时消息
          setMessages(prev => prev.filter(m => m.id !== 'temp-user'))
        }
      )

      // 流式完成，添加最终消息
      const aiMsg: ChatMessage = {
        id: 'temp-ai',
        role: 'assistant',
        content: accumulatedContent,
        loaded_hotspots: loadedHotspots,
        created_at: new Date().toISOString(),
      }

      // 替换临时用户消息，添加AI回复
      setMessages(prev => [
        ...prev.filter(m => m.id !== 'temp-user'),
        { ...tempUserMsg, id: 'user-' + Date.now() },
        aiMsg,
      ])
      setStreamingContent('')

      // 刷新会话列表
      loadSessions()

    } catch (e: any) {
      console.error('发送消息失败:', e)
      setError(e.message || '发送失败，请重试')
      // 移除临时消息
      setMessages(prev => prev.filter(m => m.id !== 'temp-user'))
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const startNewSession = () => {
    setMessages([])
    setSessionId(null)
    setShowSessions(false)
    inputRef.current?.focus()
  }

  const handleDeleteSession = async (sid: string) => {
    try {
      await chatApi.deleteSession(hotspot.id, sid)
      setDeletingSession(null)
      // 如果删除的是当前会话，清空消息
      if (sessionId === sid) {
        setMessages([])
        setSessionId(null)
      }
      // 刷新会话列表
      loadSessions()
    } catch (e: any) {
      console.error('删除会话失败:', e)
      setError(e.message || '删除失败')
    }
  }

  const handleRenameSession = async (sid: string) => {
    if (!editingName.trim()) return
    try {
      await chatApi.renameSession(hotspot.id, sid, editingName.trim())
      setEditingSession(null)
      setEditingName('')
      // 刷新会话列表
      loadSessions()
    } catch (e: any) {
      console.error('重命名会话失败:', e)
      setError(e.message || '重命名失败')
    }
  }

  const startEditing = (s: ChatSession) => {
    setEditingSession(s.id)
    setEditingName(s.name || '')
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed right-0 top-0 h-full w-[520px] bg-surface/95 backdrop-blur-sm border-l border-line/50 shadow-xl z-50 flex flex-col"
    >
      {/* 头部 */}
      <div className="p-4 border-b border-line/50 flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-content truncate">{hotspot.title}</h3>
          <p className="text-xs text-content-subtle mt-1">热点问答</p>
        </div>
        <div className="flex items-center gap-2">
          <Tooltip content="历史会话">
            <button
              onClick={() => setShowSessions(!showSessions)}
              className="p-2 rounded-lg bg-surface-dim text-content-muted hover:bg-surface-dim hover:text-content-alt transition-colors"
            >
              <Clock className="w-4 h-4" />
            </button>
          </Tooltip>
          <Tooltip content="开始新对话">
            <button
              onClick={startNewSession}
              className="p-2 rounded-lg bg-surface-dim text-content-muted hover:bg-surface-dim hover:text-content-alt transition-colors"
            >
              <MessageSquarePlus className="w-4 h-4" />
            </button>
          </Tooltip>
          <Tooltip content="关闭">
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-surface-dim text-content-muted hover:bg-t-red-light hover:text-t-red transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* 会话列表 */}
      <AnimatePresence>
        {showSessions && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="border-b border-line/50 overflow-hidden"
          >
            <div className="p-3 pb-4 max-h-64 overflow-y-auto space-y-1">
              {sessions.length === 0 ? (
                <p className="text-xs text-content-subtle text-center py-2">暂无历史会话</p>
              ) : (
                sessions.map(s => (
                  <div
                    key={s.id}
                    className={cn(
                      'group flex items-center gap-2 p-2 rounded-lg hover:bg-surface-dim',
                      sessionId === s.id && 'bg-t-blue-light'
                    )}
                  >
                    {editingSession === s.id ? (
                      // 编辑模式
                      <div className="flex-1 flex items-center gap-1">
                        <input
                          type="text"
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleRenameSession(s.id)
                            if (e.key === 'Escape') {
                              setEditingSession(null)
                              setEditingName('')
                            }
                          }}
                          autoFocus
                          className="flex-1 bg-surface-alt rounded px-2 py-1 text-xs text-content outline-none border border-t-blue-line"
                        />
                        <button
                          onClick={() => handleRenameSession(s.id)}
                          className="p-1 text-t-green hover:text-t-green"
                        >
                          <Check className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingSession(null)
                            setEditingName('')
                          }}
                          className="p-1 text-content-muted hover:text-content-alt"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : deletingSession === s.id ? (
                      // 删除确认模式
                      <div className="flex-1 flex items-center justify-between">
                        <span className="text-xs text-t-red">确认删除？</span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleDeleteSession(s.id)}
                            className="p-1 text-t-green hover:text-t-green"
                          >
                            <Check className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => setDeletingSession(null)}
                            className="p-1 text-content-muted hover:text-content-alt"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      // 正常显示
                      <>
                        <button
                          onClick={() => loadSessionMessages(s.id)}
                          className="flex-1 min-w-0 text-xs"
                        >
                          <span className={cn(
                            'block truncate',
                            sessionId === s.id ? 'text-t-blue' : 'text-content-muted'
                          )}>
                            {s.name || `${s.message_count} 条消息`}
                          </span>
                          <span className="text-xs text-content-subtle">
                            {new Date(s.updated_at).toLocaleDateString()}
                          </span>
                        </button>
                        {/* 操作按钮 */}
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => startEditing(s)}
                            className="p-1 text-content-muted hover:text-t-blue"
                          >
                            <Pencil className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => setDeletingSession(s.id)}
                            className="p-1 text-content-muted hover:text-t-red"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-8">
            <p className="text-content-subtle text-sm">开始对话探索这条热点</p>
            <p className="text-content-subtle text-xs mt-2">AI会基于热点内容回答你的问题</p>
          </div>
        )}

        {messages.map(msg => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              'max-w-[85%] rounded-lg p-3',
              msg.role === 'user'
                ? 'ml-auto bg-[var(--chat-user-bg)] text-[var(--chat-user-text)]'
                : 'mr-auto bg-[var(--chat-ai-bg)] text-[var(--chat-ai-text)]'
            )}
          >
            {msg.role === 'user' ? (
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
            ) : (
              <MarkdownRenderer content={msg.content} />
            )}
            {msg.loaded_hotspots && msg.loaded_hotspots.length > 0 && (
              <div className="mt-2 pt-2 border-t border-line-alt/30">
                <p className="text-xs text-content-subtle flex items-center gap-1">
                  <FileSearch className="w-3 h-3" />
                  加载了 {msg.loaded_hotspots.length} 条相关热点
                </p>
              </div>
            )}
          </motion.div>
        ))}

        {/* 流式输出内容 */}
        {streamingContent && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mr-auto bg-[var(--chat-ai-bg)] rounded-lg p-3 max-w-[85%]"
          >
            <MarkdownRenderer content={streamingContent} />
          </motion.div>
        )}

        {/* Tool Calling 状态 */}
        {toolCallStatus && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mr-auto accent-blue rounded-lg p-2 max-w-[85%]"
          >
            <div className="flex items-center gap-2 text-t-blue">
              <FileSearch className="w-4 h-4 animate-pulse" />
              <span className="text-xs">{toolCallStatus}</span>
            </div>
          </motion.div>
        )}

        {/* 加载动画（等待开始） */}
        {isLoading && !streamingContent && !toolCallStatus && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mr-auto bg-[var(--chat-ai-bg)] rounded-lg p-3 max-w-[85%]"
          >
            <div className="flex items-center gap-2 text-content-muted">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">思考中...</span>
            </div>
          </motion.div>
        )}

        {/* 错误提示 */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mx-auto bg-t-red-light rounded-lg p-3 max-w-[85%] text-center"
          >
            <p className="text-sm text-t-red">{error}</p>
            <button
              onClick={sendMessage}
              className="mt-2 inline-flex items-center gap-1 text-xs text-t-red hover:text-t-red"
            >
              <Loader2 className="w-3 h-3" />
              重试
            </button>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="p-4 border-t border-line/50">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="输入问题..."
            disabled={isLoading}
            className="flex-1 bg-surface-dim rounded-lg px-4 py-2 text-sm text-content placeholder-content-subtle border border-line focus:border-t-blue focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !inputValue.trim()}
            className="p-2 rounded-lg bg-[var(--accent-blue)] text-white disabled:bg-surface-dim disabled:text-content-subtle disabled:cursor-not-allowed transition-all duration-200"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  )
}