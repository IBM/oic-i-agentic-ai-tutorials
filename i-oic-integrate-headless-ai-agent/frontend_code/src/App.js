// App.js
import React, { useState, useEffect } from 'react';
import { Button, TextInput } from '@carbon/react';
import * as Icons from '@carbon/icons-react';
import ReactMarkdown from 'react-markdown';
import './App.css';

// === Backend endpoint (non-streaming) ===
const API_URL = 'http://127.0.0.1:8000/chat/v2';

// Your deployed agent ID
const DEFAULT_AGENT_ID = '87e081f7-4fdb-42e4-9ddd-16bb3ce4d8fc';

// Leave blank to let backend create the first thread
const DEFAULT_THREAD_ID = '';

function QnAChat() {
  const [agentId, setAgentId] = useState(DEFAULT_AGENT_ID);
  const [threadId, setThreadId] = useState(DEFAULT_THREAD_ID);
  const [showConfig, setShowConfig] = useState(false);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  // Send handler (accepts optional preset text)
  const handleSendQuestion = async (text) => {
    if (loading) return;
    const finalQuestion = (text ?? question).trim();
    if (!finalQuestion || !agentId.trim()) return;

    setLoading(true);
    setMessages((prev) => [...prev, { type: 'user', text: finalQuestion }]);
    setQuestion('');

    const params = new URLSearchParams({
      query: finalQuestion,
      agent_id: agentId,
      ...(threadId.trim() ? { thread_id: threadId } : {}),
    }).toString();

    try {
      const res = await fetch(`${API_URL}?${params}`, { method: 'GET' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.thread_id && data.thread_id !== threadId) {
        setThreadId(data.thread_id);
      }

      const answer =
        typeof data.response === 'string' && data.response.trim()
          ? data.response
          : '(empty reply)';
      setMessages((prev) => [...prev, { type: 'assistant', text: answer }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { type: 'assistant', text: 'Sorry, something went wrong.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Press Enter to send
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendQuestion();
      }
    };
    const input = document.getElementById('chat-input');
    input?.addEventListener('keydown', onKey);
    return () => input?.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, agentId, threadId, loading]);

  return (
    <div className="qna-chat-container">
      <div className="chat-header">
        <div className="config-toggle" onClick={() => setShowConfig(!showConfig)}>
          <Icons.Settings /> <span>Settings</span>
        </div>

        {showConfig && (
          <div className="id-inputs">
            <TextInput
              id="agent-id-input"
              labelText="Agent ID (required)"
              placeholder="Enter Agent ID…"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            />
            <TextInput
              id="thread-id-input"
              labelText="Thread ID (optional)"
              placeholder="Enter Thread ID…"
              value={threadId}
              onChange={(e) => setThreadId(e.target.value)}
            />
          </div>
        )}

        <div className="get-started">Get started by asking a question</div>
        <div className="see-examples">See some examples:</div>
      </div>

      {/* Example prompts */}
      <div className="example-questions-container column">
        <div
          className="example-question"
          onClick={() =>
            handleSendQuestion('Show me examples of the invoice date analysis you can do')
          }
        >
          <div className="example-question-text">
            Show me examples of the invoice date analysis you can do
          </div>
          <Icons.ChevronRight className="example-question-arrow" />
        </div>
        <div
          className="example-question"
          onClick={() => handleSendQuestion('Analyze the earliest invoice')}
        >
          <div className="example-question-text">Analyze the earliest invoice</div>
          <Icons.ChevronRight className="example-question-arrow" />
        </div>
      </div>

      {/* Chat messages */}
      <div className="chat-box">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`message ${m.type === 'user' ? 'user-message' : 'assistant-message'}`}
          >
            <div className="message-text">
              {m.type === 'assistant' ? <ReactMarkdown>{m.text}</ReactMarkdown> : m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant-message loading-message">
            <div className="loading-spinner" />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="chat-input-container">
        <TextInput
          id="chat-input"
          labelText=""
          placeholder="Enter your question and press Enter or click Send…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
        />
        <Button
          kind="primary"
          onClick={() => handleSendQuestion()}
          disabled={loading || !question.trim() || !agentId.trim()}
        >
          {loading ? 'Sending…' : 'Send'}
        </Button>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="App">
      <QnAChat />
    </div>
  );
}
