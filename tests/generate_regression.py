"""Regression checks for the two generate operators, run inside a real Blender window.

No request leaves the machine: requests.post / requests.get are replaced before any
operator runs. Results are written to a JSON file and Blender quits.

Usage (the add-on must already be installed and enabled):

    blender --python tests/generate_regression.py -- <out.json> <add-on module>

<add-on module> is `uthana` for a classic install and `bl_ext.user_default.uthana`
for an extension install. On a machine without a display, run it under `xvfb-run`.

Scenarios, for text to motion and (prefixed video_) for video to motion:
  scene_switch    the scene on screen changes while a job runs
  scene_deleted   the scene that started the job is deleted while it runs
  stalled_submit  the paid request never gets an answer
  stalled_status  a status check never gets an answer
  submit_timeout  the paid request fails with a network timeout (text to motion only)
"""

import json
import os
import sys
import tempfile
import threading
import time
import traceback
from importlib import import_module

import bpy
import requests

ARGS = sys.argv[sys.argv.index("--") + 1 :]
OUT, MODULE = ARGS[0], ARGS[1]

modal = import_module(MODULE + ".ui.modal_operators")
OP = modal.UTHANA_OT_generate_motion
VOP = modal.UTHANA_OT_video_to_motion
modal.JOB_POLL_SECONDS = 0.5

results = {"blender": bpy.app.version_string, "scenarios": [], "errors": []}
fake = {"submit": "ok", "status": "finish", "submits": 0, "status_calls": 0, "timeouts": []}
release = threading.Event()
run = {"index": 0, "started": 0.0, "data": {}}
BASE_SCENE = bpy.data.scenes[0].name


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b""
        self.text = json.dumps(payload)
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=8192):
        return iter(())


def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
    if files is not None:
        fake["submits"] += 1
        fake["timeouts"].append(["upload", timeout is not None])
        if fake["submit"] == "stall":
            release.wait(60)
        job = {"id": "jobREG", "status": "RESERVED"}
        return FakeResponse({"data": {"create_video_to_motion": {"job": job}}})
    query = (json or {}).get("query", "")
    if "create_text_to_motion_job" in query:
        fake["submits"] += 1
        fake["timeouts"].append(["submit", timeout is not None])
        if fake["submit"] == "stall":
            release.wait(60)
        if fake["submit"] == "timeout":
            raise requests.exceptions.ReadTimeout("simulated")
        job = {"id": "jobREG", "status": "RESERVED"}
        return FakeResponse({"data": {"create_text_to_motion_job": {"job": job}}})
    if "job(" in query or "GetJob" in query:
        fake["status_calls"] += 1
        fake["timeouts"].append(["status", timeout is not None])
        if fake["status"] == "stall":
            release.wait(60)
        if fake["status_calls"] < 3:
            return FakeResponse({"data": {"job": {"id": "jobREG", "status": "STARTED"}}})
        result = {"exc": None, "result": {"id": "mREG", "name": "regression motion", "tags": {}}}
        job = {"id": "jobREG", "status": "FINISHED", "result": result}
        return FakeResponse({"data": {"job": job}})
    return FakeResponse({"data": {}})


def fake_get(url, **kwargs):
    return FakeResponse({}, 404)


requests.post = fake_post
requests.get = fake_get


def window():
    return bpy.context.window_manager.windows[0]


def view3d():
    win = window()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def start_generation(scene):
    props = scene.uthana_props
    props.api_key = "test-key"
    props.prompt = "a person waves"
    props.ttm_model = "text-to-motion-3.0-lite"
    props.pending_motion_id = ""
    win, area, region = view3d()
    with bpy.context.temp_override(window=win, area=area, region=region, scene=scene):
        return bpy.ops.uthana.generate_motion("INVOKE_DEFAULT")


def start_video(scene):
    props = scene.uthana_props
    props.api_key = "test-key"
    props.video_file_path = VIDEO_FILE
    props.video_motion_name = "regression video"
    props.pending_motion_id = ""
    win, area, region = view3d()
    with bpy.context.temp_override(window=win, area=area, region=region, scene=scene):
        return bpy.ops.uthana.video_to_motion("INVOKE_DEFAULT")


def reset_fake(submit="ok", status="finish", deadline=None):
    release.clear()
    fake.update(submit=submit, status=status, submits=0, status_calls=0)
    OP._timeout_seconds = deadline or 900.0
    VOP._timeout_seconds = deadline or 1200.0


