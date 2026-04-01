import asyncio
import uuid
import json
import os
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from instagrapi import Client

app = Flask(__name__)

client = None
is_running = False
logs = []
round_number = 1

CURRENT_MESSAGES = []
CURRENT_NC_TITLES = []
MSG_DELAY = 25
NC_DELAY = 8
TARGET_THREAD_ID = None

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    logs.append(line)
    if len(logs) > 500:
        logs.pop(0)
    print(line)

def get_random_fingerprint():
    agents = ["Instagram 312.0.0.22.114 Android", "Instagram 311.0.0.21.111 Android", "Instagram 310.0.0.20.108 Android"]
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

# ===================== PEHLI BAAR LOGIN + AUTO SAVE =====================
@app.route('/first_login', methods=['POST'])
def first_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    thread_id = data.get('thread_id', '').strip()

    cl = Client()
    setup_fingerprint(cl)

    try:
        cl.login(username, password)
        cl.dump_settings("session.json")
        
        with open("session.json", "r", encoding="utf-8") as f:
            session_content = f.read()
        
        log("✅ LOGIN SUCCESSFUL")
        log("📁 session.json automatically saved on server")
        log("🔽 Pura Session JSON neeche copy kar lo:")
        log(session_content)
        
        global TARGET_THREAD_ID
        TARGET_THREAD_ID = thread_id
        
        return jsonify({"status": "success", "message": "Session saved successfully"})
        
    except Exception as e:
        log(f"❌ Login Failed: {e}")
        return jsonify({"error": str(e)}), 400

# ===================== NORMAL START =====================
@app.route('/start', methods=['POST'])
def start_bot():
    global client, is_running, CURRENT_MESSAGES, CURRENT_NC_TITLES, MSG_DELAY, NC_DELAY, TARGET_THREAD_ID

    data = request.json
    session_json = data.get('session_json', '').strip()

    cl = Client()
    setup_fingerprint(cl)

    try:
        if session_json:
            # Agar user ne pura cookies array paste kiya hai
            cookies = json.loads(session_json)
            cookie_dict = {c['name']: c['value'] for c in cookies}
            sessionid = cookie_dict.get('sessionid')
            ds_user_id = cookie_dict.get('ds_user_id')
            
            if sessionid:
                cl.login_by_sessionid(sessionid)
                if ds_user_id:
                    cl.set_user_id(ds_user_id)
                log("✅ Login Successful using pasted session.json (cookies array)")
            else:
                return jsonify({"error": "Session ID nahi mila"}), 400
        elif os.path.exists("session.json"):
            cl.load_settings("session.json")
            log("✅ Automatically loaded saved session.json")
        else:
            return jsonify({"error": "Pehle First Time Login karo"}), 400

        client = cl

        CURRENT_MESSAGES = [x.strip() for x in data.get('messages', '').split(',') if x.strip()]
        CURRENT_NC_TITLES = [x.strip() for x in data.get('nc_titles', '').split('\n') if x.strip()]
        MSG_DELAY = int(data.get('msg_delay', 25))
        NC_DELAY = int(data.get('nc_delay', 8))
        TARGET_THREAD_ID = data.get('thread_id', '').strip()

        is_running = True
        threading.Thread(target=lambda: asyncio.run(bot_main()), daemon=True).start()
        return jsonify({"status": "started"})

    except Exception as e:
        log(f"❌ Error: {e}")
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

            if TARGET_THREAD_ID:
                log(f"🎯 Targeting Specific Group → {TARGET_THREAD_ID}")
                groups = [{"id": TARGET_THREAD_ID}]
            else:
                threads = await asyncio.to_thread(client.direct_threads, amount=100)
                groups = [t for t in threads if getattr(t, "is_group", False)]

            for index, thread in enumerate(groups, 1):
                if not is_running: break
                gid = thread["id"] if isinstance(thread, dict) else thread.id

                if CURRENT_MESSAGES:
                    msg = CURRENT_MESSAGES[round_number % len(CURRENT_MESSAGES)]
                    try:
                        await asyncio.to_thread(client.direct_send, msg, thread_ids=[gid])
                        log(f"📨 Sent → GC {index}")
                    except:
                        log(f"⚠ Send Failed → GC {index}")

                if CURRENT_NC_TITLES:
                    title = CURRENT_NC_TITLES[round_number % len(CURRENT_NC_TITLES)]
                    try:
                        client.private_request(f"direct_v2/threads/{gid}/update_title/", {"title": title})
                        log(f"💠 NC Applied → {title}")
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
