"""
avatar_component.py
AI Interviewer Avatar — state-machine video panel

Videos are embedded as base64 data URIs so they work on any deployment
(Streamlit Cloud, Render, etc.) without a local file server.

State machine:
  "new_final_question"  →  new_final_question.mp4 loops + AI audio plays
  "new_waiting"   →  new_waiting.mp4  loops (JS transitions here after audio ends)
  "new_hearing"   →  new_hearing.mp4  loops (JS transitions here when mic is active)
"""

from __future__ import annotations

import base64
import os

import streamlit.components.v1 as components

# ── Module-level constants ─────────────────────────────────────────────────────
_DIR: str = os.path.dirname(os.path.abspath(__file__))

# ── Video base64 cache (loaded once per process) ──────────────────────────────
_video_cache: dict[str, str] = {}


def _video_data_uri(filename: str) -> str:
    """Return a base64 data URI for the given MP4 file (cached)."""
    if filename not in _video_cache:
        path = os.path.join(_DIR, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                _video_cache[filename] = (
                    "data:video/mp4;base64," + base64.b64encode(f.read()).decode("utf-8")
                )
        else:
            _video_cache[filename] = ""  # missing file → blank src
    return _video_cache[filename]


# ── Public render function ────────────────────────────────────────────────────

def render_avatar_panel(
    state: str = "new_waiting",    # "new_final_question" | "new_waiting" | "new_hearing"
    feedback_b64: str = "",    # base64 MP3 — played first (feedback audio)
    question_b64: str = "",    # base64 MP3 — played second (question audio)
    height: int = 520,
) -> None:
    """
    Render the AI interviewer video panel as a self-contained HTML component.

    State colours
    ─────────────
    new_final_question → green  border / glow  (interviewer speaking)
    new_waiting  → gray   border / glow  (waiting for candidate)
    new_hearing  → blue   border / glow  (interviewer listening)
    """
    q_url = _video_data_uri("new_final_question.mp4")
    w_url = _video_data_uri("new_waiting.mp4")
    h_url = _video_data_uri("new_hearing.mp4")

    _C = {
        "new_final_question": ("#22C55E", "rgba(34,197,94,0.35)",   "Asking Question"),
        "new_waiting":  ("#4A5568", "rgba(74,99,128,0.20)",   "Waiting for Response"),
        "new_hearing":  ("#3B6BE8", "rgba(59,107,232,0.35)",  "Listening\u2026"),
    }
    border, glow, label = _C.get(state, _C["new_waiting"])

    # Escape braces in f-string: CSS uses {{ / }}
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:100%;height:100%;overflow:hidden;background:#060810;
  font-family:'DM Sans','Segoe UI',sans-serif;}}

