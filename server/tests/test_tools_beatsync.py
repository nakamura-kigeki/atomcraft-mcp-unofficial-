import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.beatsync import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


@pytest.fixture
def tools_341(transport_341):
    """接続先ツールが旧バージョン(Ver.3.41.01)のtools。バージョン下限ブロック確認用。"""
    fns = {f.__name__: f for f in make_tools(transport_341)}
    return fns, transport_341._robot


@pytest.fixture
def tools_disconnected(fake_robot):
    """接続自体が失敗するtools。引数検証が接続より先に走ることの確認用。"""
    fake_robot.connectlib.connect_result = -1
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


@pytest.fixture
def tools_missing_create_beatsync_track(fake_robot):
    """接続先ツールは新しい(Ver.3.57.02)が、robot-pathが指すPython側には
    create_beatsync_track が存在しない(旧robot Pythonを指しているケース)を再現する。

    conftest.py の transport_357_old_robot_python と同じパターンを、
    project.create_beatsync_track 向けに流用したもの。
    """
    fake_robot.set_missing("project", "create_beatsync_track")
    fake_robot.set_handler("debug", "get_tool_version",
                           {"succeed": True, "data": {"version": "Ver.3.57.02"}, "message": ""})
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


# --- atomcraft_manage_beatsync: create_track ---

def test_beatsync_create_track_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_beatsync_track",
                     {"succeed": True, "data": "uuid-track1", "message": ""})
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create_track", parent="parent1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_beatsync_track"
    assert fake.call_log[-1][2] == ("parent1", None)


def test_beatsync_create_track_with_label(tools):
    fns, fake = tools
    fake.set_handler("project", "create_beatsync_track",
                     {"succeed": True, "data": "uuid-track1", "message": ""})
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create_track", parent="parent1", label="MyBeat"))
    assert r["success"] is True
    assert fake.call_log[-1][2] == ("parent1", "MyBeat")


def test_beatsync_create_track_missing_parent(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create_track", parent=""))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]
    assert fake.call_log == []


# --- atomcraft_manage_beatsync: create ---

def test_beatsync_create_success(tools):
    fns, fake = tools
    fake.set_handler("project", "create_beatsync",
                     {"succeed": True, "data": "uuid-beat1", "message": ""})
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "create_beatsync"
    assert fake.call_log[-1][2] == ("track1", 1000, 120.0, 4, [], None)


def test_beatsync_create_with_all_params(tools):
    fns, fake = tools
    fake.set_handler("project", "create_beatsync",
                     {"succeed": True, "data": "uuid-beat1", "message": ""})
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=2000, bpm=140.0, numerator=3,
        beat_pattern=["strong", "weak", "weak"], label="Verse"))
    assert r["success"] is True
    assert fake.call_log[-1][2] == (
        "track1", 2000, 140.0, 3, ["strong", "weak", "weak"], "Verse")


def test_beatsync_create_missing_parent(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create", parent="", time_ms=1000))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_missing_time_ms(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create", parent="track1"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]
    assert fake.call_log == []


def test_beatsync_create_negative_time_ms(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=-1))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_zero_time_ms_is_valid(tools):
    """time_ms=0は配置時刻としてゼロ相当であり許容される(>= 0の境界確認)。"""
    fns, fake = tools
    fake.set_handler("project", "create_beatsync",
                     {"succeed": True, "data": "uuid-beat1", "message": ""})
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=0))
    assert r["success"] is True


def test_beatsync_create_bpm_zero_invalid(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000, bpm=0))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_bpm_negative_invalid(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000, bpm=-10.0))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_numerator_zero_invalid(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000, numerator=0))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_numerator_negative_invalid(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000, numerator=-1))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


# --- unknown action ---

def test_beatsync_unknown_action(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_beatsync"](action="explode", parent="p1"))
    assert r["code"] == "INVALID_PARAMS"


# --- バージョンゲート ---

def test_beatsync_create_track_blocked_on_old_tool_version(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create_track", parent="parent1"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_beatsync_create_blocked_on_old_tool_version(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_manage_beatsync"](
        action="create", parent="track1", time_ms=1000))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_beatsync_create_track_blocked_when_callable_missing(tools_missing_create_beatsync_track):
    """接続先ツールのバージョンは新しくても、robot Python側に
    create_beatsync_track が存在しない場合はUNSUPPORTED_VERSIONで返る
    (callable_missing経路)。"""
    fns, fake = tools_missing_create_beatsync_track
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create_track", parent="parent1"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"
    assert "ATOMCRAFT_ROBOT_PATH" in r["hint"] or "robot" in r["hint"].lower()


# --- 引数検証が接続より先行 ---

def test_beatsync_create_track_param_check_precedes_connection(tools_disconnected):
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create_track", parent=""))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_beatsync_create_param_check_precedes_connection(tools_disconnected):
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_manage_beatsync"](action="create", parent="track1"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []
