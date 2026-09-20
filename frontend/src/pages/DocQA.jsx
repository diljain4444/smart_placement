import React, { useState, useRef, useEffect } from 'react';
import { ragUpload, ragAsk, ragReset } from '../api';

export default function DocQA() {
  const [phase, setPhase] = useState(1);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Phase 2 state
  const [sessionId, setSessionId] = useState(null);
  const [fileInfo, setFileInfo] = useState({ filename: '', chunkCount: 0 });
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isAsking, setIsAsking] = useState(false);

  const fileInputRef = useRef(null);
  const chatRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, isAsking]);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await ragUpload(formData);
      
      setSessionId(response.data.session_id);
      setFileInfo({
        filename: response.data.filename || file.name,
        chunkCount: response.data.chunk_count || 0
      });
      setPhase(2);
      setMessages([]);
    } catch (err) {
      console.error(err);
      setError('Failed to upload and process document. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isAsking) return;

    const question = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setIsAsking(true);
    setError(null);

    try {
      const response = await ragAsk({ session_id: sessionId, question });
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error while answering your question.' }]);
    } finally {
      setIsAsking(false);
    }
  };

  const handleReset = async () => {
    try {
      if (sessionId) {
        await ragReset({ session_id: sessionId });
      }
    } catch (err) {
      console.error('Error resetting session:', err);
    } finally {
      setPhase(1);
      setFile(null);
      setSessionId(null);
      setFileInfo({ filename: '', chunkCount: 0 });
      setMessages([]);
      setError(null);
    }
  };

  return (
    <div className="docqa-page">
      {phase === 1 && (
        <div className="docqa-upload-phase">
          <h1>📚 Document Q&A</h1>
          <p className="docqa-subtitle">
            Upload a document and ask questions — answers are generated from your document's content using RAG.
          </p>

          <div 
            className="docqa-upload-zone"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }}
              onChange={handleFileSelect}
              accept=".pdf,.docx,.csv,.txt,.png,.jpg,.jpeg"
            />
            {file ? (
              <div className="docqa-file-selected">
                <p>Selected file: <strong>{file.name}</strong></p>
                <p>Click or drag to change</p>
              </div>
            ) : (
              <div className="docqa-file-prompt">
                <p>Drag and drop your file here, or click to browse</p>
                <p className="docqa-file-types">Supports: PDF, DOCX, CSV, TXT, PNG, JPG</p>
              </div>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="docqa-actions">
            <button 
              className="submit-btn" 
              onClick={handleUpload}
              disabled={!file || loading}
            >
              Upload & Process
            </button>
          </div>

          {loading && (
            <div className="loading-overlay">
              <div className="loading-spinner" />
              <p className="loading-message">Processing document...</p>
            </div>
          )}
        </div>
      )}

      {phase === 2 && (
        <div className="docqa-chat-phase">
          <div className="docqa-header">
            <div className="docqa-file-info">
              📄 {fileInfo.filename} <span className="chunk-badge">({fileInfo.chunkCount} chunks)</span>
            </div>
            <button className="end-btn" onClick={handleReset}>
              New Document
            </button>
          </div>

          <div className="docqa-chat" ref={chatRef}>
            {messages.length === 0 ? (
              <div className="docqa-empty-state">
                Ask a question about your document...
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`docqa-msg docqa-msg-${msg.role === 'user' ? 'user' : 'ai'}`}>
                  {msg.role === 'user' ? msg.content : (
                    <div className="docqa-answer-content" dangerouslySetInnerHTML={{
                      __html: msg.content
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/\n/g, '<br/>')
                    }} />
                  )}
                </div>
              ))
            )}
            {isAsking && (
              <div className="docqa-thinking">
                <div className="docqa-thinking-dots">
                  <span></span><span></span><span></span>
                </div>
                Analyzing document...
              </div>
            )}
          </div>

          <form className="docqa-input-row" onSubmit={handleAsk}>
            <input 
              type="text" 
              className="form-input" 
              placeholder="Ask a question..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isAsking}
            />
            <button type="submit" className="submit-btn" disabled={!inputValue.trim() || isAsking}>
              Ask
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
