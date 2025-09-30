import json
import os
from datetime import datetime

from flask import Blueprint, Response, jsonify, render_template, request

from src.core.logging_config import add_log_listener, get_log_buffer, remove_log_listener
from src.core.utils import set_active_page

log_bp = Blueprint("logs", __name__)


@log_bp.route("/logs")
def logs():
    """Display the logs page."""
    set_active_page("logs")
    return render_template("logs.html")


@log_bp.route("/api/logs/stream")
def stream_logs():
    """Server-Sent Events endpoint for real-time log streaming."""
    import queue

    def event_stream():
        # Create a queue for this client
        client_queue = queue.Queue(maxsize=100)

        # Send initial logs
        buffer_logs = get_log_buffer(limit=50)
        for log_entry in buffer_logs:
            yield f"data: {json.dumps(log_entry)}\n\n"

        # Create listener for new logs
        def new_log_listener(log_entry):
            try:
                if not client_queue.full():
                    client_queue.put(log_entry)
            except Exception:
                pass

        # Add listener
        add_log_listener(new_log_listener)

        try:
            # Send logs from queue
            while True:
                try:
                    # Try to get a log entry with timeout
                    log_entry = client_queue.get(timeout=10.0)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except queue.Empty:
                    # Send ping to keep connection alive
                    ping_data = {"type": "ping", "timestamp": datetime.now().isoformat()}
                    yield f"data: {json.dumps(ping_data)}\n\n"

        except GeneratorExit:
            # Clean up when client disconnects
            remove_log_listener(new_log_listener)
        finally:
            # Clean up
            remove_log_listener(new_log_listener)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@log_bp.route("/api/logs/history")
def get_log_history():
    """Get historical logs with pagination and filtering."""
    try:
        # Get query parameters
        limit = int(request.args.get("limit", 100))
        level_filter = request.args.get("level", None)
        search_query = request.args.get("search", "").lower()

        # Limit the limit to reasonable bounds
        limit = min(limit, 1000)

        # Get logs from buffer
        logs = get_log_buffer(level_filter=level_filter)

        # Apply search filter if provided
        if search_query:
            logs = [
                log
                for log in logs
                if search_query in log["message"].lower() or search_query in log["logger"].lower()
            ]

        # Apply limit
        logs = logs[-limit:]

        return jsonify(
            {
                "logs": logs,
                "total": len(logs),
                "limit": limit,
                "level_filter": level_filter,
                "search_query": search_query,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@log_bp.route("/api/logs/download")
def download_logs():
    """Download log file."""
    try:
        log_file_path = "/config/logs/stash-manager.log"

        if not os.path.exists(log_file_path):
            return jsonify({"error": "Log file not found"}), 404

        def generate():
            with open(log_file_path, "r", encoding="utf-8") as f:
                while True:
                    data = f.read(4096)
                    if not data:
                        break
                    yield data

        response = Response(generate(), mimetype="text/plain")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=stash-manager-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@log_bp.route("/api/logs/clear-buffer")
def clear_buffer():
    """Clear the in-memory log buffer (admin function)."""
    try:
        from src.core.logging_config import _log_buffer, _log_buffer_lock

        with _log_buffer_lock:
            _log_buffer.clear()

        return jsonify({"success": True, "message": "Log buffer cleared"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
