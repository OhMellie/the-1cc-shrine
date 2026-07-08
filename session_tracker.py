"""Launch a game executable and measure how long it runs.

Two discovery mechanisms, both needed in practice:

1. Process tree: the session covers the launched process AND every
   descendant, not just the direct child - loaders like thcrap spawn
   the real game and exit immediately.
2. Directory adoption: some loaders (observed with a thcrap-patched
   wrapper exe) spawn the game *detached*, so it is never a child of
   anything we launched. Any process created after launch whose
   executable lives under the launched exe's directory is adopted into
   the session. This assumes the loader sits in (or under) the game's
   folder, which is how thcrap/vpatch setups are laid out.

The session ends when no tracked process is left, but never before
STARTUP_GRACE seconds have elapsed - a loader can exit before the game
process exists, and the gap must not end the session. Duration is
counted to the moment the last process died, not to when the grace
period ran out.
"""
import os
import subprocess
import time
from functools import lru_cache

import psutil

STARTUP_GRACE = 15  # seconds to keep looking for late-appearing processes


@lru_cache(maxsize=4096)
def _canon(path):
    """Canonical form for path comparison: realpath resolves 8.3 short
    names (psutil reports whatever form the process was spawned with)
    and junctions; normcase handles Windows case-insensitivity."""
    return os.path.normcase(os.path.realpath(path))


def _poll_interval(elapsed):
    # Tight polling early to catch a loader -> game handoff, then relax.
    if elapsed < 10:
        return 0.1
    if elapsed < 60:
        return 0.5
    return 2.0


def _dir_processes(anchor_dir, since):
    """Processes created after `since` whose exe lives under anchor_dir."""
    prefix = _canon(anchor_dir) + os.sep
    found = set()
    for proc in psutil.process_iter(attrs=["exe", "create_time"]):
        try:
            exe = proc.info["exe"]
            # create_time check first: skips the realpath call for the
            # vast majority of (old) processes on the system
            if (exe
                    and proc.info["create_time"] >= since - 2
                    and _canon(exe).startswith(prefix)):
                found.add(proc)
        except (psutil.Error, OSError):
            continue
    return found


def watch_tree(pid, anchor_dir=None):
    """Block until `pid`, its descendants, and (if anchor_dir is given)
    every adopted same-directory process have all exited.

    Returns session duration in seconds, measured to the last moment a
    tracked process was seen alive. psutil identifies processes by
    (pid, create_time), so PID reuse cannot resurrect a session.
    """
    start = time.monotonic()
    launch_walltime = time.time()
    try:
        tracked = {psutil.Process(pid)}
    except psutil.NoSuchProcess:
        tracked = set()

    last_alive = start
    while True:
        alive = set()
        for proc in tracked:
            try:
                if not proc.is_running():
                    continue
                alive.add(proc)
                for child in proc.children(recursive=True):
                    alive.add(child)
            except psutil.Error:
                continue
        if anchor_dir:
            alive |= _dir_processes(anchor_dir, launch_walltime)
        tracked = alive

        elapsed = time.monotonic() - start
        if tracked:
            last_alive = time.monotonic()
        elif elapsed >= STARTUP_GRACE:
            break
        time.sleep(_poll_interval(elapsed))

    return last_alive - start


def launch_and_watch(exe_path):
    """Spawn exe_path (cwd = its own directory; Touhou games need this to
    find their data files) and block until its process tree - including
    detached same-directory processes - exits.

    Returns duration in seconds.
    """
    exe_dir = os.path.dirname(exe_path) or None
    proc = subprocess.Popen([exe_path], cwd=exe_dir)
    return watch_tree(proc.pid, anchor_dir=exe_dir)
