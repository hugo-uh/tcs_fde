"""Streamlit UI for the IT Support chatbot.
"""

import streamlit as st

from app_implementation import chat, load_mcp_tools

st.set_page_config(page_title="IT Support Bot", page_icon="🛠️")
st.title("🛠️ IT Support Chatbot")
st.caption("RAG (VoyageAI) · web search · current date/time · ticketing via MCP")

# `messages`: API history (includes RAG context); `display`: what the user sees.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "display" not in st.session_state:
    st.session_state.display = []

with st.sidebar:
    st.header("Status")
    if st.button("Reload MCP tools"):
        st.session_state.mcp_tools = load_mcp_tools()
    if "mcp_tools" not in st.session_state:
        st.session_state.mcp_tools = load_mcp_tools()
    if st.session_state.mcp_tools:
        st.success("MCP server connected")
        for tool in st.session_state.mcp_tools:
            st.write(f"• {tool['name']}")
    else:
        st.warning("MCP server unavailable (http://localhost:3000). Ticket tools disabled.")
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.display = []
        st.rerun()

for msg in st.session_state.display:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Describe your IT problem..."):
    st.session_state.display.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = chat(st.session_state.messages, user_input)
            except Exception as e:
                answer = f"Sorry, something went wrong: {e}"
        st.markdown(answer)
    st.session_state.display.append({"role": "assistant", "content": answer})

