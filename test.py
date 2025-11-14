import streamlit as st
import requests
from typing import List, Dict, Optional
import time

# Page configuration
st.set_page_config(
    page_title="HRMS Chat", 
    page_icon="💬", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-container {
        background-color: #f8fafc;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        max-height: 70vh;
        overflow-y: auto;
    }
    .user-message {
        background-color: #3b82f6;
        color: white;
        padding: 1rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
    }
    .assistant-message {
        background-color: #e2e8f0;
        color: #1f2937;
        padding: 1rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-right: auto;
    }
    .message-time {
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 0.25rem;
    }
    .input-container {
        position: fixed;
        bottom: 2rem;
        left: 50%;
        transform: translateX(-50%);
        width: 80%;
        background: white;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        z-index: 100;
    }
    .sidebar-content {
        padding: 1rem;
    }
    .auth-section {
        background: #f1f5f9;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="main-header">HRMS Chat Assistant</div>', unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm your HR Assistant. I can help you with HR policies, employee information, documentation, and more. How can I assist you today?", "timestamp": time.time()}
    ]
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "clear_input" not in st.session_state:
    st.session_state.clear_input = False

# Sidebar
with st.sidebar:
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    
    st.markdown("### 🔧 Settings")
    api_url = st.text_input(
        "API Endpoint", 
        value="http://localhost:8000/employee/chat",
        help="URL of your FastAPI backend"
    )
    
    st.markdown("---")
    st.markdown("### 🔐 Authentication")
    
    # Auth tabs
    auth_tab1, auth_tab2, auth_tab3 = st.tabs(["Login", "Sign Up", "Logout"])
    
    with auth_tab1:
        st.markdown('<div class="auth-section">', unsafe_allow_html=True)
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn", use_container_width=True):
            if login_email and login_password:
                login_url = api_url.replace("/employee/chat", "/auth/login")
                try:
                    with st.spinner("Logging in..."):
                        r = requests.post(
                            login_url, 
                            data={"username": login_email, "password": login_password}, 
                            timeout=10
                        )
                        r.raise_for_status()
                        data = r.json()
                        token = data.get("access_token") or data.get("token")
                        if token:
                            st.session_state.token = token
                            st.session_state.username = data.get("username") or login_email
                            if data.get("session_id"):
                                st.session_state.session_id = data.get("session_id")
                            st.success(f"Welcome, {st.session_state.username}!")
                            st.rerun()
                        else:
                            st.error("Login failed: No token received")
                except Exception as e:
                    st.error(f"Login failed: {str(e)}")
            else:
                st.warning("Please enter both email and password")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with auth_tab2:
        st.markdown('<div class="auth-section">', unsafe_allow_html=True)
        signup_full_name = st.text_input("Full Name", key="signup_name")
        signup_username = st.text_input("Username", key="signup_username")
        signup_email = st.text_input("Email", key="signup_email")
        signup_grade = st.text_input("Grade", key="signup_grade")
        signup_password = st.text_input("Password", type="password", key="signup_password")
        
        if st.button("Create Account", key="signup_btn", use_container_width=True):
            if all([signup_email, signup_username, signup_password, signup_full_name]):
                signup_payload = {
                    "email": signup_email,
                    "username": signup_username,
                    "password": signup_password,
                    "full_name": signup_full_name,
                    "grade": signup_grade,
                }
                try:
                    with st.spinner("Creating account..."):
                        r = requests.post(
                            api_url.replace("/employee/chat", "/auth/signup"), 
                            json=signup_payload, 
                            timeout=10
                        )
                        if r.status_code == 200:
                            st.success("Account created successfully! Please login.")
                        else:
                            st.error(f"Signup failed: {r.text}")
                except Exception as e:
                    st.error(f"Signup failed: {str(e)}")
            else:
                st.warning("Please fill all required fields")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with auth_tab3:
        if st.session_state.token:
            st.info(f"Logged in as: **{st.session_state.username}**")
            if st.button("Logout", key="logout_btn", use_container_width=True):
                st.session_state.token = None
                st.session_state.username = None
                st.session_state.session_id = None
                st.session_state.messages = [
                    {"role": "assistant", "content": "You have been logged out. Please login again to continue.", "timestamp": time.time()}
                ]
                st.success("Logged out successfully!")
                st.rerun()
        else:
            st.info("Not logged in")
    
    st.markdown("---")
    st.markdown("### 💬 Sessions")
    
    if st.session_state.token:
        if st.button("🔄 Refresh Sessions", use_container_width=True):
            st.rerun()
        
        # Session management would go here
        st.info("Session management features will appear here when logged in")
    else:
        st.info("Login to manage chat sessions")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Main chat area
col1, col2 = st.columns([1, 8])

with col2:
    # Chat messages container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-message">'
                f'<div>{msg["content"]}</div>'
                f'<div class="message-time">{time.strftime("%H:%M", time.localtime(msg.get("timestamp", time.time())))}</div>'
                f'</div>', 
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="assistant-message">'
                f'<div>{msg["content"]}</div>'
                f'<div class="message-time">{time.strftime("%H:%M", time.localtime(msg.get("timestamp", time.time())))}</div>'
                f'</div>', 
                unsafe_allow_html=True
            )
    
    st.markdown('</div>', unsafe_allow_html=True)

# Input area at bottom
st.markdown('<div class="input-container">', unsafe_allow_html=True)

input_col1, input_col2 = st.columns([6, 1])

with input_col1:
    user_input = st.text_input(
        "Type your message...",
        key="user_input",
        label_visibility="collapsed",
        placeholder="Ask about HR policies, employee info, or documentation..."
    )

with input_col2:
    send_clicked = st.button("Send", use_container_width=True)

if send_clicked and user_input.strip():
    # Add user message
    st.session_state.messages.append({
        "role": "user", 
        "content": user_input.strip(),
        "timestamp": time.time()
    })
    
    # Get AI response
    with st.spinner("Thinking..."):
        payload = {"message": user_input.strip()}
        if st.session_state.session_id:
            payload["session_id"] = st.session_state.session_id
        
        headers = {}
        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                reply = data.get("response") or data.get("reply") or data.get("answer") or str(data)
                
                # Update session ID if provided
                if data.get("session_id"):
                    st.session_state.session_id = data.get("session_id")
            else:
                reply = f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            reply = f"Sorry, I'm having trouble connecting to the server. Error: {str(e)}"
        
        # Add assistant response
        st.session_state.messages.append({
            "role": "assistant", 
            "content": reply,
            "timestamp": time.time()
        })
    
    # Clear input
    st.session_state.clear_input = True
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Status info
st.markdown("---")
col_status1, col_status2, col_status3 = st.columns(3)

with col_status1:
    if st.session_state.token:
        st.success("✅ Logged in")
    else:
        st.warning("🔒 Not logged in")

with col_status2:
    if st.session_state.session_id:
        st.info(f"Session: {st.session_state.session_id[:8]}...")
    else:
        st.info("No active session")

with col_status3:
    try:
        health_url = api_url.replace("/employee/chat", "/health")
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            st.success("✅ Backend connected")
        else:
            st.error("❌ Backend error")
    except:
        st.error("❌ Backend offline")

# Clear input if needed
if st.session_state.clear_input:
    st.session_state.clear_input = False