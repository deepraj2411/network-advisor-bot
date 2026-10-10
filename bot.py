import os
import time
import sqlite3
import hashlib
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from groq import Groq

# ----------------- DATABASE SETUP -----------------
DB_FILE = "network_advisor.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT,
                    full_name TEXT
                )''')
    # Chats Table
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    chat_id TEXT PRIMARY KEY,
                    username TEXT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    # Messages Table
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
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hash_pass(password), full_name))
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

init_db()

# ----------------- APP CONFIG -----------------
st.set_page_config(page_title="Network Advisor", page_icon="📡", layout="wide")

# Session state initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.full_name = None
    st.session_state.is_guest = False
    st.session_state.current_chat_id = None

# ----------------- LOGIN / AUTH SCREEN -----------------
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>📡 Network Advisor <span style='font-size: 18px; font-weight: normal; color: #888888;'>AI-powered</span></h2>", unsafe_allow_html=True)
        st.caption("<p style='text-align: center;'>Enterprise LPU Diagnostic & Triage Console</p>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["🔑 Login", "📝 Sign Up", "👤 Guest Access"])
        
        with tab1:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Password", type="password", key="login_p")
            if st.button("Log In", use_container_width=True):
                fname = verify_user(u, p)
                if fname:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.full_name = fname
                    st.session_state.is_guest = False
                    user_chats = get_user_chats(u)
                    st.session_state.current_chat_id = user_chats[0][0] if user_chats else create_new_chat(u)
                    st.rerun()
                else:
                    st.error("Invalid username or password")
                    
        with tab2:
            nu = st.text_input("Choose Username", key="reg_u")
            nf = st.text_input("Full Name", key="reg_f")
            np = st.text_input("Create Password", type="password", key="reg_p")
            if st.button("Create Account", use_container_width=True):
                if nu and np and nf:
                    if create_user(nu, np, nf):
                        st.success("Account created successfully! Please log in.")
                    else:
                        st.error("Username already exists!")
                else:
                    st.warning("All fields are required.")
                    
        with tab3:
            st.info("Guest mode allows quick troubleshooting. Chat data will be temporary during session.")
            if st.button("Continue as Guest User", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.username = "guest_user"
                st.session_state.full_name = "Guest User"
                st.session_state.is_guest = True
                st.session_state.guest_messages = []
                st.rerun()
    st.stop()


# ----------------- HACKY CSS INJECTIONS -----------------
avatar_seed = st.session_state.username if st.session_state.username else "Guest"
st.markdown(f"""
<style>
/* HIDE STREAMLIT BRANDING & FOOTER TO PREVENT CUT-OFF */
footer {{ visibility: hidden !important; }}
header {{ visibility: hidden !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}

/* FLOATING CIRCULAR AVATAR IN TOP LEFT */
.custom-avatar {{
    position: fixed;
    top: 15px;
    left: 15px;
    z-index: 999999;
    width: 45px;
    height: 45px;
    border-radius: 50%;
    border: 2px solid #ff4b4b;
    background-image: url('https://api.dicebear.com/7.x/bottts/svg?seed={avatar_seed}');
    background-size: cover;
    pointer-events: none;
}}

/* FIX CHAT INPUT CUT-OFF AND MAKE SPACE FOR LEFT BUTTON */
div[data-testid="stChatInput"] {{
    padding-left: 65px !important;
    padding-bottom: 20px !important; /* Lifts input up slightly */
}}

/* FORCE POPOVER TO LEFT OF CHAT BOX */
div[data-testid="stPopover"] {{
    position: fixed !important;
    bottom: 35px !important; /* Aligns with the lifted chat input */
    left: 20px !important;
    z-index: 999999 !important;
}}

div[data-testid="stPopover"] > button {{
    border-radius: 50% !important;
    width: 45px !important;
    height: 45px !important;
    padding: 0 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    border: 1px solid #444 !important;
}}
</style>
<div class="custom-avatar"></div>
""", unsafe_allow_html=True)


# ----------------- MAIN CHAT INTERFACE -----------------
api_key = os.environ.get("GROQ_API_KEY")

with st.sidebar:
    st.markdown(f"<h3 style='margin-top: 20px; font-size: 18px;'>Welcome, {st.session_state.full_name}</h3><hr style='margin-top: 0px;'>", unsafe_allow_html=True)
    
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
                delete_user_account(st.session_state.username)
                st.session_state.logged_in = False
                st.session_state.username = None
                st.rerun()
        else:
            st.write("Guest users have no stored account data.")

    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()

if not api_key:
    st.info("Enter your Groq API Key in the left sidebar to activate the AI reasoning pipeline.")
    st.stop()

client = Groq(api_key=api_key)

SYSTEM_PROMPT = (
    "You are an expert IT & Network Support Engineer. "
    "Provide concise, technically accurate solutions, command-line triage steps, and RFC-compliant diagnostic guidance."
)

if st.session_state.is_guest:
    messages = st.session_state.guest_messages
else:
    messages = get_chat_messages(st.session_state.current_chat_id)

st.markdown("<h2 style='text-align: left; margin-top: -40px;'>📡 Network Advisor <span style='font-size: 16px; font-weight: normal; color: #888888;'>AI-powered</span></h2>", unsafe_allow_html=True)
st.caption("Deterministic LPU Acceleration | OSPF, BGP, TCP & Multi-Vendor Diagnostics")

for m in messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("metrics"):
            st.caption(m["metrics"])


# File Uploader (Moved to bottom left via CSS hack)
file_context = ""
with st.popover("📎"):
    uploaded_file = st.file_uploader("Upload Network Config/Log", type=["txt", "log", "conf", "csv"], label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode("utf-8")
            file_context = f"\n\n[ATTACHED FILE CONTENT ({uploaded_file.name})]:\n```\n{file_content}\n```"
            st.success(f"Attached: {uploaded_file.name}")
        except Exception as e:
            st.error("Failed to parse file text.")


if prompt := st.chat_input("Ask a network question or describe the anomaly..."):
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