/* ── Panel wrapper ─────────────────────────────────────────────────────────── */
.panel{{
  width:100%;height:100vh;
  background:linear-gradient(160deg,#060D1F 0%,#0A1A3A 50%,#0D2060 100%);
  border-radius:18px;
  border:2.5px solid {border};
  box-shadow:0 0 36px {glow},0 8px 44px rgba(0,0,0,0.65);
  overflow:hidden;display:flex;flex-direction:column;
  transition:border-color .45s ease,box-shadow .45s ease;
  position:relative;
}}

/* ── Video container ──────────────────────────────────────────────────────── */
.vc{{position:relative;flex:1;background:#000;overflow:hidden;}}

.vid{{
  position:absolute;top:0;left:0;width:100%;height:100%;
  object-fit:cover;
  transition:opacity .35s ease;
}}
.vid.hidden {{opacity:0;pointer-events:none;}}
.vid.visible{{opacity:1;}}

/* ── LIVE badge ───────────────────────────────────────────────────────────── */
.live{{
  position:absolute;top:11px;left:11px;z-index:10;
  background:rgba(220,38,38,.88);color:#fff;
  font-size:9px;font-weight:800;letter-spacing:.12em;
  padding:3px 10px;border-radius:5px;
  display:flex;align-items:center;gap:5px;
  backdrop-filter:blur(3px);
}}
.live-dot{{width:6px;height:6px;background:#fff;border-radius:50%;
  animation:blink 1.2s infinite;}}

/* ── Interviewer name tag ─────────────────────────────────────────────────── */
.name-tag{{
  position:absolute;bottom:56px;left:11px;z-index:10;
  background:rgba(6,8,16,.78);backdrop-filter:blur(6px);
  border:1px solid rgba(255,255,255,.08);border-radius:8px;
  padding:5px 12px;
}}
.nt-name{{color:#D0E0FF;font-weight:700;font-size:12px;}}
.nt-title{{color:#4A6380;font-size:10px;font-weight:500;margin-top:1px;}}

/* ── Speaking wave bars (green) ──────────────────────────────────────────── */
.speak-bars{{
  position:absolute;bottom:14px;left:50%;transform:translateX(-50%);
  display:flex;gap:3px;align-items:flex-end;height:26px;
  opacity:0;transition:opacity .3s;z-index:10;
}}
.speak-bars.show{{opacity:1;}}
.sbar{{width:4px;background:#22C55E;border-radius:2px;
  animation:speak .7s ease-in-out infinite;}}
.sbar:nth-child(1){{animation-delay:0s;   height:10px;}}
.sbar:nth-child(2){{animation-delay:.08s; height:18px;}}
.sbar:nth-child(3){{animation-delay:.16s; height:24px;}}
.sbar:nth-child(4){{animation-delay:.08s; height:18px;}}
.sbar:nth-child(5){{animation-delay:0s;   height:10px;}}
@keyframes speak{{0%,100%{{transform:scaleY(.3)}}50%{{transform:scaleY(1)}}}}

/* ── Listening wave bars (blue) ──────────────────────────────────────────── */
.wave-bars{{
  position:absolute;bottom:14px;left:50%;transform:translateX(-50%);
  display:flex;gap:4px;align-items:flex-end;height:26px;
  opacity:0;transition:opacity .3s;z-index:10;
}}
.wave-bars.show{{opacity:1;}}
.bar{{width:4px;background:#3B6BE8;border-radius:2px;
  animation:wave .9s ease-in-out infinite;}}
.bar:nth-child(1){{animation-delay:0s;  height:8px;}}
.bar:nth-child(2){{animation-delay:.1s; height:16px;}}
.bar:nth-child(3){{animation-delay:.2s; height:24px;}}
.bar:nth-child(4){{animation-delay:.1s; height:16px;}}
.bar:nth-child(5){{animation-delay:0s;  height:8px;}}
@keyframes wave{{0%,100%{{transform:scaleY(.35)}}50%{{transform:scaleY(1)}}}}

/* ── Mic icon overlay ─────────────────────────────────────────────────────── */
.mic-overlay{{
  position:absolute;bottom:14px;right:14px;z-index:10;
  background:rgba(59,107,232,.82);border-radius:50%;
  width:36px;height:36px;display:flex;align-items:center;justify-content:center;
  font-size:15px;opacity:0;transition:opacity .3s;backdrop-filter:blur(4px);
}}
.mic-overlay.show{{opacity:1;}}

/* ── Status bar ───────────────────────────────────────────────────────────── */
.status-bar{{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 15px;
  background:rgba(6,8,16,.90);
  border-top:1px solid rgba(255,255,255,.06);
  flex-shrink:0;
}}
.sl{{display:flex;align-items:center;gap:9px;}}
.av{{
  width:34px;height:34px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#1E3A8A,#3B6BE8);
  display:flex;align-items:center;justify-content:center;font-size:16px;
}}
.av-name{{color:#D0E0FF;font-weight:700;font-size:12.5px;}}
.av-title{{color:#3A536A;font-size:10px;font-weight:500;margin-top:1px;}}
.badge{{
  display:flex;align-items:center;gap:6px;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);
  border-radius:20px;padding:5px 13px;
  font-size:11px;font-weight:600;
  color:{border};
  transition:color .45s,border-color .45s;
}}
.bdot{{
  width:7px;height:7px;border-radius:50%;
  background:{border};
  transition:background .45s;
}}
.pulse{{animation:pulse-a 1.8s ease-in-out infinite;}}
@keyframes pulse-a{{0%,100%{{transform:scale(1);opacity:1}}50%{{transform:scale(1.45);opacity:.4}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.12}}}}
</style></head><body>

<!-- Hidden audio element for AI TTS playback -->
<audio id="aud" preload="auto" style="display:none;"></audio>

<div class="panel" id="panel">
  <div class="vc">
    <div class="live"><div class="live-dot"></div>LIVE</div>

    <!-- Three video layers (all preloaded, only one visible at a time) -->
    <video class="vid hidden" id="vq" src="{q_url}"
           autoplay loop muted playsinline preload="auto"></video>
    <video class="vid hidden" id="vw" src="{w_url}"
           autoplay loop muted playsinline preload="auto"></video>
    <video class="vid hidden" id="vh" src="{h_url}"
           autoplay loop muted playsinline preload="auto"></video>

    <!-- Name tag overlay -->
    <div class="name-tag">
      <div class="nt-name">Sarah Mitchell</div>
      <div class="nt-title">Senior Technical Recruiter</div>
    </div>

    <!-- Speaking bars (question state) -->
    <div class="speak-bars" id="speak">
      <div class="sbar"></div><div class="sbar"></div>
      <div class="sbar"></div><div class="sbar"></div>
      <div class="sbar"></div>
    </div>

    <!-- Listening bars (hearing state) -->
    <div class="wave-bars" id="waves">
      <div class="bar"></div><div class="bar"></div>
      <div class="bar"></div><div class="bar"></div>
      <div class="bar"></div>
    </div>

    <!-- Mic icon (hearing state) -->
    <div class="mic-overlay" id="mic">🎙️</div>
  </div>

  <!-- Status bar -->
  <div class="status-bar">
    <div class="sl">
      <div class="av">👔</div>
      <div>
        <div class="av-name">Sarah Mitchell</div>
        <div class="av-title">Senior Technical Recruiter · AI Systems</div>
      </div>
    </div>
    <div class="badge" id="badge">
      <div class="bdot pulse" id="bdot"></div>
      <span id="blbl">{label}</span>
    </div>
  </div>
</div>

<script>(function(){{

  /* ── Config injected by Python ──────────────────────────────────────────── */
  const INIT_STATE = "{state}";
  const FB_B64     = "{feedback_b64}";
  const Q_B64      = "{question_b64}";

  /* ── State colour map ───────────────────────────────────────────────────── */
  const COLORS = {{
    new_final_question:{{ border:"#22C55E", dot:"#22C55E", glow:"rgba(34,197,94,.35)",  lbl:"Asking Question"     }},
    new_waiting: {{ border:"#4A5568", dot:"#4A5568", glow:"rgba(74,99,128,.20)",  lbl:"Waiting for Response"}},
    new_hearing: {{ border:"#3B6BE8", dot:"#3B6BE8", glow:"rgba(59,107,232,.35)", lbl:"Listening\u2026"     }},
  }};

  /* ── DOM refs ───────────────────────────────────────────────────────────── */
  const panel = document.getElementById("panel");
  const vq    = document.getElementById("vq");
  const vw    = document.getElementById("vw");
  const vh    = document.getElementById("vh");
  const aud   = document.getElementById("aud");
  const badge = document.getElementById("badge");
  const bdot  = document.getElementById("bdot");
  const blbl  = document.getElementById("blbl");
  const speak = document.getElementById("speak");
  const waves = document.getElementById("waves");
  const mic   = document.getElementById("mic");

  let cur = null;

  /* ── Preload all videos (they start paused & hidden) ────────────────────── */
  [vq, vw, vh].forEach(v => v.load());

  /* ── Video toggle helper ─────────────────────────────────────────────────── */
  function setVid(el, on) {{
    if (on) {{
      el.classList.replace("hidden", "visible");
      el.play().catch(() => {{}});
    }} else {{
      el.classList.replace("visible", "hidden");
      el.pause();
    }}
  }}

  /* ── Apply interviewer state ─────────────────────────────────────────────── */
  function applyState(s) {{
    if (s === cur) return;
    cur = s;
    const c = COLORS[s] || COLORS.new_waiting;

    // Panel border + glow
    panel.style.borderColor = c.border;
    panel.style.boxShadow   = `0 0 36px ${{c.glow}}, 0 8px 44px rgba(0,0,0,.65)`;

    // Status badge
    bdot.style.background = c.dot;
    badge.style.color     = c.dot;
    blbl.textContent      = c.lbl;

    // Videos
    setVid(vq, s === "new_final_question");
    setVid(vw, s === "new_waiting");
    setVid(vh, s === "new_hearing");

    // Overlays
    speak.classList.toggle("show", s === "new_final_question");
    waves.classList.toggle("show", s === "new_hearing");
    mic.classList.toggle("show",   s === "new_hearing");
  }}

  /* ── Audio playback helper ───────────────────────────────────────────────── */
  function playB64(b64, onEnd) {{
    if (!b64) {{ if (onEnd) onEnd(); return; }}
    aud.src = "data:audio/mp3;base64," + b64;
    aud.play().catch(() => {{ if (onEnd) onEnd(); }});
    aud.onended = () => {{ aud.onended = null; if (onEnd) onEnd(); }};
  }}

  /* ── Question state: play feedback → question → waiting ─────────────────── */
  function runQuestionFlow() {{
    applyState("new_final_question");
    if (!FB_B64 && !Q_B64) {{
      // No audio provided — stay as question briefly then go waiting
      applyState("new_waiting");
      return;
    }}
    playB64(FB_B64, () => {{
      playB64(Q_B64, () => {{
        applyState("new_waiting");
      }});
    }});
  }}

  /* ── Parent DOM polling: detect st.audio_input recording ────────────────── */
  function pollParentRecording() {{
    try {{
      const pd = window.parent.document;
      let wasRec = false;

      setInterval(() => {{
        // Streamlit 1.31+ audio_input record button selectors
        const btn = pd.querySelector(
          '[data-testid="stAudioInputRecordButton"],' +
          '[data-testid="stAudioInputRecordingButton"],' +
          'button[aria-label="Start recording"],' +
          'button[aria-label="Stop recording"]'
        );
        if (!btn) return;

        const lbl   = (btn.getAttribute("aria-label") || "").toLowerCase();
        const isRec = lbl.includes("stop") ||
                      btn.getAttribute("aria-pressed") === "true";

        if (isRec && !wasRec) {{
          wasRec = true;
          applyState("new_hearing");
        }} else if (!isRec && wasRec) {{
          wasRec = false;
          if (cur === "new_hearing") applyState("new_waiting");
        }}
      }}, 250);

    }} catch (e) {{
      /* Cross-origin guard — DOM polling silently disabled */
    }}
  }}

  /* ── Message bus: sibling components or parent can push state changes ────── */
  window.addEventListener("message", e => {{
    if (!e.data || !e.data.ivState) return;
    if (e.data.ivState === "new_final_question") runQuestionFlow();
    else applyState(e.data.ivState);
  }});

  /* ── Bootstrap ───────────────────────────────────────────────────────────── */
  if (INIT_STATE === "new_final_question") {{
    runQuestionFlow();
  }} else {{
    applyState(INIT_STATE || "new_waiting");
  }}

  pollParentRecording();

}})();
</script>
</body></html>"""

    components.html(html, height=height, scrolling=False)
