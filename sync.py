"""Production preset sync.

Copies the preset configs from the production (pipeline) folder into the local
config folder. The production folder always wins: local files with the same
name are overwritten, nothing is ever deleted.

All disk/network access happens in a background thread so a slow or offline
share can never freeze Blender. The thread never touches bpy; the main thread
polls a timer for the result and then refreshes the config cache.

Accepted production folder layouts:
    <folder>/Presets_Config/*.json  (+ <folder>/basic_settings.json, <folder>/output_nodes.json)
    <folder>/*.json                 (+ basic_settings.json, output_nodes.json in the same folder)
"""

import filecmp
import os
import shutil
import threading
import time

import bpy

from . import config

status = {"level": "idle", "message": "Not synced yet this session", "time": ""}
_job = None


def _set_status(level, message):
    status["level"] = level
    status["message"] = message
    status["time"] = time.strftime("%H:%M:%S")


def is_running():
    return _job is not None and not _job["done"]


# -- worker thread (no bpy access in here) -----------------------------------

def _collect_pairs(src, presets_dst, root_dst):
    pairs = []
    nested = os.path.join(src, config.PRESETS_DIR_NAME)
    presets_src = nested if os.path.isdir(nested) else src

    for fn in sorted(os.listdir(presets_src)):
        stem, ext = os.path.splitext(fn)
        full = os.path.join(presets_src, fn)
        if (ext.lower() == ".json" and stem.lower() not in config.RESERVED_STEMS
                and os.path.isfile(full)):
            pairs.append((full, os.path.join(presets_dst, fn)))

    # Root-level configs (basic settings, output nodes), found next to or inside the presets folder
    for filename in (config.BASIC_SETTINGS_FILENAME, config.OUTPUT_NODES_FILENAME):
        for candidate in (os.path.join(src, filename), os.path.join(presets_src, filename)):
            if os.path.isfile(candidate):
                pairs.append((candidate, os.path.join(root_dst, filename)))
                break
    return pairs


def _copy_if_changed(src, dst):
    if os.path.isfile(dst) and filecmp.cmp(src, dst, shallow=False):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tmp"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)   # atomic: a half-written file is never visible
    return True


def _worker(job):
    try:
        src = job["src"]
        if not os.path.isdir(src):
            job["result"] = ("error", f"Production folder not reachable: {src}")
            return

        pairs = _collect_pairs(src, job["presets_dst"], job["root_dst"])
        if not pairs:
            job["result"] = ("warning", f"No .json files found in {src}")
            return

        updated = unchanged = 0
        failed = []
        for s, d in pairs:
            try:
                if _copy_if_changed(s, d):
                    updated += 1
                else:
                    unchanged += 1
            except OSError as e:
                failed.append(f"{os.path.basename(s)} ({e})")

        message = f"{updated} updated, {unchanged} unchanged"
        if failed:
            job["result"] = ("warning", message + "; failed: " + ", ".join(failed))
        else:
            job["result"] = ("ok", message)
    except Exception as e:
        job["result"] = ("error", f"Sync failed: {e}")
    finally:
        job["done"] = True


# -- main thread ---------------------------------------------------------------

def _redraw_all():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass


def _poll():
    job = _job
    if job is None or not job["done"]:
        return 0.25
    level, message = job["result"]
    config.reload_configs()
    _set_status(level, message)
    _redraw_all()
    return None   # stop the timer


def start(production_path):
    """Start a sync in the background. Returns True if one was started."""
    global _job
    if is_running():
        return False

    raw = (production_path or "").strip()
    if not raw:
        _set_status("skipped", "No production path set - sync skipped")
        return False

    src = bpy.path.abspath(raw)
    _job = {
        "src": src,
        "presets_dst": config.get_presets_dir(),
        "root_dst": config.get_config_root(),
        "done": False,
        "result": None,
    }
    _set_status("running", f"Syncing from {src} ...")
    threading.Thread(target=_worker, args=(_job,), daemon=True).start()

    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, first_interval=0.25)
    return True


def _startup_sync():
    prefs = config.get_prefs()
    if prefs is not None:
        start(prefs.production_path)
    return None


def schedule_startup_sync():
    # Not on the render farm / in background mode
    if bpy.app.background:
        return
    bpy.app.timers.register(_startup_sync, first_interval=3.0)


def unregister():
    for fn in (_poll, _startup_sync):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
