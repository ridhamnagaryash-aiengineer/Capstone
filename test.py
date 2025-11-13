import streamlit as st
import requests
from typing import List, Dict


st.set_page_config(page_title="HRMS Chat", page_icon="💬", layout="wide")
st.title("HRMS Chat — HR Assistant")

with st.expander("About"):
	st.write(
		"This is a lightweight Streamlit chat UI that sends user messages to a FastAPI backend running on port 8000.\n\n"
		"The frontend POSTs JSON {\"message\": <text>} to the API URL and expects a JSON response like {\"reply\": <text>}."
	)

# Sidebar settings
st.sidebar.header("Settings")
# Default to the protected employee chat endpoint which requires auth
api_url = st.sidebar.text_input("FastAPI chat URL", value="http://localhost:8000/employee/chat")
st.sidebar.markdown("Ensure FastAPI is running (e.g. `uvicorn main:app --reload --port 8000`) and the `/employee/chat` endpoint exists.")
st.sidebar.caption("API contract: POST JSON {\"message\": string, optional session_id} → returns ChatResponse JSON")


# ------------------
# Authentication UI
# ------------------
if "token" not in st.session_state:
	st.session_state.token = None
if "username" not in st.session_state:
	st.session_state.username = None

st.sidebar.subheader("Authentication")
auth_action = st.sidebar.radio("Action", options=["Login", "Signup", "Logout"], index=0)

auth_base = st.sidebar.empty()
with auth_base.container():
	if auth_action == "Signup":
		st.sidebar.text_input("Full name", key="signup_full_name")
		st.sidebar.text_input("Username", key="signup_username")
		st.sidebar.text_input("Email", key="signup_email")
		st.sidebar.text_input("Grade", key="signup_grade")
		signup_password = st.sidebar.text_input("Password", key="signup_password", type="password")
		if st.sidebar.button("Create account"):
			signup_payload = {
				"email": st.session_state.get("signup_email"),
				"username": st.session_state.get("signup_username"),
				"password": signup_password,
				"full_name": st.session_state.get("signup_full_name"),
				"grade": st.session_state.get("signup_grade"),
			}
			try:
				r = requests.post(api_url.replace("/employee/chat", "/auth/signup"), json=signup_payload, timeout=10)
				r.raise_for_status()
				st.sidebar.success("Account created. Please login.")
			except Exception as e:
				st.sidebar.error(f"Signup failed: {e}")

	elif auth_action == "Login":
		login_email = st.sidebar.text_input("Email", key="login_email")
		login_password = st.sidebar.text_input("Password", key="login_password", type="password")
		if st.sidebar.button("Login"):
			login_url = api_url.replace("/employee/chat", "/auth/login")
			try:
				# OAuth2PasswordRequestForm expects form-encoded 'username' and 'password'
				r = requests.post(login_url, data={"username": login_email, "password": login_password}, timeout=10)
				r.raise_for_status()
				data = r.json()
				token = data.get("access_token") or data.get("token") or data.get("accessToken")
				if token:
					st.session_state.token = token
					st.session_state.username = data.get("username") or login_email
					st.sidebar.success(f"Logged in as {st.session_state.username}")
				else:
					st.sidebar.error("Login response did not contain an access token")
			except Exception as e:
				st.sidebar.error(f"Login failed: {e}")

	else:  # Logout
		if st.sidebar.button("Logout"):
			st.session_state.token = None
			st.session_state.username = None
			st.sidebar.info("Logged out")

	# show current token/user
	if st.session_state.token:
		st.sidebar.markdown(f"**User:** {st.session_state.username}")
		st.sidebar.caption("Token stored in session for Authorization header")
	else:
		st.sidebar.caption("Not authenticated")


def init_state():
	if "messages" not in st.session_state:
		st.session_state.messages = [
			{"role": "assistant", "content": "Hello — I'm the HR Assistant. Ask me about HR docs, policies, or employee info."}
		]


def add_message(role: str, text: str):
	st.session_state.messages.append({"role": role, "content": text})


def send_to_api(message: str, session_id: str = None) -> str:
	payload = {"message": message}
	if session_id:
		payload["session_id"] = session_id
	headers = {}
	if st.session_state.get("token"):
		headers["Authorization"] = f"Bearer {st.session_state.get('token')}"
	try:
		resp = requests.post(api_url, json=payload, headers=headers, timeout=20)
		resp.raise_for_status()
		data = resp.json()
		# employee/chat returns ChatResponse with 'response' key
		if isinstance(data, dict):
			return data.get("response") or data.get("reply") or data.get("answer") or str(data)
		return str(data)
	except Exception as e:
		return f"[error contacting API] {e}"


def render_chat(messages: List[Dict[str, str]]):
	for msg in messages:
		role = msg.get("role")
		content = msg.get("content")
		if role == "user":
			st.markdown(f"**You:** {content}")
		else:
			st.markdown(f"**Assistant:** {content}")
		st.write("---")


init_state()

col1, col2 = st.columns([3, 1])

with col1:
	st.subheader("Conversation")
	render_chat(st.session_state.messages)

with col2:
	st.subheader("Send a message")
	user_input = st.text_area("Message", key="user_input", placeholder="Type your question here...")
	if st.button("Send"):
		text = user_input.strip()
		if text:
			add_message("user", text)
			reply = send_to_api(text)
			add_message("assistant", reply)
			# clear input
			st.session_state.user_input = ""
			st.experimental_rerun()


# small helper: quick health check
with st.expander("Backend Health"):
	try:
		r = requests.get(api_url.replace("/chat", "/health"), timeout=5)
		st.write("Health endpoint response:", r.status_code, r.text)
	except Exception:
		st.write("No health response detected. Make sure FastAPI runs on port 8000.")


st.caption("Frontend: Streamlit. Backend: FastAPI on port 8000. Default endpoint: /chat")

