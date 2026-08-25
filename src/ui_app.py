import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit.components.v1 as components

from agent import handle_turn

ACTIONS_HTML = """
<div class="actions-row" style="display:flex;gap:4px;margin-top:2px;justify-content:__ALIGN__;">
  <button class="act copy-btn" title="Copy" onclick="copyText(this)">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="9" y="9" width="13" height="13" rx="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  </button>
  <button class="act" title="Helpful" onclick="fb(this)">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
    </svg>
  </button>
  <button class="act" title="Not helpful" onclick="fb(this)">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
    </svg>
  </button>
  <span class="copied" style="display:none;color:#4c8a4c;font-size:11.5px;margin-left:4px;">Copied</span>
</div>
<script>
function copyText(btn) {
  var text = window.__copyText || "";
  var done = function () {
    var note = btn.parentNode.querySelector(".copied");
    note.style.display = "inline";
    setTimeout(function () { note.style.display = "none"; }, 1200);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done);
  } else {
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    done();
  }
}
function fb(btn) {
  var buttons = btn.parentNode.querySelectorAll("button");
  var wasActive = btn.classList.contains("active");
  buttons.forEach(function (b) {
    if (!b.classList.contains("copy-btn")) b.classList.remove("active");
  });
  if (!wasActive) btn.classList.add("active");
}
</script>
<style>
  .act {
    width: 30px; height: 30px;
    display: inline-flex; align-items: center; justify-content: center;
    border: none; border-radius: 9px;
    background: transparent; color: #808790;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }
  .act:hover { background: #eef0f2; color: #4d545d; }
  .act.active { background: #e7eaed; color: #40464d; }
</style>
"""


def _message_actions(text: str, align: str = "left") -> None:
    payload = json.dumps(text)
    align_value = "flex-end" if align == "right" else "flex-start"
    row_html = ACTIONS_HTML.replace("__ALIGN__", align_value)
    html = (
        "<div style='position:absolute;left:-9999px;' id='copy-src'></div>"
        f"<script>window.__copyText = {payload};</script>" + row_html
    )
    components.html(html, height=44, scrolling=False)

st.set_page_config(
    page_title="Aster & Row Support",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
}

.stApp {
    background: #ffffff;
}

header[data-testid="stHeader"] {
    display: none;
}

.block-container {
    max-width: 860px;
    padding-top: 1rem;
    padding-bottom: 7rem;
}

.header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.4rem;
}

.icon-btn {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    border: 1px solid #e3e5e8;
    background: #f6f7f8;
    color: #555c64;
    font-size: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(31, 35, 41, 0.06);
}

.icon-btn:hover {
    background: #ececee;
}

.brand-pill {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 26px 8px 10px;
    background: #ffffff;
    border: 1px solid #e3e5e8;
    border-radius: 30px;
    box-shadow: 0 3px 14px rgba(31, 35, 41, 0.10);
}

.brand-logo {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #000000;
    color: #ffffff;
    font-size: 19px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
}

.brand-name {
    font-size: 17px;
    font-weight: 600;
    letter-spacing: -0.2px;
    color: #2f343a;
    white-space: nowrap;
}

div[data-testid="stChatMessage"] {
    background: transparent;
}

.user-bubble {
    background: #ececee;
    border-radius: 24px;
    padding: 15px 24px;
    color: #3c4147;
    font-size: 15.5px;
    line-height: 1.55;
    margin-left: auto;
    margin-bottom: 4px;
    width: fit-content;
    max-width: 78%;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.agent-answer {
    color: #3d4249;
    font-size: 15.5px;
    line-height: 1.62;
    margin-bottom: 4px;
}

.sources-line {
    margin-top: 10px;
    color: #6f7680;
    font-size: 12.5px;
    line-height: 1.55;
}

.sources-title {
    font-weight: 600;
    color: #606871;
}

.handoff-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    padding: 5px 14px;
    border-radius: 16px;
    background: #f6e8e8;
    border: 1px solid #e4cfcf;
    color: #a45151;
    font-size: 13px;
    font-weight: 500;
}

.footer-note {
    position: fixed;
    bottom: 84px;
    left: 0;
    right: 0;
    text-align: center;
    color: #969ca4;
    font-size: 11.5px;
    pointer-events: none;
}

[data-testid="stChatInput"] {
    border-radius: 28px;
    border: 1px solid #d7dbe0;
    background: #f4f5f6;
}

[data-testid="stSidebar"] {
    background: #f8f9fa;
    border-right: 1px solid #e8eaed;
}

