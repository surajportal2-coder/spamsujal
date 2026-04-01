import asyncio
import uuid
import json
import os
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from instagrapi import Client

app = Flask(__name__)

# ===================== GLOBAL =====================
client = None
is_running = False
logs = []
round_number = 1

CURRENT_MESSAGES = []
CURRENT_NC_TITLES = []
MSG_DELAY = 25
NC_DELAY = 8

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    logs.append(line)
    if len(logs) > 500:
        logs.pop(0)
    print(line)

def get_random_fingerprint():
    agents = [
        "Instagram 312.0.0.22.114 Android",
        "Instagram 311.0.0.21.111 Android",
        "Instagram 310.0.0.20.108 Android"
    ]
    return agents[round_number % len(agents)]

def setup_fingerprint(cl):
    cl.set_user_agent(get_random_fingerprint())
    uuids = {
        "phone_id": str(uuid.uuid4()),
        "uuid": str(uuid.uuid4()),
        "client_session_id": str(uuid.uuid4()),
        "advertising_id": str(uuid.uuid4()),
        "device_id": "android-" + uuid.uuid4().hex[:16]
    }
    cl.set_uuids(uuids)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/logs')
def get_logs():
    return "<br>".join(logs[-60:])

@app.route('/start', methods=['POST'])
def start_bot():
    global client, is_running, CURRENT_MESSAGES, CURRENT_NC_TITLES, MSG_DELAY, NC_DELAY

    data = request.json

    cl = Client()
    setup_fingerprint(cl)

    try:
        # === OPTION 1: Full session.json ===
        if data.get('session_json'):
            settings = json.loads(data.get('session_json'))
            cl.set_settings(settings)
            log("✅ Full Session JSON Loaded")

        # === OPTION 2: Simple Session ID ===
        elif data.get('sessionid'):
            sessionid = data.get('sessionid').strip()
            ds_user_id = data.get('ds_user_id', '').strip()
            
            cl.login_by_sessionid(sessionid)
            log("✅ Login Successful using Session ID")
            
            if ds_user_id:
                cl.set_user_id(ds_user_id)

        # === OPTION 3: Normal Username + Password ===
        else:
            username = data.get('username')
            password = data.get('password')
            if username and password:
                cl.login(username, password)
                cl.dump_settings("session.json")
                log("✅ Normal Login + Session Saved")
            else:
                return jsonify({"error": "Session ID, session.json ya Username/Password do"}), 400

        client = cl

        # Messages aur NC Titles
        CURRENT_MESSAGES = [x.strip() for x in data.get('messages', '').split(',') if x.strip()]
        CURRENT_NC_TITLES = [x.strip() for x in data.get('nc_titles', '').split('\n') if x.strip()]
        MSG_DELAY = int(data.get('msg_delay', 25))
        NC_DELAY = int(data.get('nc_delay', 8))

        is_running = True
        threading.Thread(target=lambda: asyncio.run(bot_main()), daemon=True).start()
        
        return jsonify({"status": "started", "message": "Login Successful"})

    except Exception as e:
        log(f"❌ Login Failed: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/stop')
def stop_bot():
    global is_running
    is_running = False
    return jsonify({"status": "stopped"})

async def bot_main():
    global round_number
    while is_running:
        try:
            log(f"🔄 ROUND {round_number} STARTED")
            threads = await asyncio.to_thread(client.direct_threads, amount=100)
            groups = [t for t in threads if getattr(t, "is_group", False)]

            for index, thread in enumerate(groups, 1):
                if not is_running: break

                gid = thread.id

                # Message Send
                if CURRENT_MESSAGES:
                    msg = CURRENT_MESSAGES[round_number % len(CURRENT_MESSAGES)]
                    try:
                        await asyncio.to_thread(client.direct_send, msg, thread_ids=[gid])
                        log(f"📨 Sent → GC {index}")
                    except:
                        log(f"⚠ Message Failed → GC {index}")

                # Name Change
                if CURRENT_NC_TITLES:
                    title = CURRENT_NC_TITLES[round_number % len(CURRENT_NC_TITLES)]
                    try:
                        client.private_request(f"direct_v2/threads/{gid}/update_title/", {"title": title})
                        log(f"💠 NC → {title}")
                    except:
                        pass

                await asyncio.sleep(MSG_DELAY)

            round_number += 1
            await asyncio.sleep(90)

        except Exception as e:
            log(f"⚠ Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("🌐 SUJAL CONTROL PANEL → http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000)
