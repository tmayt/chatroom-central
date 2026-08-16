import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles.css'
import ErrorsPage from './ErrorsPage'
import { describeFetchError, openHtmlInNewTab } from './errorDisplay'

const SCROLL_THRESHOLD = 48
const FALLBACK_POLL_MS = 60000
const WS_PING_MS = 30000

function authHeaders(token, extra = {}) {
  const headers = { ...extra }
  if (token) headers.Authorization = `Token ${token}`
  return headers
}

function messagesEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false
  return a.every((msg, i) => {
    const other = b[i]
    return (
      msg.id === other.id &&
      msg.seen === other.seen &&
      msg.status === other.status &&
      msg.content === other.content
    )
  })
}

function mergeMessages(prev, incoming) {
  if (!incoming) return prev
  if (messagesEqual(prev, incoming)) return prev
  return incoming
}

function upsertMessage(prev, message) {
  const idx = prev.findIndex((m) => m.id === message.id)
  if (idx === -1) return [...prev, message]
  const next = [...prev]
  next[idx] = { ...next[idx], ...message }
  return next
}

function upsertConversation(prev, conversation) {
  if (!conversation) return prev
  const idx = prev.findIndex((c) => c.id === conversation.id)
  if (idx === -1) return [conversation, ...prev]
  const next = [...prev]
  next[idx] = { ...next[idx], ...conversation }
  next.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
  return next
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

function statusLabel(status) {
  switch (status) {
    case 'PENDING':
      return 'Sending…'
    case 'SENT':
      return 'Sent'
    case 'FAILED':
      return 'Failed'
    case 'RECEIVED':
      return 'Received'
    default:
      return status || ''
  }
}

export default function App() {
  const [offcanvasOpen, setOffcanvasOpen] = useState(false)
  const [conversations, setConversations] = useState([])
  const [selected, setSelected] = useState(null)
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([])
  const [token, setToken] = useState(localStorage.getItem('api_token') || '')
  const [loadingConversations, setLoadingConversations] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [search, setSearch] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [wsStatus, setWsStatus] = useState('disconnected')
  const [error, setError] = useState('')
  const [errorHtml, setErrorHtml] = useState('')
  const [showJumpButton, setShowJumpButton] = useState(false)
  const [page, setPage] = useState('chat')
  const [errorCount, setErrorCount] = useState(0)

  const refreshErrorCount = useCallback(async () => {
    if (!token) {
      setErrorCount(0)
      return
    }
    try {
      const res = await fetch('/api/v1/errors/?count_only=1', { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setErrorCount(data.count || 0)
      }
    } catch {
      // ignore
    }
  }, [token])

  const showError = (message, html = '') => {
    setError(message)
    setErrorHtml(html || '')
    if (html) refreshErrorCount()
  }

  const clearError = () => {
    setError('')
    setErrorHtml('')
  }

  const messagesRef = useRef(null)
  const convListRef = useRef(null)
  const isScrolledUpRef = useRef(false)
  const prevMessageIdsRef = useRef('')
  const initialConvLoadRef = useRef(true)
  const wsRef = useRef(null)
  const selectedRef = useRef(selected)

  useEffect(() => {
    selectedRef.current = selected
  }, [selected])

  const loadConversations = useCallback(async (showLoading = false) => {
    if (!token) {
      setConversations([])
      setLoadingConversations(false)
      return
    }
    if (showLoading) setLoadingConversations(true)
    try {
      const res = await fetch('/api/v1/conversations/', { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setConversations(data)
        clearError()
      } else {
        setConversations([])
        const err = await describeFetchError(res, 'Could not load conversations', {
          openTab: showLoading,
        })
        showError(err.message, err.html)
      }
    } catch {
      setConversations([])
      showError('Network error while loading conversations.')
    } finally {
      if (showLoading) setLoadingConversations(false)
      initialConvLoadRef.current = false
    }
  }, [token])

  const loadConversationDetail = useCallback(async (conversation, showLoading = false) => {
    if (!conversation || !token) {
      setMessages([])
      return
    }
    if (showLoading) setLoadingMessages(true)
    try {
      const res = await fetch(`/api/v1/conversations/${conversation.id}/`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setMessages((prev) => mergeMessages(prev, data.messages || []))
        setSelected((prev) => {
          if (prev?.id !== conversation.id) return prev
          return {
            ...prev,
            updated_at: data.updated_at || prev.updated_at,
            title: data.title ?? prev.title,
            is_closed: data.is_closed ?? prev.is_closed,
          }
        })
        clearError()
      } else {
        setMessages([])
        const err = await describeFetchError(res, 'Could not load messages', {
          openTab: showLoading,
        })
        showError(err.message, err.html)
      }
    } catch {
      setMessages([])
      showError('Network error while loading messages.')
    } finally {
      if (showLoading) setLoadingMessages(false)
    }
  }, [token])

  useEffect(() => {
    initialConvLoadRef.current = true
    loadConversations(true)
  }, [loadConversations])

  useEffect(() => {
    if (!selected) {
      setMessages([])
      return
    }
    isScrolledUpRef.current = false
    prevMessageIdsRef.current = ''
    setShowJumpButton(false)
    loadConversationDetail(selected, true)
  }, [selected?.id, loadConversationDetail])

  useEffect(() => {
    refreshErrorCount()
  }, [refreshErrorCount])

  useEffect(() => {
    if (!token) return undefined
    const interval = setInterval(() => {
      loadConversations(false)
      if (selectedRef.current) {
        loadConversationDetail(selectedRef.current, false)
      }
      refreshErrorCount()
    }, FALLBACK_POLL_MS)
    return () => clearInterval(interval)
  }, [token, loadConversations, loadConversationDetail, refreshErrorCount])

  useEffect(() => {
    if (!token) return undefined

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/admin/?token=${encodeURIComponent(token)}`
    let reconnectTimer = null
    let pingTimer = null
    let closedByUser = false

    const connect = () => {
      setWsStatus('connecting')
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setWsStatus('connected')
        clearError()
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, WS_PING_MS)
      }

      ws.onmessage = (event) => {
        let data
        try {
          data = JSON.parse(event.data)
        } catch {
          return
        }

        if (data.type === 'message.new' || data.type === 'message.updated') {
          if (data.conversation) {
            setConversations((prev) => upsertConversation(prev, data.conversation))
          }
          if (data.conversation_id === selectedRef.current?.id && data.message) {
            setMessages((prev) => upsertMessage(prev, data.message))
            setSelected((prev) =>
              prev?.id === data.conversation_id
                ? { ...prev, updated_at: data.conversation?.updated_at || prev.updated_at }
                : prev,
            )
          }
        }

        if (data.type === 'conversation.updated') {
          loadConversations(false)
          if (data.conversation_id === selectedRef.current?.id) {
            loadConversationDetail(selectedRef.current, false)
          }
        }
      }

      ws.onclose = () => {
        clearInterval(pingTimer)
        wsRef.current = null
        setWsStatus('disconnected')
        if (!closedByUser) {
          reconnectTimer = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      closedByUser = true
      clearTimeout(reconnectTimer)
      clearInterval(pingTimer)
      if (wsRef.current) wsRef.current.close()
    }
  }, [token, loadConversations, loadConversationDetail])

  useEffect(() => {
    if (!selected || !messages.length) return undefined
    const unseenInbound = messages.filter((m) => m.direction === 'IN' && m.seen !== true)
    if (!unseenInbound.length) return undefined

    const timer = setTimeout(async () => {
      try {
        await fetch(`/api/v1/conversations/${selected.id}/seen/`, {
          method: 'POST',
          headers: authHeaders(token, { 'Content-Type': 'application/json' }),
        })
        setMessages((msgs) =>
          msgs.map((msg) => (msg.direction === 'IN' ? { ...msg, seen: true } : msg)),
        )
        setConversations((prev) =>
          prev.map((c) => (c.id === selected.id ? { ...c, has_unseen: false } : c)),
        )
      } catch {
        // ignore
      }
    }, 2500)

    return () => clearTimeout(timer)
  }, [messages, selected, token])

  useEffect(() => {
    const el = messagesRef.current
    if (!el) return

    const currentIds = messages.map((m) => m.id).join(',')
    const hadNewMessages =
      currentIds !== prevMessageIdsRef.current &&
      messages.length >= prevMessageIdsRef.current.split(',').filter(Boolean).length

    if (hadNewMessages && !isScrolledUpRef.current) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight
      })
    }

    prevMessageIdsRef.current = currentIds
  }, [messages])

  const handleMessagesScroll = () => {
    const el = messagesRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const scrolledUp = distanceFromBottom > SCROLL_THRESHOLD
    isScrolledUpRef.current = scrolledUp
    setShowJumpButton(scrolledUp)
  }

  const jumpToLatest = () => {
    const el = messagesRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    isScrolledUpRef.current = false
    setShowJumpButton(false)
  }

  const reply = async () => {
    if (!selected || !text.trim() || sending) return
    setSending(true)
    try {
      const res = await fetch(`/api/v1/conversations/${selected.id}/reply/`, {
        method: 'POST',
        headers: authHeaders(token, { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text: text.trim() }),
      })
      if (res.ok) {
        const data = await res.json()
        setText('')
        clearError()
        if (data.message) {
          setMessages((prev) => upsertMessage(prev, data.message))
        }
      } else {
        const err = await describeFetchError(res, 'Failed to send reply')
        showError(err.message, err.html)
      }
    } catch {
      showError('Network error while sending reply.')
    } finally {
      setSending(false)
    }
  }

  const login = async (e) => {
    e?.preventDefault()
    setLoginError('')
    try {
      const res = await fetch('/api/v1/auth/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        if (res.status >= 500) {
          const err = await describeFetchError(res, 'Login failed')
          setLoginError(err.message)
          return
        }
        setLoginError('Invalid username or password.')
        return
      }
      const data = await res.json()
      if (data?.token) {
        setToken(data.token)
        localStorage.setItem('api_token', data.token)
        setPassword('')
      }
    } catch {
      setLoginError('Login failed. Please try again.')
    }
  }

  const logout = () => {
    setToken('')
    localStorage.removeItem('api_token')
    setConversations([])
    setSelected(null)
    setMessages([])
    setUsername('')
    setPassword('')
    setPage('chat')
    setErrorCount(0)
  }

  const filteredConversations = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return conversations
    return conversations.filter((c) => {
      const contact = (c.external_contact || '').toLowerCase()
      const last = (c.last_message || '').toLowerCase()
      const source = (c.source || '').toLowerCase()
      return contact.includes(q) || last.includes(q) || source.includes(q)
    })
  }, [conversations, search])

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-brand">
            <div className="brand-icon">💬</div>
            <h1>Chatroom Central</h1>
            <p className="text-muted">Sign in to manage conversations</p>
          </div>
          {loginError && <div className="alert alert-danger py-2">{loginError}</div>}
          <form onSubmit={login}>
            <label className="form-label">Username</label>
            <input
              className="form-control mb-3"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
            />
            <label className="form-label">Password</label>
            <input
              className="form-control mb-3"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
            />
            <button className="btn btn-primary w-100" type="submit">
              Sign in
            </button>
          </form>
          <hr />
          <p className="small text-muted mb-2">Or paste an API token (dev):</p>
          <input
            className="form-control form-control-sm"
            value={token}
            onChange={(e) => {
              setToken(e.target.value)
              localStorage.setItem('api_token', e.target.value)
            }}
            placeholder="Token"
          />
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        {page === 'chat' && (
          <button
            className="btn btn-icon d-md-none"
            type="button"
            onClick={() => setOffcanvasOpen(true)}
            aria-label="Open conversations"
          >
            ☰
          </button>
        )}
        <div className="app-header-title">
          <span className="brand-dot" />
          Chatroom Central
        </div>
        <nav className="app-nav">
          <button
            type="button"
            className={`nav-link-btn ${page === 'chat' ? 'active' : ''}`}
            onClick={() => setPage('chat')}
          >
            Chats
          </button>
          <button
            type="button"
            className={`nav-link-btn ${page === 'errors' ? 'active' : ''}`}
            onClick={() => {
              setPage('errors')
              setOffcanvasOpen(false)
            }}
          >
            Errors
            {errorCount > 0 && (
              <span className="error-count-badge">{errorCount > 99 ? '99+' : errorCount}</span>
            )}
          </button>
        </nav>
        <div className="app-header-actions">
          <span className={`ws-badge ws-${wsStatus}`}>
            {wsStatus === 'connected' ? 'Live' : wsStatus === 'connecting' ? 'Connecting…' : 'Offline'}
          </span>
          <button className="btn btn-outline-secondary btn-sm" type="button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {error && (
        <div className="app-alert">
          <span>{error}</span>
          <div className="app-alert-actions">
            {errorHtml && (
              <button
                type="button"
                className="btn btn-outline-light btn-sm"
                onClick={() => openHtmlInNewTab(errorHtml)}
              >
                View traceback
              </button>
            )}
            <button type="button" className="btn-close-alert" onClick={clearError}>
              ×
            </button>
          </div>
        </div>
      )}

      {page === 'errors' ? (
        <ErrorsPage token={token} onCountChange={setErrorCount} />
      ) : (
      <div className="app-layout">
        <aside className={`sidebar ${offcanvasOpen ? 'open' : ''}`}>
          <div className="sidebar-inner">
            <div className="sidebar-head">
              <h2>Conversations</h2>
              <button
                className="btn btn-icon d-md-none"
                type="button"
                onClick={() => setOffcanvasOpen(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <input
              className="form-control form-control-sm search-input"
              placeholder="Search contacts or messages…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div ref={convListRef} className="conversation-list">
              {loadingConversations && initialConvLoadRef.current ? (
                <div className="empty-state">Loading conversations…</div>
              ) : filteredConversations.length === 0 ? (
                <div className="empty-state">No conversations found</div>
              ) : (
                filteredConversations.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={`conversation-item ${selected?.id === c.id ? 'active' : ''} ${c.has_unseen ? 'unseen' : ''}`}
                    onClick={() => {
                      setSelected(c)
                      setOffcanvasOpen(false)
                    }}
                  >
                    <div className="conversation-top">
                      <span className="conversation-name">{c.external_contact || 'Unknown'}</span>
                      <span className="conversation-time">{formatTime(c.updated_at)}</span>
                    </div>
                    <div className="conversation-preview">{c.last_message || 'No messages yet'}</div>
                    <div className="conversation-meta">
                      <span className="source-pill">{c.source}</span>
                      {c.has_unseen && <span className="unseen-pill">New</span>}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </aside>

        {offcanvasOpen && (
          <button
            type="button"
            className="sidebar-backdrop d-md-none"
            aria-label="Close sidebar"
            onClick={() => setOffcanvasOpen(false)}
          />
        )}

        <main className="chat-panel">
          {!selected ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">📨</div>
              <h3>Select a conversation</h3>
              <p className="text-muted">Choose a chat from the sidebar to view messages and reply.</p>
            </div>
          ) : (
            <>
              <div className="chat-header">
                <div>
                  <h3>{selected.external_contact || 'Unknown contact'}</h3>
                  <div className="chat-subtitle">
                    Source: <span className="source-pill">{selected.source}</span>
                  </div>
                </div>
                <div className="chat-updated text-muted small">
                  Updated {formatTime(selected.updated_at)}
                </div>
              </div>

              <div
                ref={messagesRef}
                onScroll={handleMessagesScroll}
                className="messages-panel"
              >
                {loadingMessages && messages.length === 0 ? (
                  <div className="empty-state">Loading messages…</div>
                ) : messages.length === 0 ? (
                  <div className="empty-state">No messages yet</div>
                ) : (
                  messages.map((m) => {
                    const isIn = m.direction === 'IN'
                    const bubbleClass = [
                      'bubble',
                      isIn ? 'bubble-in' : 'bubble-out',
                      isIn && m.seen !== true ? 'bubble-unseen' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')
                    return (
                      <div key={m.id} className={`message-row ${isIn ? 'in' : 'out'}`}>
                        <div className={bubbleClass}>
                          <div className="bubble-meta">
                            <span className="sender">
                              {m.sender_name || (isIn ? selected.external_contact : 'Admin')}
                            </span>
                            <span className="dot">·</span>
                            <span className="time">{formatTime(m.created_at)}</span>
                          </div>
                          <div className="bubble-content">{m.content}</div>
                          {!isIn && (
                            <div className={`message-status status-${(m.status || '').toLowerCase()}`}>
                              {statusLabel(m.status)}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>

              {showJumpButton && (
                <div className="jump-wrap">
                  <button type="button" className="btn btn-secondary btn-sm jump-btn" onClick={jumpToLatest}>
                    Jump to latest ↓
                  </button>
                </div>
              )}

              <div className="composer">
                <textarea
                  className="form-control"
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Type your reply…"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault()
                      reply()
                    }
                  }}
                />
                <div className="composer-actions">
                  <span className="composer-hint text-muted small">Ctrl+Enter to send</span>
                  <div className="d-flex gap-2">
                    <button
                      type="button"
                      className="btn btn-outline-secondary btn-sm"
                      onClick={() => setText('')}
                      disabled={!text}
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={reply}
                      disabled={!text.trim() || sending}
                    >
                      {sending ? 'Sending…' : 'Send reply'}
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
      )}
    </div>
  )
}
