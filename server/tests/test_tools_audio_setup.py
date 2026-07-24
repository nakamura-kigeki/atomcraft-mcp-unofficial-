import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.audio_setup import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


# --- atomcraft_manage_busmap ---

def test_busmap_create_for_cue_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_busmap_for_cue", {"succeed": True, "data": "bm-1", "message": ""})
    r = json.loads(fns["atomcraft_manage_busmap"](action="create_for_cue", busmap_name="MyBusmap"))
    assert r["success"] is True
    assert r["data"] == "bm-1"
    assert fake.call_log[-1][1] == "create_busmap_for_cue"
    assert fake.call_log[-1][2] == ("MyBusmap",)


def test_busmap_create_for_cue_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_busmap"](action="create_for_cue"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_busmap_get_for_aisac_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_busmap_for_aisac", {"succeed": True, "data": "bm-aisac", "message": ""})
    r = json.loads(fns["atomcraft_manage_busmap"](action="get_for_aisac"))
    assert r["success"] is True


def test_busmap_unknown_action(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_busmap"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


# --- atomcraft_setup_aisac ---

def test_aisac_create_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_aisac", {"succeed": True, "data": "aisac-1", "message": ""})
    r = json.loads(fns["atomcraft_setup_aisac"](
        action="create", parent="p1", object_name="Vol", aisac_control="c1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_aisac"
    assert fake.call_log[-1][2] == ("p1", "Vol", "c1")


def test_aisac_create_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_setup_aisac"](action="create", parent="p1"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_aisac_add_point_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_aisac_point", {"succeed": True, "data": "pt-1", "message": ""})
    r = json.loads(fns["atomcraft_setup_aisac"](
        action="add_point", aisac_graph="g1", control_value=0.5, destination_value=1.0))
    assert r["success"] is True
    assert fake.call_log[-1][2] == ("g1", 0.5, 1.0)


# --- atomcraft_setup_automation ---

def test_automation_create_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_automation", {"succeed": True, "data": "auto-1", "message": ""})
    r = json.loads(fns["atomcraft_setup_automation"](action="create", parent="p1", graph_type="Volume"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_automation"


def test_automation_create_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_setup_automation"](action="create"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_automation_get_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_automation", {"succeed": True, "data": "auto-2", "message": ""})
    r = json.loads(fns["atomcraft_setup_automation"](action="get", parent="p1", graph_type="Volume"))
    assert r["success"] is True


# --- atomcraft_setup_mixer ---

def test_mixer_create_mixer_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_mixer", {"succeed": True, "data": "mx-1", "message": ""})
    r = json.loads(fns["atomcraft_setup_mixer"](action="create_mixer", object_name="MainMixer"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_mixer"


def test_mixer_create_mixer_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_setup_mixer"](action="create_mixer"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_mixer_add_bus_send_success(tools):
    fns, fake = tools
    fake.set_handler("project", "add_mixer_bus_send", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_setup_mixer"](
        action="add_bus_send", bus_from="b1", bus_to="b2", send_level=0.75))
    assert r["success"] is True
    assert fake.call_log[-1][2] == ("b1", "b2", 0.75)


def test_mixer_send_level_out_of_range(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_setup_mixer"](
        action="add_bus_send", bus_from="b1", bus_to="b2", send_level=1.5))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"] == "send_levelは0.0〜1.0"
    assert fake.call_log == []


def test_mixer_send_level_negative_out_of_range(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_setup_mixer"](
        action="add_bus_send", bus_from="b1", bus_to="b2", send_level=-0.1))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_mixer_move_bus_success(tools):
    fns, fake = tools
    fake.set_handler("project", "move_bus", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_setup_mixer"](action="move_bus", bus="b1", destination_bus="b2"))
    assert r["success"] is True


def test_mixer_unknown_action(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_setup_mixer"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"
