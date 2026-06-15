import os
import queue
import threading
from flask import Flask, render_template, Response, jsonify, send_from_directory, request
from pubchem_downloader_agent import PubChemBrowserAgent

app = Flask(__name__)

# Directory configuration
DOWNLOAD_DIR = os.path.abspath("pubchem_downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# SSE log queue management
log_clients = []

def agent_log_callback(message):
    for q in log_clients:
        try:
            q.put_nowait(message)
        except queue.Full:
            pass

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/search", methods=["POST"])
def start_search():
    data = request.get_json() or {}
    keyword = data.get("keyword", "").strip()
    count = int(data.get("count", 3))

    if not keyword:
        return jsonify({"success": False, "error": "Keyword is required."}), 400

    # Start the agent in a background thread so it doesn't block the HTTP request
    def run_agent_async():
        agent = PubChemBrowserAgent(download_dir=DOWNLOAD_DIR, log_callback=agent_log_callback)
        agent.log(f"🚀 AI Agent launched in background thread for keyword: '{keyword}' (Count: {count})")
        agent.download_papers(keyword, count)
        agent.log("🏁 AI Agent run completed.")

    threading.Thread(target=run_agent_async, daemon=True).start()
    return jsonify({"success": True, "message": "Search agent started in the background."})

@app.route("/api/logs")
def stream_logs():
    q = queue.Queue(maxsize=100)
    log_clients.append(q)

    def sse_stream():
        yield "data: ⚡ System Console connected. Awaiting agent output...\n\n"
        try:
            while True:
                message = q.get()
                yield f"data: {message}\n\n"
        except GeneratorExit:
            # Client disconnected
            if q in log_clients:
                log_clients.remove(q)

    return Response(sse_stream(), mimetype="text/event-stream")

@app.route("/api/papers")
def get_papers():
    json_path = os.path.join(DOWNLOAD_DIR, "metadata.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(data)
        except Exception as e:
            return jsonify([])
    return jsonify([])

@app.route("/api/download_pdf/<path:filename>")
def download_pdf(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)

@app.route("/api/export/<file_format>")
def export_metadata(file_format):
    if file_format == "csv":
        filename = "metadata.csv"
    elif file_format == "json":
        filename = "metadata.json"
    else:
        return "Invalid format", 400
        
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    return "File not found", 404

if __name__ == "__main__":
    import json  # Required in get_papers
    app.run(host="localhost", port=5000, debug=True)