def any_running():
    return OP.is_running() or VOP.is_running()


def base_scene():
    return bpy.data.scenes[BASE_SCENE]


# Each scenario: setup() starts a generation, check() runs once it has stopped (or the
# wait limit passed) and returns a dict of named pass/fail checks.


def setup_scene_switch():
    reset_fake()
    origin = base_scene()
    window().scene = origin
    started = start_generation(origin)
    other = bpy.data.scenes.new("Other")
    window().scene = other
    run["data"] = {"started": started, "other": other.name}


def check_scene_switch():
    origin, other = base_scene(), bpy.data.scenes[run["data"]["other"]]
    checks = {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "result_in_origin_scene": origin.uthana_props.pending_motion_id == "mREG",
        "origin_status_cleared": origin.uthana_props.ttm_job_status == "",
        "nothing_in_other_scene": other.uthana_props.pending_motion_id == "",
        "other_status_untouched": other.uthana_props.ttm_job_status == "",
        "one_paid_request": fake["submits"] == 1,
    }
    window().scene = origin
    bpy.data.scenes.remove(other)
    # Removing a scene invalidates earlier references, so look the base scene up again.
    base_scene().uthana_props.pending_motion_id = ""
    return checks


def setup_scene_deleted():
    reset_fake()
    doomed = bpy.data.scenes.new("Doomed")
    window().scene = doomed
    started = start_generation(doomed)
    window().scene = base_scene()
    bpy.data.scenes.remove(doomed)
    run["data"] = {"started": started}


def check_scene_deleted():
    origin = base_scene()
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_cleanly": not OP.is_running(),
        "nothing_in_other_scene": origin.uthana_props.pending_motion_id == "",
        "other_status_untouched": origin.uthana_props.ttm_job_status == "",
        "one_paid_request": fake["submits"] == 1,
    }


def setup_stalled_submit():
    reset_fake(submit="stall", deadline=3.0)
    run["data"] = {"started": start_generation(base_scene())}


def check_stalled_submit():
    props = base_scene().uthana_props
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_at_deadline": not OP.is_running() and run["data"]["seconds"] < 8,
        "status_cleared": props.ttm_job_status == "",
        "no_result": props.pending_motion_id == "",
        "paid_request_not_retried": fake["submits"] == 1,
    }


def setup_stalled_status():
    reset_fake(status="stall", deadline=4.0)
    run["data"] = {"started": start_generation(base_scene())}


def check_stalled_status():
    props = base_scene().uthana_props
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_at_deadline": not OP.is_running() and run["data"]["seconds"] < 9,
        "status_cleared": props.ttm_job_status == "",
        "paid_request_not_retried": fake["submits"] == 1,
        "status_checks_not_piled_up": fake["status_calls"] == 1,
    }


def setup_submit_timeout():
    reset_fake(submit="timeout")
    run["data"] = {"started": start_generation(base_scene())}


def check_submit_timeout():
    props = base_scene().uthana_props
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped": not OP.is_running() and run["data"]["seconds"] < 5,
        "status_cleared": props.ttm_job_status == "",
        "paid_request_not_retried": fake["submits"] == 1,
    }


def setup_video_scene_switch():
    reset_fake()
    origin = base_scene()
    window().scene = origin
    started = start_video(origin)
    other = bpy.data.scenes.new("Other")
    window().scene = other
    run["data"] = {"started": started, "other": other.name}


def check_video_scene_switch():
    origin, other = base_scene(), bpy.data.scenes[run["data"]["other"]]
    checks = {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "result_in_origin_scene": origin.uthana_props.pending_motion_id == "mREG",
        "origin_job_cleared": origin.uthana_props.video_job_id == "",
        "nothing_in_other_scene": other.uthana_props.pending_motion_id == "",
        "other_status_untouched": other.uthana_props.video_job_status == "",
        "one_paid_request": fake["submits"] == 1,
    }
    window().scene = origin
    bpy.data.scenes.remove(other)
    base_scene().uthana_props.pending_motion_id = ""
    base_scene().uthana_props.video_job_status = ""
    return checks


def setup_video_scene_deleted():
    reset_fake()
    doomed = bpy.data.scenes.new("Doomed")
    window().scene = doomed
    started = start_video(doomed)
    window().scene = base_scene()
    bpy.data.scenes.remove(doomed)
    run["data"] = {"started": started}


