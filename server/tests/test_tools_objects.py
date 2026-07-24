import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.objects import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


def test_find_by_name_success(tools):
    fns, fake = tools
    fake.set_handler("project", "find_object", {"succeed": True, "data": "uuid-1", "message": ""})
    r = json.loads(fns["atomcraft_get_object"](method="find_by_name",
                                               object_type="CueSheet", object_name="S1"))
    assert r["success"] is True and r["data"] == "uuid-1"


def test_find_by_name_missing_params_has_hint(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_get_object"](method="find_by_name"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_invalid_type_gets_catalog_hint(tools):
    fns, fake = tools
    fake.set_handler("project", "find_objects",
                     {"succeed": False, "message": "指定したタイプ [MaterialFolde] は現在利用できません。"})
    r = json.loads(fns["atomcraft_get_object"](method="find_all_by_type",
                                               object_type="MaterialFolde"))
    assert r["code"] == "INVALID_TYPE"
    assert "MaterialFolder" in r["hint"]  # 近似候補


def test_list_pagination(tools):
    fns, fake = tools
    ids = [f"u{i}" for i in range(600)]
    fake.set_handler("project", "get_child_objects", {"succeed": True, "data": ids, "message": ""})
    r = json.loads(fns["atomcraft_get_object"](method="get_children",
                                               parent="p", object_type="Cue"))
    assert len(r["data"]["ids"]) == 500
    assert r["data"]["total"] == 600
    assert r["data"]["truncated"] is True
    r2 = json.loads(fns["atomcraft_get_object"](method="get_children",
                                                parent="p", object_type="Cue", offset=500))
    assert len(r2["data"]["ids"]) == 100


def test_create_object_is_non_idempotent(tools):
    """createは失敗時リトライされずUNKNOWN_OUTCOMEになる"""
    fns, fake = tools
    fake.fail_times("project", "create_object", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_create_object"](parent="p", object_type="Cue", object_name="n"))
    assert r["code"] == "UNKNOWN_OUTCOME"
    assert "確認" in r["hint"]
    assert len([c for c in fake.call_log if c[1] == "create_object"]) == 1


def test_modify_unknown_action_rejected_by_signature(tools):
    """actionはLiteral型。ランタイムでも未知値はINVALID_PARAMSで弾く"""
    fns, _ = tools
    r = json.loads(fns["atomcraft_modify_object"](action="explode", target="u"))
    assert r["code"] == "INVALID_PARAMS"
