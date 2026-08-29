"""
Streamlit chat UI for the cloud RAG pipeline (Gemini + Pinecone).

Run with: streamlit run app.py  (from the project root)
Make sure you've already run `python src/embed.py` at least once
to build the index before chatting.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from generate import generate_answer_stream

st.set_page_config(page_title="Cloud RAG Chat", page_icon="☁️")
st.title("☁️ Cloud RAG Assistant")
st.caption("Gemini API + Pinecone vector DB")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            st.caption(f"📄 Sources: {', '.join(msg['sources'])}")

if query := st.chat_input("Ask something about your documents..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_answer = ""
        sources = []
        retrieved_chunks = []

        for event in generate_answer_stream(query):
            if event["type"] == "token":
                full_answer += event["text"]
                placeholder.markdown(full_answer + "▌")
            elif event["type"] == "done":
                sources = event["sources"]
                retrieved_chunks = event["retrieved_chunks"]

        placeholder.markdown(full_answer)
        if sources:
            st.caption(f"📄 Sources: {', '.join(sources)}")

        with st.expander("🔍 Retrieved chunks (debug)"):
            for chunk in retrieved_chunks:
                st.text(f"[{chunk['source']} #{chunk['chunk_id']}] distance={chunk['distance']:.4f}")
                st.text(chunk["text"][:300])
                st.divider()

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_answer,
        "sources": sources,
    })
