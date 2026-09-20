import axios from 'axios';

const api = axios.create({
  baseURL: '',
});

// Health
export const healthCheck = () => api.get('/api/health');

// Interview
export const processResume = (formData) => api.post('/api/interview/process-resume', formData);
export const startInterview = (data) => api.post('/api/interview/start', data);
export const submitAnswer = (data) => api.post('/api/interview/answer', data);
export const submitVoiceAnswer = (formData) => api.post('/api/interview/voice-answer', formData);
export const endInterview = (data) => api.post('/api/interview/end', data);
export const resetInterview = (data) => api.post('/api/interview/reset', data);

// Resume
export const buildResume = (formData) => api.post('/api/resume/build', formData, { responseType: 'blob' });
export const modifyResume = (formData) => api.post('/api/resume/modify', formData, { responseType: 'blob' });
export const rateResume = (formData) => api.post('/api/resume/rate', formData);
export const extractText = (formData) => api.post('/api/resume/extract-text', formData);

// RAG Document Q&A
export const ragUpload = (formData) => api.post('/api/rag/upload', formData);
export const ragAsk = (data) => api.post('/api/rag/ask', data);
export const ragReset = (data) => api.post('/api/rag/reset', data);

// Roadmap
export const generateRoadmapApi = (data) => api.post('/api/roadmap/generate', data);
