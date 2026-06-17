import React, { useState, useEffect, useRef } from 'react'

export default function App(){
  const [messages, setMessages] = useState(()=>{
    const s = localStorage.getItem('messages')
    return s ? JSON.parse(s) : []
  })
  const [userId, setUserId] = useState(()=>localStorage.getItem('user_id') || 'user1')
  const inputRef = useRef(null)

  useEffect(()=>{
    localStorage.setItem('messages', JSON.stringify(messages))
  }, [messages])

  useEffect(()=>{
    localStorage.setItem('user_id', userId)
  }, [userId])

  const send = async ()=>{
    const message = inputRef.current.value.trim()
    if(!message) return
    setMessages(m=>[...m, {from:'you', text:message, time: new Date().toISOString()}])
    inputRef.current.value = ''

    try{
      const res = await fetch('http://localhost:8000/api/message', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({user_id: userId, message})
      })
      const data = await res.json()
      const text = data.response || data?.response || JSON.stringify(data)
      setMessages(m=>[...m, {from:'agent', text, time: new Date().toISOString()}])
    }catch(e){
      setMessages(m=>[...m, {from:'agent', text: 'Error contacting server', time: new Date().toISOString()}])
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
