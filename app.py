from flask import Flask, render_template, request, jsonify
from instagrapi import Client
import threading
import time
import random
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sujal_hawk_final_2025"

state = {"running": False, "sent": 0, "logs": [], "start_time": None}
cfg = {"sessionid": "", "thread_id": 0, "messages": [], "group_name": "", "delay": 25, "cycle": 35, "break_sec": 40}

def log(msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    state["logs"].append(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]

def bomber():
    cl = Client()
    cl.delay_range = [8, 30]
    
    try:
        cl.login_by_sessionid(cfg["sessionid"])
        log("LOGIN SUCCESS — BOMBING STARTED")
    except Exception as e:
        log(f"LOGIN FAILED → {str(e)[:80]}")
        return

    sent_in_cycle = 0
    while state["running"]:
        try:
            msg = random.choice(cfg["messages"])
            cl.direct_send(msg, thread_ids=[cfg["thread_id"]])
            sent_in_cycle += 1
            state["sent"] += 1
            log(f"SENT #{state['sent']} → {msg[:50]}...")

            if sent_in_cycle >= cfg["cycle"]:
                if cfg["group_name"]:
                    new_name = f"{cfg['group_name']} → {datetime.now().strftime('%I:%M:%S %p')}"
                    try:
                        cl.direct_thread_change_title(cfg["thread_id"], new_name)
                        log(f"GROUP NAME CHANGED → {new_name}")
                    except:
                        log("Name change failed")
                log(f"BREAK {cfg['break_sec']} SECONDS")
                time.sleep(cfg["break_sec"])
                sent_in_cycle = 0

            time.sleep(cfg["delay"] + random.uniform(-2, 3))
        except Exception as e:
            log(f"SEND FAILED → {str(e)[:60]}")
            time.sleep(15)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state
    state["running"] = False
    time.sleep(1)

    state = {"running": True, "sent": 0, "logs": ["BOMBING STARTED"], "start_time": time.time()}

    cfg["sessionid"] = request.form["sessionid"].strip()
    cfg["thread_id"] = int(request.form["thread_id"])
    cfg["messages"] = [m.strip() for m in request.form["messages"].split("\n") if m.strip()]
    cfg["group_name"] = request.form.get("group_name", "").strip()
    cfg["delay"] = float(request.form.get("delay", "25"))
    cfg["cycle"] = int(request.form.get("cycle", "35"))
    cfg["break_sec"] = int(request.form.get("break_sec", "40"))

    threading.Thread(target=bomber, daemon=True).start()
    log("THREAD STARTED — BOT IS RUNNING")
    return jsonify({"ok": True})

@app.route("/stop")
def stop():
    state["running"] = False
    log("STOPPED BY USER")
    return jsonify({"ok": True})

@app.route("/status")
def status():
    uptime = "00:00:00"
    if state.get("start_time"):
        t = int(time.time() - state["start_time"])
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"
    return jsonify({
        "running": state["running"],
        "sent": state["sent"],
        "uptime": uptime,
        "logs": state["logs"][-100:]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
