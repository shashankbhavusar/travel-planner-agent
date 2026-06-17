import React, { useState, useEffect, useRef } from 'react'

export default function App(){
  const [messages, setMessages] = useState([])
  const [userId, setUserId] = useState(()=>localStorage.getItem('user_id') || 'user1')
  const inputRef = useRef(null)

  useEffect(()=>{
    localStorage.setItem('user_id', userId)
  }, [userId])

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/history?user_id=${encodeURIComponent(userId)}`)
        if (!res.ok) throw new Error('Failed to load history')
        const data = await res.json()
        const normalized = (data.messages || []).map((m) => ({
          from: m.type === 'human' ? 'you' : 'agent',
          text: m.content,
          time: m.created_at || new Date().toISOString()
        }))
        setMessages(normalized)
        localStorage.setItem('messages', JSON.stringify(normalized))
      } catch (err) {
        const stored = localStorage.getItem('messages')
        if (stored) {
          setMessages(JSON.parse(stored))
        }
      }
    }

    fetchHistory()
  }, [userId])

  const send = async ()=>{
    const message = inputRef.current.value.trim()
    if(!message) return
    setMessages(prev => {
      const next = [...prev, {from:'you', text:message, time: new Date().toISOString()}]
      localStorage.setItem('messages', JSON.stringify(next))
      return next
    })
    inputRef.current.value = ''

    try{
      const res = await fetch('http://localhost:8000/api/message', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({user_id: userId, message})
      })
      const data = await res.json()
      const text = data.response || data?.response || JSON.stringify(data)
      setMessages(prev => {
        const next = [...prev, {from:'agent', text, time: new Date().toISOString()}]
        localStorage.setItem('messages', JSON.stringify(next))
        return next
      })
    }catch(e){
      setMessages(prev => {
        const next = [...prev, {from:'agent', text: 'Error contacting server', time: new Date().toISOString()}]
        localStorage.setItem('messages', JSON.stringify(next))
        return next
      })
    }
  }

  return (
    <div className="container">
      <h1>Travel Planner Agent</h1>

      <div className="controls">
        <label style={{marginRight:12}}>User ID:
          <input value={userId} onChange={e=>setUserId(e.target.value)} style={{marginLeft:8}} />
        </label>
      </div>

      <div className="messages">
        {messages.map((m,i)=> (
          <div key={i} className={"message "+(m.from==='you'? 'you':'agent')}>
            <div className="meta"><strong>{m.from}</strong> <span className="time">{new Date(m.time).toLocaleTimeString()}</span></div>
            <div className="text">{m.text}</div>
          </div>
        ))}
      </div>

      <div className="input">
        <textarea ref={inputRef} rows={3} placeholder="Type your message..." />
        <div style={{marginTop:8}}>
          <button onClick={send}>Send</button>
        </div>
      </div>
    </div>
  )
}
