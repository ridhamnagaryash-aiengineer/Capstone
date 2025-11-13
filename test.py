# import streamlit as st
# import requests
# from typing import List, Dict, Optional


# st.set_page_config(page_title="HRMS Chat", page_icon="💬", layout="wide")
# st.title("HRMS Chat — HR Assistant")

# with st.expander("About"):
# 	st.write(
# 		"Lightweight Streamlit chat UI for the HR Assistant backend.\n"
# 		"POSTs JSON {\"message\": <text>} to the API and expects JSON with a reply field."
# 	)


# # Compatibility helper for rerunning the app across Streamlit versions
# def safe_rerun() -> None:
# 	"""Request a rerun in a way that works across Streamlit versions.

# 	Tries `st.experimental_rerun()` first, falls back to `st.script_request_rerun()`
# 	or `st.stop()` if neither exists.
# 	"""
# 	if hasattr(st, "experimental_rerun"):
# 		try:
# 			st.experimental_rerun()
# 			return
# 		except Exception:
# 			pass
# 	if hasattr(st, "script_request_rerun"):
# 		try:
# 			st.script_request_rerun()
# 			return
# 		except Exception:
# 			pass
# 	# As a last resort, stop execution so the UI can be interacted with again.
# 	st.stop()


# # ------------------
# # Settings + Session
# # ------------------
# st.sidebar.header("Settings")
# api_url = st.sidebar.text_input("FastAPI chat URL", value="http://localhost:8000/employee/chat")
# st.sidebar.markdown("Ensure FastAPI is running (e.g. `uvicorn main:app --reload --port 8000`).")
# st.sidebar.caption("API: POST JSON {\"message\": string, optional session_id} → ChatResponse JSON")

# # initialize session state
# if "token" not in st.session_state:
# 	st.session_state.token = None
# if "username" not in st.session_state:
# 	st.session_state.username = None
# if "messages" not in st.session_state:
# 	st.session_state.messages = [
# 		{"role": "assistant", "content": "Hello — I'm the HR Assistant. Ask me about HR docs, policies, or employee info."}
# 	]
# if "session_id" not in st.session_state:
# 	st.session_state.session_id = None

# # helper flag to clear the input on the next rerun (avoid modifying widget state after instantiation)
# if "clear_input_next_run" not in st.session_state:
# 	st.session_state.clear_input_next_run = False

# if st.session_state.get("clear_input_next_run"):
# 	# Set the input value before the widget is created on this run
# 	st.session_state["user_input"] = ""
# 	st.session_state.clear_input_next_run = False


# # ------------------
# # Authentication UI
# # ------------------
# st.sidebar.subheader("Authentication")
# auth_mode = st.sidebar.radio("Action", ["Login", "Signup", "Logout"])

# if auth_mode == "Signup":
# 	with st.sidebar.form("signup_form"):
# 		signup_full_name = st.text_input("Full name")
# 		signup_username = st.text_input("Username")
# 		signup_email = st.text_input("Email")
# 		signup_grade = st.text_input("Grade")
# 		signup_password = st.text_input("Password", type="password")
# 		signup_submitted = st.form_submit_button("Create account")
# 	if signup_submitted:
# 		signup_payload = {
# 			"email": signup_email,
# 			"username": signup_username,
# 			"password": signup_password,
# 			"full_name": signup_full_name,
# 			"grade": signup_grade,
# 		}
# 		try:
# 			r = requests.post(api_url.replace("/employee/chat", "/auth/signup"), json=signup_payload, timeout=10)
# 			r.raise_for_status()
# 			st.sidebar.success("Account created. Please switch to Login.")
# 		except Exception as e:
# 			st.sidebar.error(f"Signup failed: {e}")

