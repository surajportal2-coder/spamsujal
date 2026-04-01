import asyncio
import uuid
import json
import os
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

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
GROUP_URL = None

# ===================== LOG =====================
def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    logs.append(line)
    if len(logs) > 500:
        logs.pop(0)
    print(line)

# ===================== FINGERPRINT ROTATION =====================
def get_random_fingerprint():
    agents = [
        "Instagram 312.0.0.22.114 Android",
        "Instagram 311.0.0.21.111 Android",
        "Instagram 310.0.0.20.108 Android",
        "Instagram 309.0.0.19.105 Android"
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
    cl.private.headers.update({
        "X-IG-App-ID": "936619743392459",
        "X-IG-Device-ID": uuids["uuid"],
    })

# ===================== ROUTES =====================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/logs')
def get_logs():
    return "<br>".join(logs[-60:])

@app.route('/start', methods=['POST'])
def start_bot():
    global client, is_running, CURRENT_MESSAGES, CURRENT_NC_TITLES, MSG_DELAY, NC_DELAY, GROUP_URL

    data = request.json
    session_json = data.get('session_json', '').strip()

    cl = Client()
    setup_fingerprint(cl)

    try:
        if session_json:
            settings = json.loads(session_json)
            cl.set_settings(settings)
            cl.get_timeline_feed()          # Session valid check
            log("✅ SESSION LOGIN SUCCESSFUL")
        else:
            username = data.get('username')
            password = data.get('password')
            if username and password:
                cl.login(username, password)
                cl.dump_settings("session.json")
                log("✅ NORMAL LOGIN + SESSION SAVED")
            else:
                return jsonify({"error": "Session ya Credentials chahiye"}), 400

        client = cl

        # Frontend se values le
        CURRENT_MESSAGES = [x.strip() for x in data.get('messages', '').split(',') if x.strip()]
        CURRENT_NC_TITLES = [x.strip() for x in data.get('nc_titles', '').split('\n') if x.strip()]
        MSG_DELAY = int(data.get('msg_delay', 25))
        NC_DELAY = int(data.get('nc_delay', 8))
        GROUP_URL = data.get('group_url')

        # Agar frontend khali hai to file se load kar lo (fallback)
        if not CURRENT_MESSAGES and os.path.exists("text.txt"):
            with open("text.txt", "r", encoding="utf-8") as f:
                content = f.read()
                CURRENT_MESSAGES = [x.strip() for x in content.split(',') if x.strip()]

        if not CURRENT_NC_TITLES and os.path.exists("nc.txt"):
            with open("nc.txt", "r", encoding="utf-8") as f:
                CURRENT_NC_TITLES = [x.strip() for x in f if x.strip()]

        is_running = True
        threading.Thread(target=lambda: asyncio.run(bot_main()), daemon=True).start()
        return jsonify({"status": "started"})

    except Exception as e:
        log(f"❌ Login Failed: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/stop')
def stop_bot():
    global is_running
    is_running = False
    return jsonify({"status": "stopped"})

# ===================== MAIN BOT LOGIC (Tera Original Script Wala Logic) =====================
async def bot_main():
    global round_number
    while is_running:
        try:
            log(f"🔄 ROUND {round_number} STARTED")

            threads = await asyncio.to_thread(client.direct_threads, amount=100)
            groups = [t for t in threads if getattr(t, "is_group", False)]

            log(f"📊 {len(groups)} Group Chats Found")

            for index, thread in enumerate(groups, 1):
                if not is_running:
                    break

                gid = thread.id

                # Message Send
                if CURRENT_MESSAGES:
                    msg = CURRENT_MESSAGES[round_number % len(CURRENT_MESSAGES)]
                    try:
                        await asyncio.to_thread(client.direct_send, msg, thread_ids=[gid])
                        log(f"📨 Sent → GC {index}/{len(groups)}")
                    except Exception:
                        log(f"⚠ Message Failed → GC {index}")

                # Name Change (NC)
                if CURRENT_NC_TITLES:
                    new_title = CURRENT_NC_TITLES[round_number % len(CURRENT_NC_TITLES)]
                    try:
                        client.private_request(f"direct_v2/threads/{gid}/update_title/", {"title": new_title})
                        log(f"💠 NC Applied → {new_title}")
                    except:
                        pass

                await asyncio.sleep(MSG_DELAY)

            log(f"✅ ROUND {round_number} COMPLETED")
            round_number += 1
            await asyncio.sleep(90)   # Round ke beech cooldown

        except Exception as e:
            log(f"⚠ Round Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("🌐 SUJAL CONTROL PANEL → http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
