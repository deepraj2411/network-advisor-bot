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

def save_message(chat_id, role, content, metrics
