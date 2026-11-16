#!/usr/bin/env python3
"""
Instagram Mass Report Bot – Mobile‑Ready, Un‑Ban Friendly
Author : Lucifer
"""

import json
import os
import random
import time
import threading
from datetime import datetime

import requests
import telebot
from telebot import types
from flask import Flask

# ---------- CONFIG ----------
API_KEY  = "8898649047:AAHzMC5R2Vv-iEcIiMGikPdIRaDfKNWrxqI"   # ← YOUR BOT TOKEN
ADMIN_ID = 8741170935                                        # ← YOUR TELEGRAM ID
CHAT_ID  = ADMIN_ID                                          # ← Same as admin

# JSON files – store data locally (Termux will keep them in your home dir)
SESSIONS_FILE = "sessions.json"
USERS_FILE    = "users.json"

# Flask app – for health‑check, optional
app = Flask(__name__)

# ---------- TELEGRAM BOT ----------
try:
    bot = telebot.TeleBot(API_KEY)
except Exception as e:
    print(f"[ERROR] Telebot init failed: {e}")
    exit(1)

# ---------- HELPERS ----------
def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# Session management
def add_session(session_str):
    sessions = load_json(SESSIONS_FILE, [])
    sessions.append({"id": session_str.strip(), "added_at": time.time()})
    save_json(SESSIONS_FILE, sessions)

def delete_session(index):
    sessions = load_json(SESSIONS_FILE, [])
    if 0 <= index < len(sessions):
        sessions.pop(index)
        save_json(SESSIONS_FILE, sessions)
        return True
    return False

def get_sessions(): return load_json(SESSIONS_FILE, [])

# User management
def add_user(uid):
    users = load_json(USERS_FILE, {})
    if str(uid) not in users:
        users[str(uid)] = {"paid": False, "session": None}
        save_json(USERS_FILE, users)

def mark_paid(uid, session_id=None):
    users = load_json(USERS_FILE, {})
    if str(uid) in users:
        users[str(uid)]["paid"] = True
        users[str(uid)]["session"] = session_id
        save_json(USERS_FILE, users)

def reset_user(uid):
    users = load_json(USERS_FILE, {})
    if str(uid) in users:
        users[str(uid)] = {"paid": False, "session": None}
        save_json(USERS_FILE, users)

def get_users(): return load_json(USERS_FILE, {})

# ---------- INSTAGRAM API ----------
WEB_PROFILE_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"
REPORT_URL      = "https://i.instagram.com/api/v1/users/{user_id}/report_user/"

REASON_MAP = {
    "spam": 4,
    "bully_me": 20,
    "scam_fraud": 13,
    "suspicious_contact": 15,
    "threats": 6,
    "hate_exploitation": 7
}

REPORT_DISTRIBUTION = {
    "spam": 5,
    "bully_me": 1,
    "scam_fraud": 2,
    "suspicious_contact": 10,
    "threats": 10,
    "hate_exploitation": 20
}

def generate_device_id(): return str(random.randint(100000000000000, 999999999999999))

def get_user_id(username, session_str):
    headers = {
        "User-Agent": "Instagram 238.0.0.29.115 Android (30/11; 480dpi; 1080x2265; Xiaomi; Redmi Note 8 Pro; whyred; qcom; en_IN)",
        "X-IG-Capability": "3",
        "Cookie": session_str
    }
    try:
        resp = requests.get(f"{WEB_PROFILE_URL}?username={username}", headers=headers, timeout=10)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        data = resp.json()
        if "data" in data and "user" in data["data"]:
            return str(data["data"]["user"]["pk"]), None
        return None, data.get("message", "Unknown error")
    except Exception as e:
        return None, str(e)

def send_report(user_id, reason_code, session_str):
    headers = {
        "User-Agent": "Instagram 238.0.0.29.115 Android (30/11; 480dpi; 1080x2265; Xiaomi; Redmi Note 8 Pro; whyred; qcom; en_IN)",
        "X-IG-App-ID": "936619743392459",
        "X-IG-Capability": "3",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json"
    }
    payload = {
        "reason_id": reason_code,
        "container_module": "feed_timeline",
        "target_user_ids": f"[{user_id}]",
        "action_source": "long_press",
        "device_id": generate_device_id(),
        "ig_sig_key_version": "4"
    }
    url = REPORT_URL.format(user_id=user_id)
    try:
        sid = session_str.split('=')[1]
        resp = requests.post(url, headers=headers, data=payload, cookies={"sessionid": sid}, timeout=10)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        data = resp.json()
        if data.get("status") == "ok":
            return True, "Success"
        else:
            msg = data.get("message", "Unknown")
            if "try again later" in msg.lower():
                return False, "Rate Limited"
            return False, f"API {msg}"
    except Exception as e:
        return False, str(e)

def check_osint(username):
    """Mock Dark‑Web / OSINT check – replace with real API later."""
    return {
        "status": "Checked",
        "info": f"OSINT for @{username}: No major breaches found.",
        "dark_web_score": random.randint(1,10)
    }

