from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
import threading
import requests
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

tasks = {}


def is_allowed_media_url(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        # Only direct media files are accepted.
        allowed_extensions = (
            ".mp4", ".webm", ".mov", ".m4v",
            ".mp3", ".m4a", ".wav", ".ogg"
        )

        path = parsed.path.lower()
        return path.endswith(allowed_extensions)

    except Exception:
        return False


def download_media(task_id, url):
    try:
        tasks[task_id]["status"] = "processing"

        response = requests.get(
            url,
            stream=True,
            timeout=60,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if not (
            content_type.startswith("video/")
            or content_type.startswith("audio/")
        ):
            raise Exception("The URL does not point to a video or audio file.")

        extension = ".mp4"

        if "audio/" in content_type:
            if "mpeg" in content_type:
                extension = ".mp3"
            elif "mp4" in content_type:
                extension = ".m4a"
            else:
                extension = ".audio"

        elif "webm" in content_type:
            extension = ".webm"
        elif "quicktime" in content_type:
            extension = ".mov"

        filename = f"{task_id}{extension}"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["files"] = [
            {
                "name": filename,
                "link": f"/download/{task_id}"
            }
        ]

        tasks[task_id]["direct_link"] = (
            f"/download/{task_id}"
        )

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@app.route("/api/server_status", methods=["GET"])
def server_status():
    return jsonify({
        "online": True,
        "status": "online"
    })


@app.route("/api/add", methods=["POST"])
def add_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({
            "error": "URL is required"
        }), 400

    if not is_allowed_media_url(url):
        return jsonify({
            "error": (
                "Please provide a direct video/audio file URL "
                "that you are authorized to download."
            )
        }), 400

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

    return jsonify({
        "task_id": task_id
    })


@app.route("/api/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = tasks.get(task_id)

    if not task:
        return jsonify({
            "status": "failed",
            "error": "Task not found"
        }), 404

    return jsonify(task)


@app.route("/download/<task_id>", methods=["GET"])
def download_file(task_id):
    task = tasks.get(task_id)

    if not task or task.get("status") != "completed":
        return jsonify({
            "error": "File is not ready"
        }), 404

    files = task.get("files", [])

    if not files:
        return jsonify({
            "error": "File not found"
        }), 404

    filename = files[0]["name"]
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({
            "error": "File no longer exists"
        }), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename
    )


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "name": "Video Downloader Backend",
        "status": "running"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
                  )
