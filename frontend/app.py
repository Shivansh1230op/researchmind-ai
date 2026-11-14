"""DocuMind AI — Streamlit Frontend

A modern, responsive web interface for the DocuMind AI document
intelligence platform.  Communicates with the FastAPI backend via HTTP.

Features:
- Sidebar: document upload, document list, delete
- Main panel: AI chat interface with conversation history
- Source citation panel with document name and page number
- Document preview
- Summarization and comparison tools
- Loading indicators and error handling
- Clear chat functionality

Run with: ``streamlit run frontend/app.py``
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

# ── Configuration ──────────────────────────────────────────────

# Backend API URL (configurable via environment variable)
API_BASE_URL = os.environ.get("DOCUMIND_API_URL", "http://localhost:8000")

# Page configuration — must be the first Streamlit command
st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/yourusername/documind-ai",
        "Report a Bug": "https://github.com/yourusername/documind-ai/issues",
        "About": (
            "DocuMind AI — RAG-powered document intelligence platform. "
            "Upload documents and ask questions with grounded, cited answers."
        ),
    },
)


# ── API Helper Functions ──────────────────────────────────────

def api_health_check() -> dict:
    """Check if the backend API is running."""
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return resp.json() if resp.status_code == 200 else {"status": "unhealthy"}
    except Exception:
        return {"status": "unreachable"}


def api_upload_document(file) -> dict:
    """Upload a document to the backend."""
    files = {"file": (file.name, file.getvalue(), "application/octet-stream")}
    resp = requests.post(f"{API_BASE_URL}/documents/upload", files=files, timeout=300)
    resp.raise_for_status()
    return resp.json()


def api_list_documents() -> dict:
    """List all uploaded documents."""
    resp = requests.get(f"{API_BASE_URL}/documents", timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_delete_document(doc_id: str) -> dict:
    """Delete a document by ID."""
    resp = requests.delete(f"{API_BASE_URL}/documents/{doc_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_chat(question: str, session_id: str, document_ids=None, top_k=None) -> dict:
    """Send a chat question to the backend."""
    payload = {"question": question, "session_id": session_id}
    if document_ids:
        payload["document_ids"] = document_ids
    if top_k:
        payload["top_k"] = top_k
    resp = requests.post(f"{API_BASE_URL}/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def api_get_history(session_id: str) -> dict:
    """Get chat history for a session."""
    resp = requests.get(f"{API_BASE_URL}/chat/history", params={"session_id": session_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_clear_history(session_id: str) -> dict:
    """Clear chat history for a session."""
    resp = requests.post(f"{API_BASE_URL}/chat/clear", params={"session_id": session_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_summarize(doc_id: str, summary_type: str = "comprehensive") -> dict:
    """Request document summarization."""
    payload = {"document_id": doc_id, "summary_type": summary_type}
    resp = requests.post(f"{API_BASE_URL}/documents/summarize", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def api_compare(doc_ids: list, aspect: str = "general") -> dict:
    """Request document comparison."""
    payload = {"document_ids": doc_ids, "aspect": aspect}
    resp = requests.post(f"{API_BASE_URL}/documents/compare", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ── Session State Initialization ───────────────────────────────

def init_session_state():
    """Initialize Streamlit session state variables."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_doc_ids" not in st.session_state:
        st.session_state.selected_doc_ids = []
    if "documents_cache" not in st.session_state:
        st.session_state.documents_cache = None


def refresh_documents():
    """Force refresh of the document list."""
    st.session_state.documents_cache = None


# ── Custom CSS ────────────────────────────────────────────────

