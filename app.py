import os
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

tasks = {}

def download_media(task_id, url):
    try:
        tasks[task_id]["status"] = "processing"
        
        output_template = os.path.join(DOWNLOAD_DIR, f"{task_id}.%(ext)s")
        
        # FFmpeg ছাড়াই যেন সেরা সিঙ্গেল ফাইল ডাউনলোড হতে পারে, তাই ফরম্যাট পরিবর্তন করা হয়েছে
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            filename = f"{task_id}.{ext}"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            
            # যদি এক্সটেনশন অন্য কিছু হয় কিন্তু ফাইল থাকে
            if not os.path.exists(filepath):
                # ডিরেক্টরি চেক করে ফাইল খুঁজে বের করা
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(task_id):
                        filename = f
                        filepath = os.path.join(DOWNLOAD_DIR, filename)
                        break

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["files"] = [
            {
                "name": filename,
                "link": f"/download/{task_id}"
            }
        ]
        tasks[task_id]["direct_link"] = f"/download/{task_id}"

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.route("/api/server_status", methods=["GET"])
def server_status():
    return jsonify({"online": True, "status": "online"})

@app.route("/api/add", methods=["POST"])
def add_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "files": [],
        "direct_link": None
    }

    thread = threading.Thread(
        target=download_media,
        args=(task_id, url),
        daemon=True
    )
    thread.start()

    return jsonify({"task_id": task_id})

@app.route("/api/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"status": "failed", "error": "Task not found"}), 404
    return jsonify(task)

@app.route("/download/<task_id>", methods=["GET"])
def download_file(task_id):
    task = tasks.get(task_id)
    if not task or task.get("status") != "completed":
        return jsonify({"error": "File is not ready"}), 404

    files = task.get("files", [])
    if not files:
        return jsonify({"error": "File not found"}), 404

    filename = files[0]["name"]
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "File no longer exists"}), 404

    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"name": "Video Downloader Backend", "status": "running"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
