"""SQLite layer: schema, idempotent seeding, and all queries the UI needs.

Database lives in %APPDATA%\\TouhouTracker\\tracker.db so a packaged .exe
keeps data across rebuilds. Override with the TOUHOU_TRACKER_DB env var.
"""
import os
import random
import sqlite3
from datetime import date

import seed_data

MAIN_DIFFICULTIES = ["Easy", "Normal", "Hard", "Lunatic"]
STATUS_CYCLE = ["not_cleared", "cleared", "one_cc", "one_cc_no_bomb",
                "one_cc_no_miss", "one_cc_nmnb"]
PHANTASM_GAME_NUMBER = 7  # PCB only


def is_one_cc(status):
    return STATUS_CYCLE.index(status) >= STATUS_CYCLE.index("one_cc")

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id     INTEGER PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE,
    title  TEXT    NOT NULL,
    year   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS shot_types (
    id             INTEGER PRIMARY KEY,
    game_id        INTEGER NOT NULL REFERENCES games(id),
    name           TEXT    NOT NULL,
    sort_order     INTEGER NOT NULL,
    main_eligible  INTEGER NOT NULL DEFAULT 1,
    extra_eligible INTEGER NOT NULL DEFAULT 1,
    UNIQUE (game_id, name)
);
CREATE TABLE IF NOT EXISTS attempts (
    id            INTEGER PRIMARY KEY,
    shot_type_id  INTEGER NOT NULL REFERENCES shot_types(id),
    difficulty    TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    date_achieved TEXT,
    UNIQUE (shot_type_id, difficulty)
);
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    game_id    INTEGER NOT NULL REFERENCES games(id),
    started_at TEXT    NOT NULL,
    ended_at   TEXT,
    minutes    INTEGER NOT NULL,
    method     TEXT    NOT NULL CHECK (method IN ('launched','stopwatch','manual'))
);
"""


def db_path():
    override = os.environ.get("TOUHOU_TRACKER_DB")
    if override:
        return override
    base = os.path.join(os.environ["APPDATA"], "TouhouTracker")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "tracker.db")


def connect(path=None):
    conn = sqlite3.connect(path or db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def _migrate(conn):
    # v2: games.exe_path — ALTER only, existing rows keep NULL
    columns = [r["name"] for r in conn.execute("PRAGMA table_info(games)")]
    if "exe_path" not in columns:
        conn.execute("ALTER TABLE games ADD COLUMN exe_path TEXT")


def init_db(conn):
    conn.executescript(SCHEMA)
    _migrate(conn)
    for number, title, year in seed_data.GAMES:
        conn.execute(
            "INSERT OR IGNORE INTO games (number, title, year) VALUES (?, ?, ?)",
            (number, title, year),
        )
    for number, shots in seed_data.SHOT_TYPES.items():
        game_id = conn.execute(
            "SELECT id FROM games WHERE number = ?", (number,)
        ).fetchone()["id"]
        for order, (name, main_ok, extra_ok) in enumerate(shots):
            conn.execute(
                "INSERT OR IGNORE INTO shot_types"
                " (game_id, name, sort_order, main_eligible, extra_eligible)"
                " VALUES (?, ?, ?, ?, ?)",
                (game_id, name, order, int(main_ok), int(extra_ok)),
            )
    conn.commit()


def eligible_difficulties(shot_row, game_number):
    """Ordered list of difficulties this shot type can actually play."""
    diffs = []
    if shot_row["main_eligible"]:
        diffs.extend(MAIN_DIFFICULTIES)
    if shot_row["extra_eligible"]:
        diffs.append("Extra")
        if game_number == PHANTASM_GAME_NUMBER:
            diffs.append("Phantasm")
    return diffs


def get_games(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, number, title, year, exe_path FROM games ORDER BY number"
    )]


def set_exe_path(conn, game_id, path):
    conn.execute("UPDATE games SET exe_path = ? WHERE id = ?", (path, game_id))
    conn.commit()


def add_session(conn, game_id, started_at, ended_at, minutes, method):
    """Store a play session. Sessions under 1 minute are misclicks: discarded.

    Returns True if the session was stored."""
    minutes = int(minutes)
    if minutes < 1:
        return False
    conn.execute(
        "INSERT INTO sessions (game_id, started_at, ended_at, minutes, method)"
        " VALUES (?, ?, ?, ?, ?)",
        (game_id, started_at, ended_at, minutes, method),
    )
    conn.commit()
    return True


def get_playtime(conn):
    """Total minutes per game_id (games with no sessions are absent)."""
    return {
        r["game_id"]: r["minutes"]
        for r in conn.execute(
            "SELECT game_id, SUM(minutes) AS minutes FROM sessions GROUP BY game_id"
        )
    }


def get_grid(conn, game_id):
    game = dict(conn.execute(
        "SELECT id, number, title, year, exe_path FROM games WHERE id = ?", (game_id,)
    ).fetchone())
    game["playtime_minutes"] = get_playtime(conn).get(game_id, 0)
    columns = list(MAIN_DIFFICULTIES) + ["Extra"]
    if game["number"] == PHANTASM_GAME_NUMBER:
        columns.append("Phantasm")
    shots = []
    for row in conn.execute(
        "SELECT * FROM shot_types WHERE game_id = ? ORDER BY sort_order",
        (game_id,),
    ):
        eligible = eligible_difficulties(row, game["number"])
        cells = {d: {"status": "not_cleared", "date": None} for d in eligible}
        for att in conn.execute(
            "SELECT difficulty, status, date_achieved FROM attempts"
            " WHERE shot_type_id = ?",
            (row["id"],),
        ):
            if att["difficulty"] in cells:
                cells[att["difficulty"]] = {
                    "status": att["status"],
                    "date": att["date_achieved"],
                }
        shots.append({"id": row["id"], "name": row["name"], "cells": cells})
    # Games with no Extra stage (PoFV, UDoALG) drop the Extra column entirely
    if not any("Extra" in s["cells"] for s in shots):
        columns.remove("Extra")
    return {"game": game, "columns": columns, "shots": shots}


def cycle_status(conn, shot_type_id, difficulty):
    """Advance a cell: not_cleared -> cleared -> one_cc -> not_cleared."""
    row = conn.execute(
        "SELECT status FROM attempts WHERE shot_type_id = ? AND difficulty = ?",
        (shot_type_id, difficulty),
    ).fetchone()
    current = row["status"] if row else "not_cleared"
    new = STATUS_CYCLE[(STATUS_CYCLE.index(current) + 1) % len(STATUS_CYCLE)]
    if new == "not_cleared":
        conn.execute(
            "DELETE FROM attempts WHERE shot_type_id = ? AND difficulty = ?",
            (shot_type_id, difficulty),
        )
        achieved = None
    else:
        achieved = date.today().isoformat()
        conn.execute(
            "INSERT INTO attempts (shot_type_id, difficulty, status, date_achieved)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT (shot_type_id, difficulty)"
            " DO UPDATE SET status = excluded.status,"
            "               date_achieved = excluded.date_achieved",
            (shot_type_id, difficulty, new, achieved),
        )
    conn.commit()
    return {"status": new, "date": achieved}


def _all_cells(conn):
    """Yield (game_number, game_title, shot_id, shot_name, difficulty, status)."""
    status_map = {
        (r["shot_type_id"], r["difficulty"]): r["status"]
        for r in conn.execute("SELECT shot_type_id, difficulty, status FROM attempts")
    }
    for shot in conn.execute(
        "SELECT s.*, g.number AS game_number, g.title AS game_title, g.id AS gid"
        " FROM shot_types s JOIN games g ON g.id = s.game_id"
        " ORDER BY g.number, s.sort_order"
    ):
        for diff in eligible_difficulties(shot, shot["game_number"]):
            status = status_map.get((shot["id"], diff), "not_cleared")
            yield shot, diff, status


def get_dashboard(conn):
    per_game, per_difficulty = {}, {}
    for shot, diff, status in _all_cells(conn):
        counters = {s: 0 for s in STATUS_CYCLE[1:]}
        g = per_game.setdefault(shot["gid"], {
            "game_id": shot["gid"], "number": shot["game_number"],
            "title": shot["game_title"], "total": 0, "one_cc_plus": 0,
            **counters,
        })
        d = per_difficulty.setdefault(diff, {
            "difficulty": diff, "total": 0, "one_cc_plus": 0, **counters,
        })
        for bucket in (g, d):
            bucket["total"] += 1
            if status != "not_cleared":
                bucket[status] += 1
            if is_one_cc(status):
                bucket["one_cc_plus"] += 1
    playtime = get_playtime(conn)
    for g in per_game.values():
        g["minutes"] = playtime.get(g["game_id"], 0)
    diff_order = MAIN_DIFFICULTIES + ["Extra", "Phantasm"]
    return {
        "games": sorted(per_game.values(), key=lambda g: g["number"]),
        "difficulties": sorted(
            per_difficulty.values(), key=lambda d: diff_order.index(d["difficulty"])
        ),
    }


def pick_next(conn, difficulty=None):
    """Random cell not yet 1cc'd, optionally restricted to one difficulty."""
    candidates = [
        {
            "game_id": shot["gid"],
            "game_title": shot["game_title"],
            "game_number": shot["game_number"],
            "shot_type_id": shot["id"],
            "shot_name": shot["name"],
            "difficulty": diff,
            "status": status,
        }
        for shot, diff, status in _all_cells(conn)
        if not is_one_cc(status) and (difficulty is None or diff == difficulty)
    ]
    return random.choice(candidates) if candidates else None


