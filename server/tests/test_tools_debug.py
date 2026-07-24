import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.debug import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot, t


def test_ping_success(tools):
    fns, fake, t = tools
    fake.set_handler("debug", "ping", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_debug"](action="ping"))
    assert r["success"] is True
    assert r["message"] == "Connection alive"
    assert fake.call_log[-1][1] == "ping"


def test_ping_failure(tools):
    fns, fake, t = tools
    fake.set_handler("debug", "ping", {"succeed": False, "message": "not connected"})
    r = json.loads(fns["atomcraft_debug"](action="ping"))
    assert r["success"] is False


def test_log_success(tools):
    fns, fake, t = tools
    fake.set_handler("debug", "log", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_debug"](action="log", message="hello"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "log"
    assert fake.call_log[-1][2] == ("hello",)


def test_log_missing_message(tools):
    fns, _, _ = tools
    r = json.loads(fns["atomcraft_debug"](action="log"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_warning_missing_message(tools):
    fns, _, _ = tools
    r = json.loads(fns["atomcraft_debug"](action="warning"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_clear_log_success(tools):
    fns, fake, t = tools
    fake.set_handler("debug", "clear_log", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_debug"](action="clear_log"))
    assert r["success"] is True


def test_get_version_success(tools):
    fns, fake, t = tools
    fake.set_handler("debug", "get_tool_version", {"succeed": True, "data": "3.41.01", "message": ""})
    r = json.loads(fns["atomcraft_debug"](action="get_version"))
    assert r["success"] is True
    assert r["data"] == {"version": "3.41.01"}


def test_unknown_action(tools):
    fns, _, _ = tools
    r = json.loads(fns["atomcraft_debug"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


def test_status_shape(tools):
    fns, fake, t = tools
    r = json.loads(fns["atomcraft_debug"](action="status"))
    assert r["success"] is True
    data = r["data"]
    assert set(data.keys()) == {"host", "port", "initialized", "connected", "dll_status"}


def test_reconnect_success(tools):
    """full_reset -> connect -> ping の順で呼ばれ、成功メッセージが返る"""
    fns, fake, t = tools
    fake.set_handler("debug", "ping", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_debug"](action="reconnect"))
    assert r["success"] is True
    assert "Reconnected" in r["message"]
    # full_reset -> connectlib.finalize済み、その後connect()でinitialize/connectが呼ばれ、pingが呼ばれる
    assert fake.connectlib.initialized is True
    assert fake.connectlib.connected is True
    assert t._connected is True
    assert fake.call_log[-1] == ("debug", "ping", ())


def test_reconnect_connect_failure(tools):
    """connect失敗時はSERVER_UNREACHABLE + 復旧hint"""
    fns, fake, t = tools
    fake.connectlib.connect_result = 1
    r = json.loads(fns["atomcraft_debug"](action="reconnect"))
    assert r["success"] is False
    assert r["code"] == "SERVER_UNREACHABLE"
    assert "復旧手順" in r["hint"]


def test_reconnect_ping_failure_after_connect(tools):
    """connectは成功するがping確認に失敗した場合もSERVER_UNREACHABLE + 復旧hint"""
    fns, fake, t = tools
    fake.set_handler("debug", "ping", {"succeed": False, "message": "not connected"})
    r = json.loads(fns["atomcraft_debug"](action="reconnect"))
    assert r["success"] is False
    assert r["code"] == "SERVER_UNREACHABLE"
    assert "復旧手順" in r["hint"]
