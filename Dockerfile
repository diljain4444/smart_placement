# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies first (cached layer) ─────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy project files ────────────────────────────────────────────────────────
COPY . .

# ── Hugging Face Spaces requires port 7860 ───────────────────────────────────
EXPOSE 7860

# ── Start FastAPI server ──────────────────────────────────────────────────────
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
