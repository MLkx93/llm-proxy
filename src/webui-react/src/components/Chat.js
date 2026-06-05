import React, { useState, useRef, useEffect, useCallback } from 'react';
import { streamChatCompletion, sendChatCompletion,
         listConversations, createConversation, getConversation,
         addMessage, deleteConversation } from '../services/api';
import ProviderSelector from './ProviderSelector';
import BlockCard from './BlockCard';
import './Chat.css';

/**
 * Chat with the security proxy.
 *
 * CONTINUITY GUARANTEE (core requirement):
 *   We keep TWO representations of the conversation:
 *     - `transcript` : everything shown on screen, INCLUDING ephemeral block
 *                      notices and redaction notices.
 *     - the LLM-sent history (derived via `cleanHistory()`): only real user +
 *                      real assistant turns. Block/notice entries are NEVER sent.
 *   So when a turn is blocked, the conversation is NOT broken or polluted — the
 *   next message continues from the last clean exchange, and the LLM never sees
 *   a fake "blocked" turn.
 */

// Roles that are display-only and must never be sent back to the LLM.
const DISPLAY_ONLY = new Set(['block', 'notice']);

function cleanHistory(transcript) {
  return transcript
    .filter((m) => !DISPLAY_ONLY.has(m.role) && !m.error && !m.blocked)
    .map((m) => ({ role: m.role, content: m.content }));
}

