import React, {useEffect, useState, useRef} from 'react'
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles.css'

export default function App(){
  const [offcanvasOpen, setOffcanvasOpen] = useState(false)

  const [conversations, setConversations] = useState([])
  const [selected, setSelected] = useState(null)
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([])
  const [token, setToken] = useState(localStorage.getItem('api_token') || '')
  const [loadingConversations, setLoadingConversations] = useState(true)
  const [isScrolledUp, setIsScrolledUp] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')

  useEffect(()=>{
    // load conversations whenever token changes (or on mount if token exists)
    const load = async () =>{
      setLoadingConversations(true)
      if(!token){ setConversations([]); setLoadingConversations(false); return }
      const headers = {}
      if(token) headers['Authorization'] = `Token ${token}`
      try{
        const res = await fetch('/api/v1/conversations/', { headers })
        if(res.ok){ const data = await res.json(); setConversations(data) }
        else { setConversations([]) }
      }catch(e){ setConversations([]) }
      setLoadingConversations(false)
    }
    load()
  }, [token])

  useEffect(()=>{
    const loadDetail = async () => {
      if(!selected){ setMessages([]); return }
      const headers = {}
      if(token) headers['Authorization'] = `Token ${token}`
      try{
        const res = await fetch(`/api/v1/conversations/${selected.id}/`, { headers })
        if(res.ok){ const data = await res.json(); setMessages(data.messages || []) }
        else { setMessages([]) }
      }catch(e){ setMessages([]) }
    }
    loadDetail()
  }, [selected, token])

  // When messages change (loaded), mark unseen inbound messages as seen
  useEffect(()=>{
    if(!messages || messages.length===0) return
  const unseenInbound = messages.filter(m => m.direction === 'IN' && m.seen !== true)
    if(unseenInbound.length === 0) return

    const markAllSeen = async () => {
      const headers = {'Content-Type':'application/json'}
      if(token) headers['Authorization'] = `Token ${token}`
      try{
        // send requests in parallel
        await Promise.all(unseenInbound.map(m => fetch(`/api/v1/messages/${m.id}/seen/`, { method: 'POST', headers })))
        // optimistically update UI
  setMessages(msgs => msgs.map(msg => (msg.direction === 'IN' ? {...msg, seen: true} : msg)))
      }catch(e){
        // ignore errors for now
      }
    }

  // mark after a short delay so UI can render first; use 3s to ensure user had time to view
  const t = setTimeout(markAllSeen, 3000)
    return () => clearTimeout(t)
  }, [messages, token])

  const reply = async ()=>{
    if(!selected) return
    const headers = {'Content-Type':'application/json'}
    if(token) headers['Authorization'] = `Token ${token}`
    const res = await fetch(`/api/v1/conversations/${selected.id}/reply/`, {
      method:'POST',
      headers,
      body: JSON.stringify({text}),
      credentials: 'include'
    })
    if(res.ok){
      setText('')
      // refresh messages to include the new outbound message (may be pending)
      const d = await fetch(`/api/v1/conversations/${selected.id}/`).then(r=>r.json())
      setMessages(d.messages || [])
    } else {
      const err = await res.text()
      alert('Error sending: ' + err)
    }
  }

  const messagesRef = useRef(null)

  useEffect(()=>{
    // auto-scroll to bottom when messages change (only if the user hasn't scrolled up)
    if(!messagesRef.current) return
    const el = messagesRef.current
    if(!isScrolledUp){
      // smooth for user-friendly animation, instant if there are many messages
      try{
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
      }catch(e){
        el.scrollTop = el.scrollHeight
      }
    }
  }, [messages, isScrolledUp])

  const handleMessagesScroll = () => {
    if(!messagesRef.current) return
    const el = messagesRef.current
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 40
    setIsScrolledUp(!atBottom)
  }

  const login = async (e) => {
    e && e.preventDefault()
    setLoginError('')
    try{
      const res = await fetch('/api/v1/auth/token/', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({username, password})
      })
      if(!res.ok){ const t = await res.text(); setLoginError('Login failed'); return }
      const data = await res.json()
      if(data && data.token){ setToken(data.token); localStorage.setItem('api_token', data.token); setPassword('') }
    }catch(e){ setLoginError('Login failed') }
  }

  const logout = () => {
    setToken('')
    localStorage.removeItem('api_token')
    setConversations([])
    setSelected(null)
  }

  // If not logged in (no token), show a simple login page
  if(!token){
    return (
      <div className="container d-flex align-items-center justify-content-center vh-100">
        <div className="card p-4" style={{width: 420}}>
          <h4 className="mb-3">Admin login</h4>
          {loginError && <div className="alert alert-danger">{loginError}</div>}
          <form onSubmit={login}>
            <div className="mb-2">
              <input className="form-control" value={username} onChange={e=>setUsername(e.target.value)} placeholder="Username" />
            </div>
            <div className="mb-3">
              <input className="form-control" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password" />
            </div>
            <div className="d-flex gap-2">
              <button className="btn btn-primary" type="submit">Sign in</button>
              <button className="btn btn-outline-secondary" type="button" onClick={()=>{ setUsername(''); setPassword('') }}>Clear</button>
            </div>
          </form>
          <hr />
          <div className="small text-muted">Or paste an API token below (for local/dev):</div>
          <div className="input-group mt-2">
            <input className="form-control form-control-sm" value={token} onChange={e=>{setToken(e.target.value); localStorage.setItem('api_token', e.target.value)}} placeholder="Paste admin token here" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container-fluid vh-100 d-flex flex-column p-3">
      <div className="row g-3 flex-grow-1">
        <div className="col-12 d-flex d-md-none mb-2 offcanvas-toggle-parent">
          <button className="btn btn-outline-secondary offcanvas-toggle-btn" onClick={()=>setOffcanvasOpen(true)}>☰</button>
        </div>
        <div className={`col-12 col-md-4 col-lg-3 d-flex`}>
          {/* Offcanvas wrapper: on small screens this becomes a slide-in panel */}
          <div className={`app-offcanvas ${offcanvasOpen ? 'show' : ''}`}>
            <div className="card flex-grow-1 d-flex flex-column" style={{maxHeight: 'calc(100vh - 48px)'}}>
            <div className="card-body d-flex flex-column" style={{minHeight: 0}}>
              <h5 className="card-title">Conversations</h5>
              <div className="mb-2">
                <input className="form-control form-control-sm" value={token} onChange={e=>{setToken(e.target.value); localStorage.setItem('api_token', e.target.value)}} placeholder="Paste admin token here" />
              </div>
              <div className="list-group overflow-auto flex-grow-1" style={{minHeight: 0}}>
                {loadingConversations ? (
                  <div className="text-center text-muted small py-3">Loading...</div>
                ) : conversations.length===0 ? (
                  <div className="text-center text-muted small py-3">No conversations</div>
                ) : conversations.map(c=> (
                  <button key={c.id} className={`list-group-item list-group-item-action d-flex flex-column align-items-start ${selected && selected.id===c.id ? 'active' : ''} conversation-item ${c.has_unseen ? 'has-unseen' : ''}`} onClick={()=>{ setSelected(c); setOffcanvasOpen(false) }}>
                    <div className="fw-semibold">{c.external_contact || 'Unknown'}</div>
                    <div className="text-truncate small text-muted">{c.last_message}</div>
                    <div className="small text-muted mt-1">{new Date(c.updated_at).toLocaleString()}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
          </div>
          {/* backdrop for offcanvas on mobile */}
          <div className={`app-offcanvas-backdrop ${offcanvasOpen ? 'show' : ''}`} onClick={()=>setOffcanvasOpen(false)} />
        </div>
        <div className="col-12 col-md-8 col-lg-9 d-flex flex-column">
          <div className="card flex-grow-1 d-flex flex-column" style={{maxHeight: 'calc(100vh - 48px)'}}>
            <div className="card-body d-flex flex-column" style={{minHeight: 0}}>
              {selected ? (
                <>
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <div>
                      <h5 className="mb-0">{selected.external_contact}</h5>
                      <div className="text-muted small">Source: {selected.source}</div>
                    </div>
                    <div className="text-muted small">Updated: {new Date(selected.updated_at).toLocaleString()}</div>
                  </div>

                  <div ref={messagesRef} onScroll={handleMessagesScroll} className="messages overflow-auto mb-3 p-3 flex-grow-1" style={{minHeight: 0, position: 'relative'}}>
                    {messages.length===0 ? (
                      <div className="text-center text-muted">No messages yet</div>
                    ) : messages.map(m=> {
                      // Style unseen messages with a border or background
                      const bubbleClass = `bubble ${m.direction==='IN' ? 'bubble-in' : 'bubble-out'}${m.direction==='IN' && m.seen !== true ? ' bubble-unseen' : ''}`;
                      return (
                        <div key={m.id} className={`d-flex mb-2 ${m.direction==='IN' ? 'justify-content-start' : 'justify-content-end'}`}>
                          <div className={bubbleClass}>
                            <div className="small text-muted">
                              {m.sender_name || (m.direction==='OUT' ? 'Admin' : selected.external_contact)}  {new Date(m.created_at).toLocaleString()}
                            </div>
                            <div className="mt-1">{m.content}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Jump-to-bottom button shown when user scrolled up */}
                  {isScrolledUp && (
                    <div className="d-flex justify-content-end my-2">
                      <button className="btn btn-sm btn-secondary jump-to-bottom" onClick={() => { if(messagesRef.current){ messagesRef.current.scrollTo({ top: messagesRef.current.scrollHeight, behavior: 'smooth' }); setIsScrolledUp(false) } }}>
                        Jump to latest
                      </button>
                    </div>
                  )}

                  <div>
                    <textarea className="form-control mb-2" rows={4} value={text} onChange={e=>setText(e.target.value)} placeholder="Type your reply..." />
                    <div className="d-flex gap-2">
                      <button className="btn btn-primary" onClick={reply}>Send Reply</button>
                      <button className="btn btn-outline-secondary" onClick={()=>{setText('')}}>Clear</button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-muted my-auto">Select a conversation to view messages</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