# elif auth_mode == "Login":
# 	with st.sidebar.form("login_form"):
# 		login_email = st.text_input("Email")
# 		login_password = st.text_input("Password", type="password")
# 		login_submitted = st.form_submit_button("Login")
# 	if login_submitted:
# 		login_url = api_url.replace("/employee/chat", "/auth/login")
# 		try:
# 			# OAuth2PasswordRequestForm expects form-encoded 'username' and 'password'
# 			r = requests.post(login_url, data={"username": login_email, "password": login_password}, timeout=10)
# 			r.raise_for_status()
# 			data = r.json()
# 			token = data.get("access_token") or data.get("token") or data.get("accessToken")
# 			if token:
# 				st.session_state.token = token
# 				st.session_state.username = data.get("username") or login_email
# 				# Optionally backend may return session_id
# 				if isinstance(data, dict) and data.get("session_id"):
# 					st.session_state.session_id = data.get("session_id")
# 				st.sidebar.success(f"Logged in as {st.session_state.username}")
# 				safe_rerun()
# 			else:
# 				st.sidebar.error("Login response did not contain an access token")
# 		except Exception as e:
# 			st.sidebar.error(f"Login failed: {e}")
# 	else:  # Logout
# 		if st.sidebar.button("Logout"):
# 			st.session_state.token = None
# 			st.session_state.username = None
# 			st.session_state.session_id = None
# 			# preserve only greeting assistant message after logout
# 			st.session_state.messages = [
# 				{"role": "assistant", "content": "Hello — I'm the HR Assistant. Please login to access protected features."}
# 			]
# 			st.sidebar.info("Logged out")
# 			safe_rerun()
# def add_message(role: str, text: str) -> None:
# 	st.session_state.messages.append({"role": role, "content": text})


# def send_to_api(message: str, session_id: Optional[str] = None) -> str:
# 	payload = {"message": message}
# 	if session_id:
# 		payload["session_id"] = session_id
# 	headers = {}
# 	if st.session_state.get("token"):
# 		headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
# 	try:
# 		resp = requests.post(api_url, json=payload, headers=headers, timeout=20)
# 		resp.raise_for_status()
# 		data = resp.json()
# 		# If backend returns/creates a session id for this chat, store it
# 		if isinstance(data, dict):
# 			new_sid = data.get("session_id") or data.get("sessionId") or data.get("id")
# 			if new_sid:
# 				st.session_state.session_id = new_sid
# 		# common keys for reply
# 		if isinstance(data, dict):
# 			return data.get("response") or data.get("reply") or data.get("answer") or str(data)
# 		return str(data)
# 	except Exception as e:
# 		return f"[error contacting API] {e}"


# def _build_sessions_url() -> str:
# 	"""Return the sessions API base URL derived from `api_url`."""
# 	if "/employee/chat" in api_url:
# 		return api_url.replace("/employee/chat", "/employee/chat/sessions")
# 	if "/chat" in api_url and "/chat/sessions" not in api_url:
# 		return api_url.replace("/chat", "/chat/sessions")
# 	return api_url.rstrip("/") + "/sessions"


# def fetch_sessions() -> list:
# 	"""Fetch list of sessions from backend. Returns list of dicts {id,label,raw}.

# 	Safe to call from the sidebar; returns empty list on error.
# 	"""
# 	url = _build_sessions_url()
# 	headers = {}
# 	if st.session_state.get("token"):
# 		headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
# 	try:
# 		r = requests.get(url, headers=headers, timeout=10)
# 		r.raise_for_status()
# 		data = r.json()
# 		items = []
# 		if isinstance(data, dict):
# 			# try common wrappers
# 			items = data.get("sessions") or data.get("data") or []
# 		elif isinstance(data, list):
# 			items = data
# 		if not isinstance(items, list):
# 			return []
# 		sessions = []
# 		for s in items:
# 			if not isinstance(s, dict):
# 				continue
# 			sid = s.get("session_id") or s.get("sessionId") or s.get("id")
# 			label = s.get("title") or s.get("name") or s.get("created_at") or s.get("createdAt") or str(sid)
# 			sessions.append({"id": sid, "label": label, "raw": s})
# 		return sessions
# 	except Exception as e:
# 		# show unobtrusive message in sidebar
# 		try:
# 			st.sidebar.error(f"Could not fetch sessions: {e}")
# 		except Exception:
# 			pass
# 		return []


# def fetch_session_history(session_id: str) -> list:
# 	"""Fetch messages for a specific session id. Returns list of {role,content}.

# 	Returns empty list on failure.
# 	"""
# 	if not session_id:
# 		return []

