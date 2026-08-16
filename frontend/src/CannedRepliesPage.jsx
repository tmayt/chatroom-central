import React, { useCallback, useEffect, useState } from 'react'

function authHeaders(token, extra = {}) {
  const headers = { ...extra }
  if (token) headers.Authorization = `Token ${token}`
  return headers
}

const emptyForm = { title: '', body: '', sort_order: 0 }

export default function CannedRepliesPage({ token, onChanged }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const [editingId, setEditingId] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [pageError, setPageError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setPageError('')
    try {
      const res = await fetch('/api/v1/canned-replies/', { headers: authHeaders(token) })
      if (!res.ok) {
        setPageError('Could not load quick replies.')
        setItems([])
        return
      }
      const data = await res.json()
      setItems(Array.isArray(data) ? data : data.results || [])
    } catch {
      setPageError('Network error while loading quick replies.')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  const resetForm = () => {
    setEditingId('')
    setForm(emptyForm)
  }

  const startEdit = (item) => {
    setEditingId(item.id)
    setForm({
      title: item.title || '',
      body: item.body || '',
      sort_order: item.sort_order || 0,
    })
  }

  const save = async (e) => {
    e?.preventDefault()
    if (!form.title.trim() || !form.body.trim() || saving) return
    setSaving(true)
    setPageError('')
    const payload = {
      title: form.title.trim(),
      body: form.body.trim(),
      sort_order: Number(form.sort_order) || 0,
    }
    try {
      const url = editingId ? `/api/v1/canned-replies/${editingId}/` : '/api/v1/canned-replies/'
      const res = await fetch(url, {
        method: editingId ? 'PATCH' : 'POST',
        headers: authHeaders(token, { 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        setPageError('Could not save quick reply.')
        return
      }
      resetForm()
      await load()
      onChanged?.()
    } catch {
      setPageError('Network error while saving quick reply.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Delete this quick reply?')) return
    setDeletingId(id)
    setPageError('')
    try {
      const res = await fetch(`/api/v1/canned-replies/${id}/`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (!res.ok && res.status !== 204) {
        setPageError('Could not delete quick reply.')
        return
      }
      if (editingId === id) resetForm()
      setItems((prev) => prev.filter((item) => item.id !== id))
      onChanged?.()
    } catch {
      setPageError('Network error while deleting quick reply.')
    } finally {
      setDeletingId('')
    }
  }

  return (
    <main className="manage-page">
      <div className="errors-toolbar">
        <div>
          <h2>Quick replies</h2>
          <p className="text-muted small mb-0">Saved messages you can insert into the composer.</p>
        </div>
      </div>

      {pageError && (
        <div className="app-alert mb-3">
          <span>{pageError}</span>
        </div>
      )}

      <form className="canned-form" onSubmit={save}>
        <div className="canned-form-grid">
          <div>
            <label className="form-label">Title</label>
            <input
              className="form-control"
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Greeting"
              required
            />
          </div>
          <div>
            <label className="form-label">Order</label>
            <input
              className="form-control"
              type="number"
              min="0"
              value={form.sort_order}
              onChange={(e) => setForm((prev) => ({ ...prev, sort_order: e.target.value }))}
            />
          </div>
        </div>
        <label className="form-label">Message</label>
        <textarea
          className="form-control"
          rows={4}
          value={form.body}
          onChange={(e) => setForm((prev) => ({ ...prev, body: e.target.value }))}
          placeholder="Hello, how can I help you?"
          required
        />
        <div className="canned-form-actions">
          {editingId && (
            <button type="button" className="btn btn-outline-secondary btn-sm" onClick={resetForm}>
              Cancel
            </button>
          )}
          <button type="submit" className="btn btn-primary btn-sm" disabled={saving || !form.title.trim() || !form.body.trim()}>
            {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add quick reply'}
          </button>
        </div>
      </form>

      <div className="errors-list">
        {loading ? (
          <div className="empty-state">Loading quick replies…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">No quick replies yet</div>
        ) : (
          items.map((item) => (
            <div key={item.id} className={`error-item ${editingId === item.id ? 'active' : ''}`}>
              <div className="error-item-main">
                <div className="error-item-top">
                  <span className="canned-title">{item.title}</span>
                </div>
                <div className="error-message">{item.body}</div>
              </div>
              <div className="error-item-actions">
                <button type="button" className="btn btn-outline-light btn-sm" onClick={() => startEdit(item)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => remove(item.id)}
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