if __name__ == "__main__":
    # Smoke test against a throwaway database
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "smoke.db")
    conn = connect(path)
    games = get_games(conn)
    n_shots = conn.execute("SELECT COUNT(*) c FROM shot_types").fetchone()["c"]
    print(f"games: {len(games)}, shot types: {n_shots}")
    for g in games:
        rows = conn.execute(
            "SELECT COUNT(*) c FROM shot_types WHERE game_id = ?", (g["id"],)
        ).fetchone()["c"]
        print(f"  TH{g['number']:02d} {g['title']}: {rows} shot types")
    init_db(conn)  # re-seed must not duplicate
    n2 = conn.execute("SELECT COUNT(*) c FROM shot_types").fetchone()["c"]
    assert n2 == n_shots, "re-seeding duplicated rows!"

    grid = get_grid(conn, games[1]["id"])  # PCB
    assert grid["columns"][-1] == "Phantasm"
    grid9 = get_grid(conn, games[3]["id"])  # PoFV
    assert "Extra" not in grid9["columns"]

    shot = grid["shots"][0]
    for expected in STATUS_CYCLE[1:] + ["not_cleared"]:
        assert cycle_status(conn, shot["id"], "Normal")["status"] == expected

    # clicks land on: 2 -> one_cc, 3 -> no_bomb, 5 -> nmnb
    for clicks, idx in ((2, 0), (3, 1), (5, 2)):
        for _ in range(clicks):
            cycle_status(conn, grid["shots"][idx]["id"], "Hard")
    dash = get_dashboard(conn)
    pcb = next(g for g in dash["games"] if g["number"] == 7)
    assert (pcb["one_cc"], pcb["one_cc_no_bomb"], pcb["one_cc_nmnb"],
            pcb["one_cc_plus"]) == (1, 1, 1, 3), pcb

    for s in grid["shots"]:
        for _ in range(5):
            cycle_status(conn, s["id"], "Phantasm")
    assert pick_next(conn, "Phantasm") is None, "picker offered a tiered cell"

    pick = pick_next(conn, "Lunatic")
    assert pick and pick["difficulty"] == "Lunatic"
    total = sum(g["total"] for g in get_dashboard(conn)["games"])
    print(f"total trackable cells: {total}")

    # v2: sessions & playtime
    g6 = games[0]
    assert not add_session(conn, g6["id"], "2026-07-08T12:00:00",
                           "2026-07-08T12:00:20", 0, "launched"), "sub-minute kept"
    assert add_session(conn, g6["id"], "2026-07-08T12:00:00",
                       "2026-07-08T13:30:00", 90, "launched")
    assert add_session(conn, g6["id"], "2026-07-07", None, 45, "manual")
    assert get_playtime(conn)[g6["id"]] == 135
    set_exe_path(conn, g6["id"], r"C:\games\th06\vpatch.exe")
    assert get_games(conn)[0]["exe_path"].endswith("vpatch.exe")
    assert next(g for g in get_dashboard(conn)["games"]
                if g["number"] == 6)["minutes"] == 135
    assert get_grid(conn, g6["id"])["game"]["playtime_minutes"] == 135
    try:
        add_session(conn, g6["id"], "2026-07-08", None, 10, "bogus")
        raise SystemExit("method CHECK constraint not enforced")
    except sqlite3.IntegrityError:
        pass
    print("smoke test OK (incl. v2 sessions)")