def load_css():
    """Inject custom CSS for a modern SaaS-like appearance."""
    st.markdown("""
    <style>
    /* Main container styling */
    .main .block-container {
        max-width: 1400px;
        padding-top: 2rem;
    }

    /* Title styling */
    .documind-title {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }

    .documind-subtitle {
        font-size: 0.9rem;
        color: #888;
        margin-bottom: 1.5rem;
    }

    /* Chat message styling */
    .chat-message {
        padding: 1rem;
        border-radius: 0.75rem;
        margin-bottom: 1rem;
        max-width: 85%;
    }

    .chat-message.user {
        background-color: #f0f4ff;
        margin-left: auto;
        border-left: 3px solid #667eea;
    }

    .chat-message.assistant {
        background-color: #f9f9f9;
        border-left: 3px solid #764ba2;
    }

    .chat-message .role-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }

    /* Source citation card */
    .source-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
    }

    .source-card .source-header {
        font-weight: 600;
        color: #667eea;
        margin-bottom: 0.25rem;
    }

    .source-card .source-content {
        color: #555;
        font-style: italic;
        max-height: 100px;
        overflow-y: auto;
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
    }

    .status-ready { background: #d4edda; color: #155724; }
    .status-processing { background: #fff3cd; color: #856404; }
    .status-error { background: #f8d7da; color: #721c24; }

    /* Upload area */
    .upload-box {
        border: 2px dashed #ccc;
        border-radius: 0.5rem;
        padding: 1rem;
        text-align: center;
    }

    /* Document list item */
    .doc-item {
        padding: 0.5rem;
        border-radius: 0.375rem;
        margin-bottom: 0.3rem;
        transition: background 0.2s;
    }

    .doc-item:hover {
        background: #f5f5f5;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Sidebar: Document Management ──────────────────────────────

def render_sidebar():
    """Render the sidebar with upload, document list, and document tools."""
    with st.sidebar:
        st.markdown('<div class="documind-title">📄 DocuMind AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="documind-subtitle">Document Intelligence Platform</div>', unsafe_allow_html=True)

        st.divider()

        # Health check
        health = api_health_check()
        if health.get("status") == "healthy":
            st.success("✅ Backend connected")
        elif health.get("status") == "degraded":
            st.warning("⚠️ Backend degraded")
        else:
            st.error("❌ Backend not reachable")
            st.caption(f"Check that the API is running at `{API_BASE_URL}`")
            return False

        st.divider()

        # ── Document Upload ──
        st.subheader("📤 Upload Documents")
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            help="Upload PDF, DOCX, or TXT files (max 50MB each)",
        )

        if uploaded_files:
            if st.button("Process Documents", type="primary", use_container_width=True):
                for uploaded_file in uploaded_files:
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        try:
                            result = api_upload_document(uploaded_file)
                            st.success(f"✅ {result['filename']} — {result['total_chunks']} chunks")
                            refresh_documents()
                        except requests.exceptions.HTTPError as exc:
                            error_detail = "Unknown error"
                            try:
                                error_detail = exc.response.json().get("detail", str(exc))
                            except Exception:
                                error_detail = str(exc)
                            st.error(f"❌ {uploaded_file.name}: {error_detail}")
                        except Exception as exc:
                            st.error(f"❌ {uploaded_file.name}: {str(exc)}")

        st.divider()

        # ── Document List ──
        st.subheader("📋 Your Documents")

        if st.session_state.documents_cache is None:
            try:
                result = api_list_documents()
                st.session_state.documents_cache = result
            except Exception as exc:
                st.error(f"Failed to load documents: {exc}")
                st.session_state.documents_cache = {"documents": [], "total": 0}

        docs = st.session_state.documents_cache.get("documents", [])

        if not docs:
            st.info("No documents uploaded yet. Upload files above to get started.")
        else:
            st.caption(f"{len(docs)} document(s) total")

            for doc in docs:
                with st.container():
                    col1, col2 = st.columns([4, 1])

                    with col1:
                        # Status badge
                        status_class = f"status-{doc['status']}"
                        st.markdown(
                            f'<div class="doc-item">'
                            f'<strong>{doc["filename"]}</strong><br>'
                            f'<span class="status-badge {status_class}">{doc["status"]}</span> '
                            f'• {doc["file_type"].upper()} • {doc["total_chunks"]} chunks'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    with col2:
                        if st.button("🗑️", key=f"del_{doc['id']}", help="Delete"):
                            try:
                                api_delete_document(doc["id"])
                                st.success(f"Deleted {doc['filename']}")
                                refresh_documents()
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Delete failed: {exc}")

                    # Checkbox for filtering search to this document
                    if doc["status"] == "ready":
                        is_selected = doc["id"] in st.session_state.selected_doc_ids
                        if st.checkbox(
                            f"Search this doc",
                            value=is_selected,
                            key=f"chk_{doc['id']}",
                        ):
                            if not is_selected:
                                st.session_state.selected_doc_ids.append(doc["id"])
                        else:
                            if is_selected:
                                st.session_state.selected_doc_ids.remove(doc["id"])

            # Select all / clear all
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Select All", use_container_width=True):
                    st.session_state.selected_doc_ids = [
                        d["id"] for d in docs if d["status"] == "ready"
                    ]
                    st.rerun()
            with col2:
                if st.button("Clear Selection", use_container_width=True):
                    st.session_state.selected_doc_ids = []
                    st.rerun()

        st.divider()

        # ── Advanced Tools ──
        with st.expander("🛠️ Advanced Tools"):
            st.markdown("**Summarize a Document**")
            if docs:
                sum_doc = st.selectbox(
                    "Select document",
                    options=[d["id"] for d in docs if d["status"] == "ready"],
                    format_func=lambda x: next(
                        (d["filename"] for d in docs if d["id"] == x), x
                    ),
                    key="summarize_doc",
                )
                sum_type = st.selectbox(
                    "Summary type",
                    ["comprehensive", "key_points", "definitions"],
                    key="summarize_type",
                )
                if st.button("Generate Summary", key="btn_summarize"):
                    with st.spinner("Generating summary..."):
                        try:
                            result = api_summarize(sum_doc, sum_type)
                            st.session_state.last_summary = result
                        except Exception as exc:
                            st.error(f"Summarization failed: {exc}")
            else:
                st.info("Upload documents to use this feature.")

            st.markdown("---")
            st.markdown("**Compare Documents**")
            ready_docs = [d for d in docs if d["status"] == "ready"]
            if len(ready_docs) >= 2:
                comp_docs = st.multiselect(
                    "Select 2-5 documents to compare",
                    options=[d["id"] for d in ready_docs],
                    format_func=lambda x: next(
                        (d["filename"] for d in ready_docs if d["id"] == x), x
                    ),
                    key="compare_docs",
                )
                comp_aspect = st.selectbox(
                    "Comparison aspect",
                    ["general", "methodology", "findings", "arguments"],
                    key="compare_aspect",
                )
                if st.button("Compare", key="btn_compare"):
                    if len(comp_docs) >= 2:
                        with st.spinner("Comparing documents..."):
                            try:
                                result = api_compare(comp_docs, comp_aspect)
                                st.session_state.last_comparison = result
                            except Exception as exc:
                                st.error(f"Comparison failed: {exc}")
                    else:
                        st.warning("Select at least 2 documents.")
            else:
                st.info("Upload at least 2 documents to compare.")

        st.divider()

        # ── Session Info ──
        st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")
        if st.button("🔄 New Session", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

    return True


# ── Main Chat Interface ───────────────────────────────────────

def render_chat_interface():
    """Render the main chat panel in the center column."""
    # Header
    st.markdown("## 🤖 Document Q&A")
    st.markdown("Ask questions about your uploaded documents. Answers are grounded in the document content with source citations.")

    # Display advanced results (summary / comparison) if available
    if "last_summary" in st.session_state:
        summary = st.session_state.last_summary
        with st.expander(f"📊 Summary: {summary.get('document_name', '')}", expanded=True):
            st.markdown(summary.get("summary", ""))
            if summary.get("key_points"):
                st.markdown("**Key Points:**")
                for pt in summary["key_points"]:
                    st.markdown(f"- {pt}")
            if summary.get("definitions"):
                st.markdown("**Definitions:**")
                for d in summary["definitions"]:
                    st.markdown(f"- **{d['term']}**: {d['definition']}")
        del st.session_state.last_summary

    if "last_comparison" in st.session_state:
        comp = st.session_state.last_comparison
        with st.expander(f"📊 Comparison: {', '.join(comp.get('document_names', []))}", expanded=True):
            st.markdown(comp.get("comparison", ""))
        del st.session_state.last_comparison

    # Chat history display
    chat_container = st.container()

    with chat_container:
        if not st.session_state.messages:
            # Welcome message
            st.markdown(
                '<div class="chat-message assistant">'
                '<div class="role-label">🤖 DocuMind AI</div>'
                'Hello! I\'m DocuMind AI, your document intelligence assistant. '
                'Upload some documents using the sidebar, then ask me questions about them. '
                'I\'ll search through your documents and provide answers with source citations.'
                '</div>',
                unsafe_allow_html=True,
            )

        for msg in st.session_state.messages:
            role = msg["role"]
            role_label = "👤 You" if role == "user" else "🤖 DocuMind AI"
            css_class = "user" if role == "user" else "assistant"

            st.markdown(
                f'<div class="chat-message {css_class}">'
                f'<div class="role-label">{role_label}</div>'
                f'{msg["content"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Show sources for assistant messages
            if role == "assistant" and msg.get("sources"):
                with st.expander("📎 Source Citations", expanded=False):
                    for idx, src in enumerate(msg["sources"], 1):
                        page_info = f", page {src['page_number']}" if src.get("page_number") else ""
                        st.markdown(
                            f'<div class="source-card">'
                            f'<div class="source-header">Source {idx}: '
                            f'{src["document_name"]}{page_info}</div>'
                            f'<div class="source-content">{src["content"][:300]}...</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    # Clear chat button
    if st.session_state.messages:
        if st.button("🗑️ Clear Chat", help="Clear all conversation history"):
            try:
                api_clear_history(st.session_state.session_id)
                st.session_state.messages = []
                st.rerun()
            except Exception as exc:
                st.warning(f"Could not clear history from server: {exc}")
                st.session_state.messages = []
                st.rerun()

    st.divider()

    # Chat input
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            user_input = st.text_area(
                "Ask a question about your documents:",
                height=68,
                placeholder="e.g., What are the key findings in this research paper?",
                label_visibility="collapsed",
            )
        with col2:
            submitted = st.form_submit_button("Ask 📤", type="primary", use_container_width=True)
            top_k = st.number_input("Results", min_value=1, max_value=20, value=5,
                                    help="Number of chunks to retrieve",
                                    label_visibility="collapsed")

        if submitted and user_input.strip():
            # Add user message to UI
            st.session_state.messages.append({"role": "user", "content": user_input.strip()})

            # Determine document filter
            doc_filter = st.session_state.selected_doc_ids if st.session_state.selected_doc_ids else None

            # Call the API
            with st.spinner("Searching documents and generating answer..."):
                try:
                    result = api_chat(
                        question=user_input.strip(),
                        session_id=st.session_state.session_id,
                        document_ids=doc_filter,
                        top_k=int(top_k),
                    )

                    # Add assistant response to UI
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result.get("sources", []),
                    })

                    if result.get("no_answer_found"):
                        st.info("ℹ️ The answer could not be found in the uploaded documents.")

                except requests.exceptions.HTTPError as exc:
                    error_detail = "Unknown error"
                    try:
                        error_detail = exc.response.json().get("detail", str(exc))
                    except Exception:
                        error_detail = str(exc)
                    st.error(f"❌ Error: {error_detail}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"I encountered an error: {error_detail}",
                        "sources": [],
                    })
                except Exception as exc:
                    st.error(f"❌ Error: {str(exc)}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"I encountered an error: {str(exc)}",
                        "sources": [],
                    })

            st.rerun()


# ── Main Application ───────────────────────────────────────────

def main():
    """Main application entry point."""
    init_session_state()
    load_css()

    # Render sidebar and check backend health
    backend_ok = render_sidebar()

    if not backend_ok:
        st.markdown("## Welcome to DocuMind AI")
        st.warning("⚠️ The backend API is not reachable. Please start the FastAPI server first:")
        st.code("uvicorn app.main:app --reload", language="bash")
        st.markdown(f"Expected API URL: `{API_BASE_URL}`")
        return

    # Two-column layout: chat (wide) + info panel (narrow)
    col_chat, col_info = st.columns([3, 1])

    with col_chat:
        render_chat_interface()

    with col_info:
        # Right panel: Tips and document info
        st.markdown("### 💡 Tips")
        st.markdown("""
        - **Upload documents** via the sidebar
        - **Select documents** to filter search scope
        - **Ask specific questions** for better results
        - **Check citations** for source verification
        - **Use advanced tools** for summaries and comparisons
        """)

        # Show selected documents
        if st.session_state.selected_doc_ids:
            st.markdown("### 🎯 Searching in")
            for doc_id in st.session_state.selected_doc_ids:
                docs = st.session_state.documents_cache.get("documents", []) if st.session_state.documents_cache else []
                name = next((d["filename"] for d in docs if d["id"] == doc_id), doc_id)
                st.markdown(f"- {name}")


if __name__ == "__main__":
    main()