[data-testid="stSidebar"] * {
    color: #3d4249 !important;
}

details summary {
    font-size: 12px;
    color: #9298a0;
}

.stButton > button {
    border-radius: 50%;
    min-width: 46px;
    height: 46px;
    padding: 0;
    font-size: 19px;
    border: 1px solid #e3e5e8;
    background: #f6f7f8;
    color: #555c64;
    box-shadow: 0 2px 8px rgba(31, 35, 41, 0.06);
}

.stButton > button:hover {
    background: #ececee;
    border-color: #d5d8db;
}
</style>
"""

WELCOME = (
    "Hello! I'm the Aster & Row support assistant.\n\n"
    "I can help you with shipping, returns, warranties, memberships, "
    "gift cards, and order status."
)


def _user_bubble(content: str) -> None:
    st.markdown(
        f'<div class="user-bubble">{content}</div>',
        unsafe_allow_html=True,
    )
    _message_actions(content, align="right")


def _agent_block(turn: dict) -> None:
    st.markdown(
        f'<div class="agent-answer">{turn["answer_html"]}</div>',
        unsafe_allow_html=True,
    )

    if turn["sources"]:
        source_text = ", ".join(
            f"{s['filename']} :: {s['heading']}" for s in turn["sources"]
        )
        st.markdown(
            f'<div class="sources-line">'
            f'<span class="sources-title">Sources:</span> {source_text}</div>',
            unsafe_allow_html=True,
        )

    if turn["human_handoff"]:
        st.markdown(
            '<div><span class="handoff-badge">&#129485; '
            "Recommending human support</span></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.get("debug_mode"):
        with st.expander("Debug trace"):
            st.json(turn["trace"])

    _message_actions(turn["answer_html"].replace("<br>", "\n").replace("&amp;", "&").replace("&lt;", "<"))


def _welcome_turn() -> dict:
    return {
        "role": "assistant",
        "answer_html": WELCOME.replace("\n\n", "<br><br>"),
        "sources": [],
        "human_handoff": False,
        "trace": {"note": "welcome message"},
    }


def init_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:12]
    if "turns" not in st.session_state:
        st.session_state.turns = [_welcome_turn()]
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False


def main() -> None:
    init_state()

    with st.sidebar:
        st.markdown("### Aster & Row Support")
        st.caption(f"Session `{st.session_state.session_id}`")
        st.session_state.debug_mode = st.toggle(
            "Debug mode", value=st.session_state.debug_mode,
            help="Show per-turn traces (also saved to traces/)",
        )
        if st.button("New chat", use_container_width=True):
            st.session_state.session_id = uuid.uuid4().hex[:12]
            st.session_state.turns = [_welcome_turn()]
            st.rerun()

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    left, center, right = st.columns([1, 5, 1], vertical_alignment="center")
    with left:
        if st.button("＋", key="new-chat", help="New chat"):
            st.session_state.session_id = uuid.uuid4().hex[:12]
            st.session_state.turns = [_welcome_turn()]
            st.rerun()
    with center:
        st.markdown(
            '<div style="display:flex; justify-content:center;">'
            '<div class="brand-pill">'
            '<div class="brand-logo">A</div>'
            '<div class="brand-name">Aster &amp; Row Support</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )
    with right:
        debug_label = "🐞" if not st.session_state.debug_mode else "🐞✓"
        if st.button(debug_label, key="debug-toggle", help="Toggle debug mode"):
            st.session_state.debug_mode = not st.session_state.debug_mode
            st.rerun()

    for turn in st.session_state.turns:
        if turn["role"] == "user":
            _user_bubble(turn["answer_html"])
        else:
            _agent_block(turn)

    st.markdown(
        '<div class="footer-note">AI can make mistakes. '
        "Powered by Aster &amp; Row</div>",
        unsafe_allow_html=True,
    )

    user_input = st.chat_input("Ask anything")
    if user_input and user_input.strip():
        user_text = user_input.strip()
        _user_bubble(user_text)
        with st.spinner("thinking..."):
            outcome = handle_turn(st.session_state.session_id, user_text)
        st.session_state.turns.append({"role": "user", "answer_html": user_text})
        st.session_state.turns.append(
            {
                "role": "assistant",
                "answer_html": outcome["answer"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace("\n", "<br>"),
                "sources": outcome["sources"],
                "human_handoff": outcome["human_handoff"],
                "trace": outcome["trace"],
            }
        )
        st.rerun()


if __name__ == "__main__":
    main()