def check_video_scene_deleted():
    origin = base_scene()
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_cleanly": not VOP.is_running(),
        "nothing_in_other_scene": origin.uthana_props.pending_motion_id == "",
        "other_status_untouched": origin.uthana_props.video_job_status == "",
        "one_paid_request": fake["submits"] == 1,
    }


def setup_video_stalled_submit():
    reset_fake(submit="stall", deadline=3.0)
    run["data"] = {"started": start_video(base_scene())}


def check_video_stalled_submit():
    props = base_scene().uthana_props
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_at_deadline": not VOP.is_running() and run["data"]["seconds"] < 8,
        "status_cleared": props.video_job_status == "" and props.video_job_id == "",
        "no_result": props.pending_motion_id == "",
        "paid_request_not_retried": fake["submits"] == 1,
    }


def setup_video_stalled_status():
    reset_fake(status="stall", deadline=4.0)
    run["data"] = {"started": start_video(base_scene())}


def check_video_stalled_status():
    props = base_scene().uthana_props
    return {
        "started": run["data"]["started"] == {"RUNNING_MODAL"},
        "stopped_at_deadline": not VOP.is_running() and run["data"]["seconds"] < 9,
        "status_cleared": props.video_job_status == "" and props.video_job_id == "",
        "paid_request_not_retried": fake["submits"] == 1,
        "status_checks_not_piled_up": fake["status_calls"] == 1,
    }


SCENARIOS = [
    ("scene_switch", setup_scene_switch, check_scene_switch, 20),
    ("scene_deleted", setup_scene_deleted, check_scene_deleted, 20),
    ("stalled_submit", setup_stalled_submit, check_stalled_submit, 12),
    ("stalled_status", setup_stalled_status, check_stalled_status, 14),
    ("submit_timeout", setup_submit_timeout, check_submit_timeout, 10),
    ("video_scene_switch", setup_video_scene_switch, check_video_scene_switch, 20),
    ("video_scene_deleted", setup_video_scene_deleted, check_video_scene_deleted, 20),
    ("video_stalled_submit", setup_video_stalled_submit, check_video_stalled_submit, 12),
    ("video_stalled_status", setup_video_stalled_status, check_video_stalled_status, 14),
]

# A stand-in clip: the fake API never reads it, the add-on only checks that it exists.
VIDEO_FILE = os.path.join(tempfile.mkdtemp(prefix="uthana_regression_"), "clip.mp4")
with open(VIDEO_FILE, "wb") as clip:
    clip.write(b"not a real video")


def finish():
    release.set()
    OP._timeout_seconds = 900.0
    VOP._timeout_seconds = 1200.0
    calls = fake["timeouts"]
    results["network_timeouts_set"] = bool(calls) and all(has for _, has in calls)
    results["passed"] = (
        not results["errors"]
        and results["network_timeouts_set"]
        and len(results["scenarios"]) == len(SCENARIOS)
        and all(all(s["checks"].values()) for s in results["scenarios"])
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, default=str)
    print("REGRESSION", "PASSED" if results["passed"] else "FAILED")
    bpy.ops.wm.quit_blender()


def guarded(fn):
    def wrapper():
        try:
            return fn()
        except Exception:
            results["errors"].append(traceback.format_exc())
            finish()
            return None

    return wrapper


@guarded
def begin():
    if run["index"] >= len(SCENARIOS):
        finish()
        return None
    _, setup, _, _ = SCENARIOS[run["index"]]
    run["started"] = time.time()
    setup()
    bpy.app.timers.register(wait, first_interval=0.5)
    return None


@guarded
def wait():
    name, _, check, limit = SCENARIOS[run["index"]]
    seconds = time.time() - run["started"]
    if any_running() and seconds < limit:
        return 0.5
    run["data"]["seconds"] = seconds
    checks = check()
    results["scenarios"].append({"name": name, "seconds": round(seconds, 1), "checks": checks})
    if any_running():
        # Left running by a failed scenario: nothing after it can be trusted.
        results["errors"].append(f"{name}: generation still marked as running")
        finish()
        return None
    release.set()
    run["index"] += 1
    bpy.app.timers.register(begin, first_interval=1.0)
    return None


def watchdog():
    results["errors"].append("watchdog: regression run did not finish in time")
    finish()
    return None


bpy.app.timers.register(begin, first_interval=3.0)
bpy.app.timers.register(watchdog, first_interval=240.0)