# 	base = _build_sessions_url()
# 	url = base.rstrip("/") + f"/{session_id}"
# 	headers = {}
# 	if st.session_state.get("token"):
# 		headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
# 	try:
# 		r = requests.get(url, headers=headers, timeout=10)
# 		r.raise_for_status()
# 		data = r.json()
# 		msgs = []
# 		if isinstance(data, dict):
# 			msgs = data.get("messages") or data.get("history") or data.get("chat") or []
# 		elif isinstance(data, list):
# 			msgs = data
# 		if not isinstance(msgs, list):
# 			return []
# 		out = []
# 		for m in msgs:
# 			if isinstance(m, dict):
# 				role = m.get("role") or m.get("sender") or m.get("from")
# 				content = m.get("content") or m.get("text") or m.get("message")
# 				if role and content:
# 					out.append({"role": role, "content": content})
# 		return out
# 	except Exception as e:
# 		try:
# 			st.sidebar.error(f"Could not load session {session_id}: {e}")
# 		except Exception:
# 			pass
# 		return []


# # ------------------
# # Sessions (sidebar)
# # ------------------
# st.sidebar.subheader("Chat Sessions")
# sessions_list = []
# if st.session_state.get("token"):
# 	# cached sessions to avoid re-fetching every rerun
# 	if "_sessions_cache" not in st.session_state:
# 		st.session_state["_sessions_cache"] = []
# 	if st.sidebar.button("Refresh sessions"):
# 		st.session_state["_sessions_cache"] = fetch_sessions()
# 	sessions_list = st.session_state.get("_sessions_cache") or fetch_sessions()
# 	# build options
# 	options = ["New chat"] + [f"{s['label']} ({s['id']})" for s in sessions_list]
# 	selected = st.sidebar.selectbox("Select session to load", options, index=0, key="session_select")
# 	if st.sidebar.button("Load selected session"):
# 		if selected == "New chat":
# 			st.session_state.session_id = None
# 			st.session_state.messages = [
# 				{"role": "assistant", "content": "Hello — I'm the HR Assistant. Ask me about HR docs, policies, or employee info."}
# 			]
# 			st.sidebar.success("New chat started")
# 			safe_rerun()
# 		else:
# 			# find corresponding id
# 			selected_id = None
# 			for s in sessions_list:
# 				label = f"{s['label']} ({s['id']})"
# 				if label == selected:
# 					selected_id = s['id']
# 					break
# 			if selected_id:
# 				msgs = fetch_session_history(selected_id)
# 				if msgs:
# 					st.session_state.messages = msgs
# 					st.session_state.session_id = selected_id
# 					st.sidebar.success(f"Loaded session {selected_id}")
# 				else:
# 					st.sidebar.error("No messages found for this session")
# 				safe_rerun()
# 	st.sidebar.markdown("---")
# else:
# 	st.sidebar.info("Login to see chat sessions")


# def render_chat(messages: List[Dict[str, str]]):
# 	# Use Streamlit's new chat components when available, fallback to markdown
# 	for msg in messages:
# 		role = msg.get("role")
# 		content = msg.get("content")
# 		if hasattr(st, "chat_message"):
# 			# st.chat_message exists in newer Streamlit versions
# 			with st.chat_message("user" if role == "user" else "assistant"):
# 				st.write(content)
# 		else:
# 			if role == "user":
# 				st.markdown(f"**You:** {content}")
# 			else:
# 				st.markdown(f"**Assistant:** {content}")
# 		st.write("---")


# # ------------------
# # Main layout
# # ------------------
# col1, col2 = st.columns([3, 1])

# with col1:
# 	st.subheader("Conversation")
# 	chat_container = st.container()
# 	with chat_container:
# 		render_chat(st.session_state.messages)

# with col2:
# 	st.subheader("Send a message")
# 	with st.form("send_form"):
# 		user_input = st.text_area("Message", key="user_input", placeholder="Type your question here...", height=120)
# 		send_submitted = st.form_submit_button("Send")
# 	if send_submitted:
# 		text = user_input.strip()
# 		if text:
# 			add_message("user", text)
# 			reply = send_to_api(text, session_id=st.session_state.get("session_id"))
# 			add_message("assistant", reply)
# 			# schedule clearing the input on the next run to avoid Streamlit API error
# 			st.session_state.clear_input_next_run = True
# 			safe_rerun()


# # small helper: quick health check
# with st.expander("Backend Health"):
# 	try:
# 		health_url = api_url.replace("/chat", "/health") if "/chat" in api_url else api_url.replace("/employee/chat", "/health")
# 		r = requests.get(health_url, timeout=5)
# 		st.write("Health endpoint response:", r.status_code, r.text)
# 	except Exception:
# 		st.write("No health response detected. Make sure FastAPI runs on the configured URL.")


# st.caption("Frontend: Streamlit. Backend: FastAPI on port 8000. Default endpoint: /employee/chat")



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