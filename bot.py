import os
import time
import sqlite3
import hashlib
import secrets
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from groq import Groq

# ----------------- DATABASE SETUP -----------------
DB_FILE = "network_advisor.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT,
                    full_name TEXT,
                    session_token TEXT
                )''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN session_token TEXT")
    except sqlite3.OperationalError:
        pass 
        
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    chat_id TEXT PRIMARY KEY,
                    username TEXT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    role TEXT,
                    content TEXT,
                    metrics TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash, full_name FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_pass(password):
        return row[1]
    return None

def create_user(username, password, full_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO users VALUES (?, ?, ?, NULL)", (username, hash_pass(password), full_name))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def update_user(username, new_name, new_pass=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if new_pass:
        c.execute("UPDATE users SET full_name = ?, password_hash = ? WHERE username = ?", (new_name, hash_pass(new_pass), username))
    else:
        c.execute("UPDATE users SET full_name = ? WHERE username = ?", (new_name, username))
    conn.commit()
    conn.close()

def delete_user_account(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id IN (SELECT chat_id FROM chats WHERE username = ?)", (username,))
    c.execute("DELETE FROM chats WHERE username = ?", (username,))
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_user_chats(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, title FROM chats WHERE username = ? ORDER BY created_at DESC", (username,))
    chats = c.fetchall()
    conn.close()
    return chats

def create_new_chat(username, title="New Consultation"):
    chat_id = f"chat_{int(time.time()*1000)}"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO chats (chat_id, username, title) VALUES (?, ?, ?)", (chat_id, username, title))
    conn.commit()
    conn.close()
    return chat_id

def update_chat_title(chat_id, new_title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE chats SET title = ? WHERE chat_id = ?", (new_title, chat_id))
    conn.commit()
    conn.close()

def delete_chat(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def save_message(chat_id, role, content, metrics=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (chat_id, role, content, metrics) VALUES (?, ?, ?, ?)", (chat_id, role, content, metrics))
    conn.commit()
    conn.close()

def get_chat_messages(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role, content, metrics FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    msgs = c.fetchall()
    conn.close()
    return [{"role": r, "content": ct, "metrics": m} for r, ct, m in msgs]

# --- SECURE SESSION FUNCTIONS ---
def create_session(username):
    token = secrets.token_hex(16) 
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET session_token = ? WHERE username = ?", (token, username))
    conn.commit()
    conn.close()
    return token

def verify_session(token):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, full_name FROM users WHERE session_token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

def destroy_session(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET session_token = NULL WHERE username = ?", (username,))
    conn.commit()
    conn.close()

init_db()

# ----------------- APP CONFIG -----------------
st.set_page_config(page_title="Network Advisor", page_icon="📡", layout="wide")

# ----------------- SECURE URL PARAMETER LOGIN -----------------
saved_token = st.query_params.get("session")

if "logged_in" not in st.session_state:
    if saved_token:
        u, fname = verify_session(saved_token)
        if u:
            st.session_state.logged_in = True
            st.session_state.username = u
            st.session_state.full_name = fname
            st.session_state.is_guest = False
            user_chats = get_user_chats(u)
            st.session_state.current_chat_id = user_chats[0][0] if user_chats else create_new_chat(u)
        else:
            st.query_params.clear()
            st.session_state.logged_in = False
            st.session_state.username = None
    else:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.full_name = None
        st.session_state.is_guest = False
        st.session_state.current_chat_id = None

# ----------------- LOGIN / AUTH SCREEN -----------------
if not st.session_state.get("logged_in", False):
    st.session_state.setdefault("auth_mode", "login")

    # Clean, responsive sign-in layout using native Streamlit controls.
    st.markdown("""
    <style>
    .block-container {
        max-width: 980px;
        padding-top: clamp(2rem, 7vh, 4.5rem);
        padding-bottom: 2.5rem;
    }
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 50% 0%, rgba(75, 91, 180, 0.18), transparent 42%),
            var(--background-color);
    }
    [data-testid="stForm"] {
        border: 1px solid rgba(140, 150, 175, 0.24);
        border-radius: 1rem;
        padding: 1.25rem 1.35rem 1rem;
        background: rgba(255, 255, 255, 0.025);
    }
    [data-testid="stForm"] input {
        min-height: 2.8rem;
        border-radius: 0.65rem;
    }
    [data-testid="stForm"] button[kind="primary"],
    [data-testid="stButton"] button {
        min-height: 2.9rem;
        border-radius: 0.65rem;
        font-weight: 600;
    }
    .auth-divider {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin: 1.1rem 0;
        color: rgba(180, 185, 200, 0.8);
        font-size: 0.9rem;
    }
    .auth-divider::before, .auth-divider::after {
        content: "";
        flex: 1;
        border-top: 1px solid rgba(140, 150, 175, 0.28);
    }
    footer, #MainMenu { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2.4, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; margin: 0 auto 1.5rem;">
          <h1 style="margin:0 0 0.45rem; font-size:2rem;">📡 Network Advisor</h1>
          <p style="margin:0; opacity:0.78; font-size:1rem;">
            AI-powered network troubleshooting
          </p>
          <p style="margin:0.55rem 0 0; opacity:0.62; font-size:0.88rem;">
            Diagnose connectivity issues and explore practical next steps.
          </p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.auth_mode == "login":
            st.markdown("**Sign in**")
            with st.form("login_form"):
                u = st.text_input("Username", placeholder="Enter your username")
                p = st.text_input("Password", type="password", placeholder="Enter your password")
                submit_login = st.form_submit_button("Sign in", type="primary", use_container_width=True)

                if submit_login:
                    if not u.strip() or not p:
                        st.warning("Enter both your username and password.")
                    else:
                        fname = verify_user(u.strip(), p)
                        if fname:
                            token = create_session(u.strip())
                            st.query_params["session"] = token

                            st.session_state.logged_in = True
                            st.session_state.username = u.strip()
                            st.session_state.full_name = fname
                            st.session_state.is_guest = False
                            user_chats = get_user_chats(u.strip())
                            st.session_state.current_chat_id = user_chats[0][0] if user_chats else create_new_chat(u.strip())
                            st.rerun()
                        else:
                            st.error("We couldn't log you in with those details. Check your username and password and try again.")

            st.markdown('<div class="auth-divider"><span>or</span></div>', unsafe_allow_html=True)
            if st.button("Continue as guest", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.username = "guest_user"
                st.session_state.full_name = "Guest User"
                st.session_state.is_guest = True
                st.session_state.guest_messages = []
                st.rerun()

            st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
            st.caption("New to Network Advisor?")
            if st.button("Create account", use_container_width=True):
                st.session_state.auth_mode = "signup"
                st.rerun()
        else:
            st.markdown("**Create your account**")
            st.caption("Save your network consultation history in an account.")
            with st.form("signup_form"):
                nu = st.text_input("Username", placeholder="Choose a username")
                nf = st.text_input("Full name", placeholder="How should we address you?")
                np = st.text_input("Password", type="password", placeholder="Create a password")
                submit_signup = st.form_submit_button("Create account", type="primary", use_container_width=True)

                if submit_signup:
                    nu, nf = nu.strip(), nf.strip()
                    if nu and np and nf:
                        if create_user(nu, np, nf):
                            st.success("Account created. You can now sign in.")
                            st.session_state.auth_mode = "login"
                        else:
                            st.error("That username is already in use. Choose another one.")
                    else:
                        st.warning("Complete all three fields to create your account.")

            if st.button("Back to sign in", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()

        st.markdown("""
        <hr style="margin:2rem 0 0.8rem; opacity:0.25;">
        <div style="text-align:center; font-size:0.78rem; opacity:0.62;">
          Network diagnostics and AI-assisted troubleshooting
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# ----------------- CLEAN UI SETUP -----------------
st.markdown("""
<style>
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)


# ----------------- MAIN CHAT INTERFACE -----------------
api_key = os.environ.get("GROQ_API_KEY")

# --- EXPERT MODES DICTIONARY ---
ROLE_PROMPTS = {
    "Network Engineer": "You are an expert IT & Network Support Engineer. Focus on routing protocols (OSPF, BGP), switching, TCP/IP, and enterprise network diagnostics.",
    "Cybersecurity Analyst": "You are an elite Cybersecurity Analyst. Focus on firewalls, threat hunting, packet analysis, IPS/IDS, and zero-trust architecture.",
    "Cloud Architect": "You are a Cloud Network Architect. Focus on AWS/Azure VPCs, cloud transit gateways, SDN troubleshooting, and hybrid cloud connectivity."
}

with st.sidebar:
    avatar_seed = st.session_state.username if st.session_state.username else "Guest"
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 20px; margin-top: 10px;">
        <img src="https://api.dicebear.com/7.x/bottts/svg?seed={avatar_seed}" style="border-radius: 50%; width: 45px; height: 45px; margin-right: 12px; border: 2px solid #ff4b4b;">
        <h3 style="margin: 0; font-size: 18px;">Welcome, {st.session_state.full_name}</h3>
    </div>
    <hr style="margin-top: 0px;">
    """, unsafe_allow_html=True)
    
    if not api_key:
        api_key = st.text_input("Groq API Key:", type="password")
        if not api_key:
            st.warning("Please provide a Groq API key to proceed.")
            
    st.divider()

    if not st.session_state.is_guest:
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.current_chat_id = create_new_chat(st.session_state.username)
            st.rerun()
            
        st.write("📂 **Recent Sessions**")
        chats = get_user_chats(st.session_state.username)
        for c_id, c_title in chats:
            col_a, col_b = st.columns([4, 1])
            is_active = (c_id == st.session_state.current_chat_id)
            btn_label = f"💬 {'▶ ' if is_active else ''}{c_title[:18]}"
            if col_a.button(btn_label, key=c_id, use_container_width=True):
                st.session_state.current_chat_id = c_id
                st.rerun()
                
        # --- CHAT MANAGEMENT (RENAME, DELETE, EXPORT) ---
        if st.session_state.current_chat_id:
            with st.expander("🛠️ Manage Current Chat"):
                # Export functionality
                chat_msgs = get_chat_messages(st.session_state.current_chat_id)
                export_str = f"--- Chat Export: {st.session_state.current_chat_id} ---\n\n"
                for m in chat_msgs:
                    export_str += f"[{m['role'].upper()}]\n{m['content']}\n\n"
                
                st.download_button(
                    label="📄 Download Export (.txt)",
                    data=export_str,
                    file_name=f"{st.session_state.current_chat_id}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
                
                # Rename functionality
                new_chat_name = st.text_input("Rename Chat", placeholder="New name...")
                if st.button("Save Name", use_container_width=True):
                    if new_chat_name:
                        update_chat_title(st.session_state.current_chat_id, new_chat_name)
                        st.rerun()
                        
                # Delete functionality
                if st.button("🗑️ Delete Chat", type="primary", use_container_width=True):
                    delete_chat(st.session_state.current_chat_id)
                    st.session_state.current_chat_id = None
                    st.rerun()
                    
    else:
        st.caption("Guest Session (Single volatile history)")

    st.divider()

    with st.expander("⚙️ Account Settings"):
        if not st.session_state.is_guest:
            new_fname = st.text_input("Update Name", value=st.session_state.full_name)
            new_pwd = st.text_input("New Password (optional)", type="password")
            if st.button("Save Profile"):
                update_user(st.session_state.username, new_fname, new_pwd)
                st.session_state.full_name = new_fname
                st.success("Profile updated!")
                st.rerun()
            
            st.divider()
            if st.button("🗑️ Delete Account", type="primary"):
                destroy_session(st.session_state.username) 
                st.query_params.clear()
                delete_user_account(st.session_state.username)
                st.session_state.logged_in = False
                st.session_state.username = None
                st.rerun()
        else:
            st.write("Guest users have no stored account data.")

    if st.button("🚪 Log Out", use_container_width=True):
        if not st.session_state.is_guest:
            destroy_session(st.session_state.username) 
        st.query_params.clear()
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()

if not api_key:
    st.info("Enter your Groq API Key in the left sidebar to activate the AI reasoning pipeline.")
    st.stop()

client = Groq(api_key=api_key)

# --- MAIN CHAT HEADER AND ROLE SWITCHER ---
head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    st.markdown("<h2 style='text-align: left; margin-top: -20px;'>📡 Network Advisor</h2>", unsafe_allow_html=True)
    st.caption("Network diagnostics and multi-vendor troubleshooting")
with head_col2:
    selected_role = st.selectbox("🎭 Expert Mode", list(ROLE_PROMPTS.keys()), label_visibility="collapsed")

# Dynamic System Prompt based on selected role
SYSTEM_PROMPT = (
    ROLE_PROMPTS[selected_role] +
    " STRICT INSTRUCTION: You must ONLY answer questions related to networking, IT infrastructure, servers, and cybersecurity. "
    "If a user asks about unrelated topics (like room decor, smartphones, movies, general knowledge, etc.), clearly and politely decline by stating that you are a Network Advisor and cannot help with non-IT queries."
)

if st.session_state.is_guest:
    messages = st.session_state.guest_messages
else:
    messages = get_chat_messages(st.session_state.current_chat_id) if st.session_state.current_chat_id else []


if not messages:
    st.markdown("""
    <div style="max-width:760px; margin:3.5rem auto 1.4rem; text-align:center;">
      <h3 style="margin-bottom:0.45rem;">What can we troubleshoot?</h3>
      <p style="opacity:0.72; margin:0;">
        Ask a network question, describe a problem, or attach a configuration or log.
      </p>
    </div>
    """, unsafe_allow_html=True)
    prompt_col1, prompt_col2 = st.columns(2)
    quick_prompts = [
        ("🌐 Slow connection", "My Wi-Fi is connected, but webpages load slowly. What should I check first?"),
        ("📉 Packet loss", "How can I troubleshoot packet loss to a remote server?"),
        ("🔌 Intermittent outage", "What information should I collect to investigate intermittent network outages?"),
        ("🛡️ Review a configuration", "Help me review an attached network configuration for common issues."),
    ]
    for index, (label, prompt_text) in enumerate(quick_prompts):
        prompt_column = prompt_col1 if index % 2 == 0 else prompt_col2
        with prompt_column:
            if st.button(label, key=f"quick_prompt_{index}", use_container_width=True):
                st.session_state.queued_prompt = prompt_text
                st.rerun()

for m in messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("metrics"):
            st.caption(m["metrics"])

file_context = ""
with st.popover("📎 Attach File"):
    uploaded_file = st.file_uploader("Upload Network Config/Log", type=["txt", "log", "conf", "csv"], label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode("utf-8")
            file_context = f"\n\n[ATTACHED FILE CONTENT ({uploaded_file.name})]:\n```\n{file_content}\n```"
            st.success(f"Attached: {uploaded_file.name}")
        except Exception as e:
            st.error("Failed to parse file text.")

chat_input_prompt = st.chat_input("Ask a network question or describe the anomaly...")
queued_prompt = st.session_state.pop("queued_prompt", None)
prompt = queued_prompt or chat_input_prompt

if prompt:
    # Edge case: All chats deleted but user types something
    if not st.session_state.is_guest and not st.session_state.current_chat_id:
        st.session_state.current_chat_id = create_new_chat(st.session_state.username)
        messages = []

    combined_query = prompt + file_context
    
    if not st.session_state.is_guest and len(messages) == 0:
        new_title = prompt[:25] + "..." if len(prompt) > 25 else prompt
        try:
            update_chat_title(st.session_state.current_chat_id, new_title)
        except Exception:
            pass
            
    if st.session_state.is_guest:
        st.session_state.guest_messages.append({"role": "user", "content": combined_query, "metrics": ""})
    else:
        save_message(st.session_state.current_chat_id, "user", combined_query, "")
    
    with st.chat_message("user"):
        st.markdown(combined_query)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        start_time = time.time()
        
        try:
            conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in (st.session_state.guest_messages if st.session_state.is_guest else get_chat_messages(st.session_state.current_chat_id)):
                conversation_history.append({"role": msg["role"], "content": msg["content"]})
            
            response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=conversation_history,
                temperature=0.2,
                max_tokens=2048,
                stream=True
            )

            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                message_placeholder.markdown(full_response + "▌")
                
            end_time = time.time()
            latency_ms = round((end_time - start_time) * 1000, 2)
            metrics_info = f"⚡ **Inference Latency:** {latency_ms} ms | **Engine:** Groq LPU"
            
            message_placeholder.markdown(full_response)
            st.caption(metrics_info)

            if st.session_state.is_guest:
                st.session_state.guest_messages.append({"role": "assistant", "content": full_response, "metrics": metrics_info})
            else:
                save_message(st.session_state.current_chat_id, "assistant", full_response, metrics_info)

        except Exception as e:
            st.error(f"Inference Error: {str(e)}")
