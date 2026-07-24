import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.cues import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


# --- atomcraft_create_cue ---

def test_create_cue_simple_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_simple_cue", {"succeed": True, "data": "cue-1", "message": ""})
    r = json.loads(fns["atomcraft_create_cue"](method="simple", parent="cs1", material="mat1"))
    assert r["success"] is True
    assert r["data"] == "cue-1"
    assert fake.call_log[-1][1] == "create_simple_cue"
    assert fake.call_log[-1][2] == ("cs1", "mat1")


def test_create_cue_simple_missing_material(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_create_cue"](method="simple", parent="cs1"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_create_cue_waveform_region_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_waveform_region", {"succeed": True, "data": "wfr-1", "message": ""})
    r = json.loads(fns["atomcraft_create_cue"](method="waveform_region", parent="track1", material="mat1"))
    assert r["success"] is True
    assert r["data"] == "wfr-1"
    assert fake.call_log[-1][1] == "create_waveform_region"
    assert fake.call_log[-1][2] == ("track1", "mat1")


def test_create_cue_waveform_region_missing_material(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_create_cue"](method="waveform_region", parent="track1"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_create_cue_cuelink_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_cuelink", {"succeed": True, "data": "cue-2", "message": ""})
    r = json.loads(fns["atomcraft_create_cue"](method="cuelink", parent="cs1", cue="orig-cue"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_cuelink"
    assert fake.call_log[-1][2] == ("cs1", "orig-cue")


def test_create_cue_cuelink_missing_cue(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_create_cue"](method="cuelink", parent="cs1"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_create_cue_external_cuelink_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_external_cuelink", {"succeed": True, "data": "cue-3", "message": ""})
    r = json.loads(fns["atomcraft_create_cue"](method="external_cuelink",
                                                parent="cs1", link_cue_name="ExtCue"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_external_cuelink"
    assert fake.call_log[-1][2] == ("cs1", "ExtCue", None)


def test_create_cue_external_cuelink_missing_params(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_create_cue"](method="external_cuelink", parent="cs1"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_create_cue_unknown_method_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_create_cue"](method="explode", parent="cs1"))
    assert r["code"] == "INVALID_PARAMS"


def test_create_cue_is_non_idempotent(tools):
    fns, fake = tools
    fake.fail_times("project", "create_simple_cue", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_create_cue"](method="simple", parent="cs1", material="mat1"))
    assert r["code"] == "UNKNOWN_OUTCOME"


# --- atomcraft_manage_bookmark ---

def test_bookmark_add_success(tools):
    fns, fake = tools
    fake.set_handler("project", "add_bookmark", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_bookmark"](action="add", target="u1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "add_bookmark"


def test_bookmark_add_missing_target(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_bookmark"](action="add"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_bookmark_remove_success(tools):
    fns, fake = tools
    fake.set_handler("project", "remove_bookmark", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_bookmark"](action="remove", target="u1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "remove_bookmark"


def test_bookmark_remove_missing_target(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_bookmark"](action="remove"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_bookmark_list_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_bookmarks", {"succeed": True, "data": ["b1", "b2"], "message": ""})
    r = json.loads(fns["atomcraft_manage_bookmark"](action="list"))
    assert r["success"] is True
    assert r["data"]["ids"] == ["b1", "b2"]
    assert r["data"]["total"] == 2
    assert fake.call_log[-1][1] == "get_bookmarks"


def test_bookmark_unknown_action_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_bookmark"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"