export default function Chat() {
  const [selectedModel, setSelectedModel] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const chatEndRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 60);
  }, []);

  useEffect(() => { scrollToBottom(); }, [transcript, scrollToBottom]);

  // ── History sidebar ────────────────────────────────────────────────────────
  const refreshConversations = useCallback(async () => {
    try {
      const res = await listConversations();
      setConversations(res.data.conversations || []);
    } catch { /* DB may be down — sidebar just stays empty */ }
  }, []);

  useEffect(() => { refreshConversations(); }, [refreshConversations]);

  const ensureConversation = async () => {
    if (activeConvId) return activeConvId;
    try {
      const res = await createConversation('New chat');
      setActiveConvId(res.data.id);
      refreshConversations();
      return res.data.id;
    } catch {
      return null; // DB down — chat still works, just no persistence
    }
  };

  const persist = async (convId, msg) => {
    if (!convId) return;
    try { await addMessage(convId, msg); } catch { /* best-effort */ }
  };

  const loadConversation = async (id) => {
    try {
      const res = await getConversation(id);
      setActiveConvId(id);
      setTranscript((res.data.messages || []).map((m) => ({
        role: m.blocked ? 'block' : m.role,
        content: m.content,
        block: m.blocked ? { block_code: m.block_code, message: m.content } : undefined,
      })));
    } catch { /* ignore */ }
  };

  const newChat = () => {
    setActiveConvId(null);
    setTranscript([]);
  };

  const removeConversation = async (id, e) => {
    e.stopPropagation();
    try { await deleteConversation(id); } catch { /* ignore */ }
    if (id === activeConvId) newChat();
    refreshConversations();
  };

  // ── Sending ──────────────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || !selectedModel || loading) return;

    const userMsg = { role: 'user', content: input.trim() };
    const convId = await ensureConversation();

    // Build the outgoing array from CLEAN history + this user turn only.
    const outgoing = [...cleanHistory(transcript), userMsg];

    setTranscript((t) => [...t, userMsg]);
    setInput('');
    setLoading(true);
    persist(convId, { role: 'user', content: userMsg.content });

    if (streaming) {
      await sendStreaming(outgoing, convId);
    } else {
      await sendBuffered(outgoing, convId);
    }
    setLoading(false);
    refreshConversations();
  };

  // Buffered request
  const sendBuffered = async (outgoing, convId) => {
    try {
      const res = await sendChatCompletion(outgoing, selectedModel.id);
      if (res.data.blocked) {
        addBlock(res.data, convId);
        return;
      }
      const content = res.data.choices?.[0]?.message?.content || '(empty response)';
      setTranscript((t) => [...t, { role: 'assistant', content }]);
      persist(convId, { role: 'assistant', content });
    } catch (err) {
      addBlock({ block_code: 'ERROR', message: err.response?.data?.detail || err.message }, convId);
    }
  };

  // Streaming request (SSE)
  const sendStreaming = async (outgoing, convId) => {
    let acc = '';
    let blocked = null;
    // Insert a live assistant bubble we append tokens to.
    setTranscript((t) => [...t, { role: 'assistant', content: '', streaming: true }]);

    const setLiveContent = (text) => {
      setTranscript((t) => {
        const copy = [...t];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].streaming) { copy[i] = { ...copy[i], content: text }; break; }
        }
        return copy;
      });
    };

    try {
      const resp = await streamChatCompletion(outgoing, selectedModel.id);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;
          let payload;
          try { payload = JSON.parse(data); } catch { continue; }

          if (payload.error) {
            blocked = { block_code: payload.error, message: payload.message, safe_version: payload.safe_version };
            continue;
          }
          const delta = payload.choices?.[0]?.delta?.content;
          if (delta) { acc += delta; setLiveContent(acc); }
        }
      }
    } catch (err) {
      blocked = { block_code: 'STREAM_ERROR', message: err.message };
    }

    // Finalize: remove the live bubble, then add either a clean assistant turn
    // or a block notice. A block NEVER enters clean history.
    setTranscript((t) => t.filter((m) => !m.streaming));

    if (blocked) {
      addBlock(blocked, convId, acc);  // acc = partial intercepted text (display only)
    } else {
      setTranscript((t) => [...t, { role: 'assistant', content: acc || '(empty response)' }]);
      persist(convId, { role: 'assistant', content: acc });
    }
  };

  // Add a block card to the transcript (display-only; excluded from clean history).
  // Also retroactively marks the preceding user message as blocked so cleanHistory
  // excludes it — the LLM must never see a message whose turn was blocked.
  const addBlock = (block, convId, partial) => {
    setTranscript((t) => {
      const updated = [...t];
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'user' && !updated[i].blocked) {
          updated[i] = { ...updated[i], blocked: true };
          break;
        }
      }
      return [...updated, { role: 'block', content: block.message, block, partial }];
    });
    persist(convId, {
      role: 'assistant', content: block.message,
      blocked: true, block_code: block.block_code,
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="chat-layout">
      {/* History sidebar */}
      <aside className="chat-history">
        <button className="new-chat-btn" onClick={newChat}>+ New chat</button>
        <div className="conv-list">
          {conversations.map((c) => (
            <div key={c.id}
              className={`conv-item ${c.id === activeConvId ? 'active' : ''}`}
              onClick={() => loadConversation(c.id)}>
              <span className="conv-title">{c.title}</span>
              <button className="conv-del" onClick={(e) => removeConversation(c.id, e)}>×</button>
            </div>
          ))}
          {conversations.length === 0 && <div className="conv-empty">No conversations yet</div>}
        </div>
      </aside>

      {/* Main chat */}
      <div className="chat-main">
        <ProviderSelector onModelSelect={setSelectedModel} />

        <div className="chat-container">
          <div className="chat-toolbar">
            <span className="demo-client-tag">Demo Client</span>
            {selectedModel && <span className="selected-model-badge">{selectedModel.name}</span>}
            <label className="stream-toggle">
              <input type="checkbox" checked={streaming} onChange={(e) => setStreaming(e.target.checked)} />
              Live streaming
            </label>
          </div>

          <div className="chat-messages">
            {transcript.length === 0 && (
              <div className="chat-empty">
                <div className="empty-icon">🛡️</div>
                <p>Start chatting — every message is scanned by the security proxy.</p>
                <p className="empty-hint">Secrets, PII, vulnerable packages and malicious code are intercepted in real time.</p>
              </div>
            )}

            {transcript.map((msg, i) => {
              if (msg.role === 'block') {
                return <BlockCard key={i} block={msg.block} partial={msg.partial} />;
              }
              return (
                <div key={i} className={`chat-message ${msg.role}`}>
                  <div className="message-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>
                  <div className="message-content">
                    <div className="message-text">
                      {msg.content}{msg.streaming && <span className="cursor">▋</span>}
                    </div>
                  </div>
                </div>
              );
            })}

            {loading && !streaming && (
              <div className="chat-message assistant">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  <div className="typing-indicator"><span></span><span></span><span></span></div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="chat-input-area">
            <textarea
              value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
              placeholder={selectedModel ? `Message ${selectedModel.name}…` : 'Select a model first…'}
              disabled={!selectedModel || loading} className="chat-input" rows={3}
            />
            <div className="input-actions">
              <button onClick={newChat} className="btn btn-secondary" disabled={transcript.length === 0}>
                🗑️ Clear
              </button>
              <button onClick={handleSend} disabled={!input.trim() || !selectedModel || loading} className="btn btn-primary">
                {loading ? '⏳ Sending…' : '🚀 Send'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
