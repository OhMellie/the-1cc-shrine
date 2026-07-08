"""The 1CC Shrine ~ Records of Eastern Clears - pywebview entry point."""
import json
import os
import sys
import threading
from datetime import datetime

import webview

import db
import session_tracker

window = None  # set in main(); needed for file dialogs and JS pushes


def resource_path(relative):
    # PyInstaller onefile extracts bundled assets to sys._MEIPASS
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


class Api:
    def __init__(self):
        self._conn = db.connect()
        self._lock = threading.Lock()
        self._playing = {}         # game_id -> start datetime (launched sessions)
        self._stopwatches = {}     # game_id -> start datetime

    def get_games(self):
        with self._lock:
            return db.get_games(self._conn)

    def get_grid(self, game_id):
        with self._lock:
            return db.get_grid(self._conn, game_id)

    def cycle_status(self, shot_type_id, difficulty):
        with self._lock:
            return db.cycle_status(self._conn, shot_type_id, difficulty)

    def get_dashboard(self):
        with self._lock:
            return db.get_dashboard(self._conn)

    def pick_next(self, difficulty=None):
        with self._lock:
            return db.pick_next(self._conn, difficulty)

    # ---- v2: sessions & playtime ----

    def set_executable(self, game_id):
        paths = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Executables (*.exe)", "All files (*.*)"),
        )
        if not paths:
            return {"exe_path": None, "cancelled": True}
        path = paths[0]
        with self._lock:
            db.set_exe_path(self._conn, game_id, path)
        return {"exe_path": path, "cancelled": False}

    def play(self, game_id):
        with self._lock:
            game = next(g for g in db.get_games(self._conn) if g["id"] == game_id)
        if not game["exe_path"]:
            return {"needs_exe": True}
        if not os.path.isfile(game["exe_path"]):
            return {"error": "Executable not found: " + game["exe_path"]}
        if game_id in self._playing:
            return {"already_running": True}
        started = datetime.now()
        self._playing[game_id] = started
        threading.Thread(
            target=self._watch_session,
            args=(game_id, game["exe_path"], started),
            daemon=True,
        ).start()
        return {"started": True}

    def _watch_session(self, game_id, exe_path, started):
        try:
            seconds = session_tracker.launch_and_watch(exe_path)
        except Exception as e:
            self._playing.pop(game_id, None)
            self._notify_js("sessionFailed", game_id, str(e))
            return
        self._playing.pop(game_id, None)
        minutes = int(seconds // 60)
        with self._lock:
            stored = db.add_session(
                self._conn, game_id, started.isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"), minutes, "launched",
            )
        self._notify_js("sessionEnded", game_id, minutes if stored else 0)

    def _notify_js(self, fn, *args):
        if window is not None:
            window.evaluate_js(f"{fn}({', '.join(json.dumps(a) for a in args)})")

    def stopwatch_start(self, game_id):
        self._stopwatches[game_id] = datetime.now()
        return {"started": True}

    def stopwatch_stop(self, game_id):
        started = self._stopwatches.pop(game_id, None)
        if started is None:
            return {"error": "No stopwatch running for this game"}
        ended = datetime.now()
        minutes = int((ended - started).total_seconds() // 60)
        with self._lock:
            stored = db.add_session(
                self._conn, game_id, started.isoformat(timespec="seconds"),
                ended.isoformat(timespec="seconds"), minutes, "stopwatch",
            )
        return {"stored": stored, "minutes": minutes}

    def flush_active_sessions(self):
        """Window is closing: watcher threads are daemons and die with the
        process, so persist what we know about in-flight sessions now.
        Records playtime up to this moment; the game may keep running."""
        now = datetime.now()
        with self._lock:
            for game_id, started in list(self._playing.items()):
                minutes = int((now - started).total_seconds() // 60)
                db.add_session(self._conn, game_id,
                               started.isoformat(timespec="seconds"),
                               now.isoformat(timespec="seconds"),
                               minutes, "launched")
            self._playing.clear()
            for game_id, started in list(self._stopwatches.items()):
                minutes = int((now - started).total_seconds() // 60)
                db.add_session(self._conn, game_id,
                               started.isoformat(timespec="seconds"),
                               now.isoformat(timespec="seconds"),
                               minutes, "stopwatch")
            self._stopwatches.clear()

    def add_manual_session(self, game_id, date_str, minutes):
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return {"error": "Minutes must be a number"}
        if minutes < 1:
            return {"error": "Sessions under 1 minute are not recorded"}
        if not date_str:
            return {"error": "Pick a date"}
        with self._lock:
            db.add_session(self._conn, game_id, date_str, None, minutes, "manual")
        return {"stored": True, "minutes": minutes}


def main():
    global window
    api = Api()
    window = webview.create_window(
        "The 1CC Shrine ~ Records of Eastern Clears",
        resource_path(os.path.join("web", "index.html")),
        js_api=api,
        width=1150,
        height=820,
    )
    window.events.closing += api.flush_active_sessions
    webview.start()


if __name__ == "__main__":
    main()
