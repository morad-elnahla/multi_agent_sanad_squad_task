"""Small presentation helpers. Escape all content before rendering HTML."""
from html import escape
from datetime import datetime
import streamlit as st


def section(number, title):
    st.markdown(f'<div class="sq-section"><span class="sq-step">{escape(str(number))}</span>{escape(title)}</div>', unsafe_allow_html=True)


def piece_preview(piece):
    label = 'Technical thread' if piece['type'] == 'tech-thread' else piece['type'].replace('-', ' ').title()
    st.markdown(f'<div class="sq-card-head"><div><span class="sq-tag">{escape(label)} · {escape(piece["slot_id"])}</span>'
                f'<h3>{escape(piece["topic"])}</h3></div><span class="sq-pill">Accepted</span></div>', unsafe_allow_html=True)
    for i, post in enumerate(piece['posts'], 1):
        st.markdown(f'<div class="sq-post"><span class="sq-post-index">{i:02}</span><div>'
                    f'<div class="sq-post-body">{escape(post["text"])}</div>'
                    f'<div class="sq-post-meta">{len(post["text"])} characters · {len(post["evidence_ids"])} evidence references</div>'
                    '</div></div>', unsafe_allow_html=True)


def run_label(path, summary):
    started = summary.get('started_at', '')
    try:
        stamp = datetime.fromisoformat(started).strftime('%d %b %Y · %H:%M UTC')
    except (ValueError, TypeError):
        stamp = path.name
    return f'{stamp} · {summary.get("mode", "unknown").title()} · {summary.get("pieces_shipped", 0)}/{summary.get("pieces_requested", 0)} accepted · {path.name}'
