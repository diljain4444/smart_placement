"""
Hugging Face Spaces entry point.
Mounts a minimal Gradio status page into the existing FastAPI app,
so HF Spaces can serve everything on port 7860.
All /api/* routes from api.py work as normal.
"""
import uvicorn
import gradio as gr
from api import app  # your existing FastAPI app

# ── Minimal Gradio status page ────────────────────────────────────────────────
with gr.Blocks(title="Smart Placement API") as demo:
    gr.Markdown("""
    # 🚀 Smart Placement — Backend API
    
    The backend is **running** and ready to accept requests.
    
    Open your frontend app to use Smart Placement.
    
    ### Available Endpoints
    | Endpoint | Description |
    |---|---|
    | `/api/health` | Health check |
    | `/api/interview/*` | Mock Interview |
    | `/api/resume/*` | Resume Suite |
    | `/api/doc-qa/*` | Document Q&A |
    | `/api/roadmap/*` | Learning Roadmap |
    | `/api/news` | Latest News |
    """)

# ── Mount Gradio UI into your FastAPI app at /ui ─────────────────────────────
app = gr.mount_gradio_app(app, demo, path="/ui")

# ── Start server on HF Spaces required port 7860 ─────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
