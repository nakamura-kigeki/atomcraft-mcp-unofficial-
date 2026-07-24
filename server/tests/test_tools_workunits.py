import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.workunits import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


# --- atomcraft_manage_workunit ---

def test_create_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_workunit", {"succeed": True, "data": "wu-1", "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="create", workunit_name="WU1"))
    assert r["success"] is True
    assert r["data"] == "wu-1"
    assert fake.call_log[-1][1] == "create_workunit"
    assert fake.call_log[-1][2] == ("WU1", False, None)


def test_create_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="create"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_create_workunit_is_non_idempotent(tools):
    fns, fake = tools
    fake.fail_times("project", "create_workunit", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_manage_workunit"](action="create", workunit_name="WU1"))
    assert r["code"] == "UNKNOWN_OUTCOME"


def test_delete_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "delete_workunit", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="delete", workunit_name="WU1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "delete_workunit"


def test_delete_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="delete"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_get_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_workunit", {"succeed": True, "data": "wu-uuid", "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="get", workunit_name="WU1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "get_workunit"


def test_get_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="get"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_save_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "save_workunit", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="save", workunit="wu-uuid"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "save_workunit"


def test_save_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="save"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_save_workunit_is_idempotent_write_not_unknown_outcome(tools):
    """saveはIDEMPOTENT_WRITE。infra失敗してもUNKNOWN_OUTCOMEにはならない"""
    fns, fake = tools
    fake.fail_times("project", "save_workunit", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_manage_workunit"](action="save", workunit="wu-uuid"))
    assert r["code"] != "UNKNOWN_OUTCOME"


def test_exclude_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "exclude_workunit", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="exclude", workunit="wu-uuid"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "exclude_workunit"


def test_exclude_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="exclude"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_include_workunit_success(tools):
    fns, fake = tools
    fake.set_handler("project", "include_workunit", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="include", workunit_name="WU1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "include_workunit"


def test_include_workunit_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="include"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_get_cuesheet_rootfolder_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_cuesheet_rootfolder", {"succeed": True, "data": "csf-1", "message": ""})
    r = json.loads(fns["atomcraft_manage_workunit"](action="get_cuesheet_rootfolder", workunit="wu-uuid"))
    assert r["success"] is True
    assert r["data"] == "csf-1"


def test_get_cuesheet_rootfolder_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="get_cuesheet_rootfolder"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_manage_workunit_unknown_action_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_workunit"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


# --- atomcraft_project_io ---

def test_project_create_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_project", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_project_io"](action="create",
                                                project_root_folder="C:/proj", project_name="MyProj"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_project"
    assert fake.call_log[-1][2] == ("C:/proj", "MyProj", False)


def test_project_create_missing_params(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_project_io"](action="create"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_project_create_is_non_idempotent(tools):
    fns, fake = tools
    fake.fail_times("project", "create_project", 1,
                    {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_project_io"](action="create",
                                                project_root_folder="C:/proj", project_name="MyProj"))
    assert r["code"] == "UNKNOWN_OUTCOME"


def test_project_open_success(tools):
    fns, fake = tools
    fake.set_handler("project", "open_project", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_project_io"](action="open", file_path="C:/proj/x.atmcproject"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "open_project"


def test_project_open_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_project_io"](action="open"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_project_save_all_success(tools):
    fns, fake = tools
    fake.set_handler("project", "save_project_all", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_project_io"](action="save_all"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "save_project_all"


def test_project_io_unknown_action_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_project_io"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"
