import React, { useCallback, useEffect, useState } from 'react'
import { looksLikeHtml, openHtmlInNewTab, readableErrorPage } from './errorDisplay'

function authHeaders(token) {
  const headers = {}
  if (token) headers.Authorization = `Token ${token}`
  return headers
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

export default function ErrorsPage({ token, onCountChange }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState('')
  const [clearing, setClearing] = useState(false)
  const [pageError, setPageError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setPageError('')
    try {
      const res = await fetch('/api/v1/errors/', { headers: authHeaders(token) })
      if (!res.ok) {
        setPageError('Could not load errors.')
        setItems([])
        return
      }
      const data = await res.json()
      setItems(data.results || [])
      onCountChange?.(data.count || 0)
    } catch {
      setPageError('Network error while loading errors.')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [token, onCountChange])

  useEffect(() => {
    load()
  }, [load])

  const viewError = async (id) => {
    try {
      const res = await fetch(`/api/v1/errors/${id}/`, { headers: authHeaders(token) })
      if (!res.ok) {
        setPageError('Could not load error details.')
        return
      }
      const data = await res.json()
      const html = looksLikeHtml(data.content_type, data.detail)
        ? data.detail
        : readableErrorPage(data.status_code, data.detail, data.content_type)
      openHtmlInNewTab(html)
    } catch {
      setPageError('Network error while loading error details.')
    }
  }

  const deleteError = async (id) => {
    setDeletingId(id)
    setPageError('')
    try {
      const res = await fetch(`/api/v1/errors/${id}/`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (!res.ok && res.status !== 204) {
        setPageError('Could not delete error.')
        return
      }
      setItems((prev) => prev.filter((item) => item.id !== id))
      onCountChange?.((n) => Math.max(0, (typeof n === 'number' ? n : 0) - 1))
    } catch {
      setPageError('Network error while deleting error.')
    } finally {
      setDeletingId('')
    }
  }

  const clearAll = async () => {
    if (!items.length) return
    if (!window.confirm('Delete all logged errors?')) return
    setClearing(true)
    setPageError('')
    try {
      const res = await fetch('/api/v1/errors/', {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (!res.ok) {
        setPageError('Could not delete errors.')
        return
      }
      setItems([])
      onCountChange?.(0)
    } catch {
      setPageError('Network error while deleting errors.')
    } finally {
      setClearing(false)
    }
  }

  return (
    <main className="errors-page">
      <div className="errors-toolbar">
        <div>
          <h2>Errors</h2>
          <p className="text-muted small mb-0">Server 500 responses are stored here so you can read and remove them.</p>
        </div>
        <div className="d-flex gap-2">
          <button type="button" className="btn btn-outline-secondary btn-sm" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button
            type="button"
            className="btn btn-outline-danger btn-sm"
            onClick={clearAll}
            disabled={clearing || !items.length}
          >
            {clearing ? 'Deleting…' : 'Delete all'}
          </button>
        </div>
      </div>

      {pageError && <div className="app-alert mb-3"><span>{pageError}</span></div>}

      <div className="errors-list">
        {loading ? (
          <div className="empty-state">Loading errors…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">No logged errors</div>
        ) : (
          items.map((item) => (
            <div key={item.id} className="error-item">
              <div className="error-item-main">
                <div className="error-item-top">
                  <span className="error-status">{item.status_code}</span>
                  <span className="error-method">{item.method}</span>
                  <span className="error-path">{item.path}</span>
                  <span className="error-time">{formatTime(item.created_at)}</span>
                </div>
                <div className="error-message">{item.message || 'No message'}</div>
              </div>
              <div className="error-item-actions">
                <button type="button" className="btn btn-outline-light btn-sm" onClick={() => viewError(item.id)}>
                  View
                </button>
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => deleteError(item.id)}
                  disabled={deletingId === item.id}
                >
                  {deletingId === item.id ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </main>
  )
}