# ---------- TELEGRAM HANDLERS ----------
@bot.message_handler(commands=['start'])
def start_handler(msg):
    uid = msg.from_user.id
    if uid == ADMIN_ID:  # Admin panel
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Add Session ID", callback_data="admin_add_session"))
        markup.add(types.InlineKeyboardButton("🗂️ View Sessions", callback_data="admin_view_sessions"))
        markup.add(types.InlineKeyboardButton("👥 View Users", callback_data="admin_view_users"))
        markup.add(types.InlineKeyboardButton("💳 Reset User Payment", callback_data="admin_reset_user"))
        bot.send_message(uid, "🛠️ Admin Panel", reply_markup=markup)
    else:  # Normal user flow
        add_user(uid)
        if get_users().get(str(uid), {}).get("paid"):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 Run Reports", callback_data="run_report"))
            markup.add(types.InlineKeyboardButton("❓ Support", url="https://t.me/YourSupportChannel"))
            bot.send_message(uid, "✅ Payment verified! You can run reports now.", reply_markup=markup)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💰 Pay 799 INR (Fampay/UPI)", callback_data="pay_now"))
            markup.add(types.InlineKeyboardButton("❓ Support", url="https://t.me/YourSupportChannel"))
            bot.send_message(uid, "⚠️ You need to pay 799 INR to use the bot.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    data = call.data

    # ---------- ADMIN ----------
    if data == "admin_add_session":
        bot.send_message(uid, "Send the Session ID string (e.g., sessionid=...; mid=...; csrftoken=...).")
        bot.register_next_step_handler(call.message, handle_add_session)

    elif data == "admin_view_sessions":
        sessions = get_sessions()
        if not sessions:
            bot.send_message(uid, "❌ No sessions added yet.")
        else:
            msg = "**Current Sessions:**\n"
            for idx, s in enumerate(sessions):
                msg += f"{idx+1}. {s['id'][:30]}... (added {datetime.fromtimestamp(s['added_at']).strftime('%Y-%m-%d')})\n"
            msg += "\nTo delete: `/delete_session <index>` (1‑based)."
            bot.send_message(uid, msg)

    elif data == "admin_view_users":
        users = get_users()
        if not users:
            bot.send_message(uid, "❌ No users yet.")
        else:
            msg = "**Users List:**\n"
            for uid_key, u in users.items():
                status = "✅ Paid" if u["paid"] else "❌ Unpaid"
                msg += f"• User {uid_key}: {status}\n"
            bot.send_message(uid, msg)

    elif data == "admin_reset_user":
        bot.send_message(uid, "Send the Telegram User ID to reset payment status.")
        bot.register_next_step_handler(call.message, handle_reset_user)

    # ---------- USER ----------
    elif data == "pay_now":
        add_user(uid)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pay via Fampay", url="https://fampay.in"))
        markup.add(types.InlineKeyboardButton("✅ I Have Paid", callback_data="confirm_payment"))
        bot.send_message(uid, "💰 Pay 799 INR via Fampay/UPI. After paying, click the button below.", reply_markup=markup)

    elif data == "confirm_payment":
        mark_paid(uid, session_id=None)
        bot.send_message(uid, "✅ Payment confirmed! You may now run reports.")

    elif data == "run_report":
        bot.send_message(uid, "Enter the Instagram username (without @):")
        bot.register_next_step_handler(call.message, handle_run_report)

    else:
        bot.send_message(uid, "❓ Unknown command.")

# ---------- STEP HANDLERS ----------
def handle_add_session(msg):
    session_str = msg.text.strip()
    add_session(session_str)
    bot.send_message(msg.chat.id, f"✅ Session added: {session_str[:30]}...")

def handle_reset_user(msg):
    try:
        target_uid = int(msg.text.strip())
        reset_user(target_uid)
        bot.send_message(msg.chat.id, f"✅ Payment reset for user {target_uid}.")
    except Exception:
        bot.send_message(msg.chat.id, "❌ Invalid User ID. Please send a numeric ID.")

def handle_run_report(msg):
    username = msg.text.strip().lstrip("@")
    uid = msg.chat.id
    sessions = get_sessions()
    if not sessions:
        bot.send_message(uid, "❌ No sessions available. Ask admin to add one.")
        return
    session = random.choice(sessions)["id"]

    bot.send_message(uid, f"🚀 Starting mass report for @{username}…")
    ig_user_id, err = get_user_id(username, session)
    if err:
        bot.send_message(uid, f"❌ Error retrieving User ID: {err}")
        return

    # Build report list
    report_list = []
    for rtype, count in REPORT_DISTRIBUTION.items():
        report_list.extend([rtype]*count)
    random.shuffle(report_list)

    total_sent = 0
    for idx, rtype in enumerate(report_list):
        reason_id = REASON_MAP[rtype]
        success, msg = send_report(ig_user_id, reason_id, session)
        if success: total_sent += 1

        # Random jitter 2.5‑4.5 s – keeps us below Instagram limits
        time.sleep(random.uniform(2.5, 4.5))

        # Periodic update
        if (idx+1) % 10 == 0 or idx == len(report_list)-1:
            bot.send_message(uid, f"📊 Progress: {total_sent}/{len(report_list)} reports sent. Last: {msg}")

    # Final summary + mock OSINT
    osint = check_osint(username)
    final = f"🔥 **Report Completed!**\nTotal Reports Sent: {total_sent}/{len(report_list)}\n\n🕵️ *OSINT:* {osint['info']}\nDark Web Score: {osint['dark_web_score']}/10"
    bot.send_message(uid, final)

# ---------- FLASK ROUTES (optional health‑check) ----------
@app.route("/health")
def health(): return "Bot is running!"

# ---------- MAIN ----------
if __name__ == "__main__":
    # Run bot and Flask in separate threads
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
