import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.materials import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


def test_register_success(tools):
    fns, fake = tools
    fake.set_handler("project", "register_material", {"succeed": True, "data": "mat-1", "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="register", parent="mf", file_path="C:/foo/a.wav"))
    assert r["success"] is True
    assert r["data"] == "mat-1"
    assert fake.call_log[-1][1] == "register_material"
    assert fake.call_log[-1][2] == ("mf", "C:/foo/a.wav")


def test_register_missing_params(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_material"](action="register"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_register_failure_maps_to_already_exists(tools):
    fns, fake = tools
    fake.set_handler("project", "register_material",
                     {"succeed": False,
                      "message": "マテリアルの登録に失敗しました。 C:/foo/3844_voice_drop_06.wav"})
    r = json.loads(fns["atomcraft_manage_material"](action="register",
                                                    parent="mf", file_path="C:/foo/3844_voice_drop_06.wav"))
    assert r["code"] == "ALREADY_EXISTS"
    assert "find_by_name" in r["hint"]


def test_register_unregistered_success(tools):
    fns, fake = tools
    fake.set_handler("project", "register_unregistered_materials",
                     {"succeed": True, "data": ["m1", "m2"], "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="register_unregistered", material_folder="mf"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "register_unregistered_materials"
    assert fake.call_log[-1][2] == ("mf",)


def test_register_unregistered_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_material"](action="register_unregistered"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_get_info_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_materialinfo", {"succeed": True, "data": {"count": 3}, "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="get_info", workunit="wu1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "get_materialinfo"


def test_get_info_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_material"](action="get_info"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_get_project_info_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_project_materialinfo", {"succeed": True, "data": {"count": 9}, "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="get_project_info"))
    assert r["success"] is True


def test_get_root_folder_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_material_rootfolder", {"succeed": True, "data": "folder-1", "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="get_root_folder", workunit="wu1"))
    assert r["success"] is True
    assert r["data"] == "folder-1"


def test_get_root_folder_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_material"](action="get_root_folder"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_get_project_root_folder_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_project_material_rootfolder",
                     {"succeed": True, "data": "root-folder", "message": ""})
    r = json.loads(fns["atomcraft_manage_material"](action="get_project_root_folder"))
    assert r["success"] is True


def test_unknown_action_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_material"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


def test_register_is_non_idempotent(tools):
    """registerは失敗時リトライされずUNKNOWN_OUTCOMEになる"""
    fns, fake = tools
    fake.fail_times("project", "register_material", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_manage_material"](action="register", parent="mf", file_path="a.wav"))
    assert r["code"] == "UNKNOWN_OUTCOME"
    assert len([c for c in fake.call_log if c[1] == "register_material"]) == 1
