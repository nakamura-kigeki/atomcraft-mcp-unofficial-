import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.build_preview import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


@pytest.fixture
def tools_341(transport_341):
    """接続先ツールが旧バージョン(Ver.3.41.01)のtools。新アクションのブロック確認用。"""
    fns = {f.__name__: f for f in make_tools(transport_341)}
    return fns, transport_341._robot


@pytest.fixture
def tools_disconnected(fake_robot):
    """接続自体が失敗するtools。引数検証が接続より先に走ることの確認用。"""
    fake_robot.connectlib.connect_result = -1
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


# --- atomcraft_build ---

def test_build_success(tools):
    fns, fake = tools
    fake.set_handler("build", "build_cuesheet", {"succeed": True, "data": "ok", "message": ""})
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "build_cuesheet"
    assert fake.call_log[-1][2] == ("cs1", "tgt1", None)


def test_build_missing_params(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_build"](action="build"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_build_clean_all_success(tools):
    fns, fake = tools
    fake.set_handler("build", "clean_all", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_build"](action="clean_all"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "clean_all"


def test_build_unknown_action(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_build"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


def test_build_timeout_sec_default_none_succeeds(tools):
    """timeout_secを省略した場合はNoneがtransportデフォルトとして使われ、成功する。"""
    fns, fake = tools
    fake.set_handler("build", "build_cuesheet", {"succeed": True, "data": "ok", "message": ""})
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1"))
    assert r["success"] is True


def test_build_timeout_sec_accepted(tools):
    """timeout_secを明示指定してもツールは受理し成功する（FakeRobot経由では実測できないため受理+成功のみ確認）。"""
    fns, fake = tools
    fake.set_handler("build", "build_cuesheet", {"succeed": True, "data": "ok", "message": ""})
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1", timeout_sec=5))
    assert r["success"] is True


def test_build_timeout_sec_zero_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1", timeout_sec=0))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_build_timeout_sec_negative_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1", timeout_sec=-5))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_build_timeout_sec_nan_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_build"](
        action="build", cuesheet="cs1", target="tgt1", timeout_sec=float("nan")))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_build_timeout_sec_inf_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_build"](
        action="build", cuesheet="cs1", target="tgt1", timeout_sec=float("inf")))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_build_timeout_sec_positive_still_accepted(tools):
    fns, fake = tools
    fake.set_handler("build", "build_cuesheet", {"succeed": True, "data": "ok", "message": ""})
    r = json.loads(fns["atomcraft_build"](
        action="build", cuesheet="cs1", target="tgt1", timeout_sec=5.5))
    assert r["success"] is True


def test_build_is_non_idempotent(tools):
    """buildは失敗時リトライされずUNKNOWN_OUTCOMEになる"""
    fns, fake = tools
    fake.fail_times("build", "build_cuesheet", 1, {"succeed": False, "message": "Failed to parse response"})
    r = json.loads(fns["atomcraft_build"](action="build", cuesheet="cs1", target="tgt1"))
    assert r["code"] == "UNKNOWN_OUTCOME"
    assert len([c for c in fake.call_log if c[1] == "build_cuesheet"]) == 1


# --- atomcraft_preview ---

def test_preview_play_success(tools):
    fns, fake = tools
    fake.set_handler("preview", "start_playback_cue", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_preview"](action="play", cue="cue1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "start_playback_cue"
    assert fake.call_log[-1][2] == ("cue1",)


def test_preview_play_missing_param(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_preview"](action="play"))
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_preview_stop_all_success(tools):
    fns, fake = tools
    fake.set_handler("preview", "stop_all", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_preview"](action="stop_all"))
    assert r["success"] is True


def test_preview_unknown_action(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_preview"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


# --- atomcraft_preview: get_playback_state / start_ingame_preview / stop_ingame_preview ---
# (Ver.3.47.0で追加。docs/api-versions.md参照)

def test_preview_get_playback_state_success(tools):
    fns, fake = tools
    fake.set_handler("preview", "get_playback_state",
                     {"succeed": True, "data": {"is_playing": True}, "message": ""})
    r = json.loads(fns["atomcraft_preview"](action="get_playback_state", cue="uuid-1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "get_playback_state"
    assert fake.call_log[-1][2] == ("uuid-1",)


def test_preview_get_playback_state_requires_cue(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_preview"](action="get_playback_state"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_preview_start_ingame_preview_success(tools):
    fns, fake = tools
    fake.set_handler("preview", "start_ingame_preview",
                     {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_preview"](
        action="start_ingame_preview", target="tgt1", ip_address="127.0.0.1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "start_ingame_preview"
    assert fake.call_log[-1][2] == ("tgt1", "127.0.0.1")


def test_preview_start_ingame_preview_requires_params(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_preview"](action="start_ingame_preview"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]


def test_preview_start_ingame_preview_requires_ip_address(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_preview"](action="start_ingame_preview", target="tgt1"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"


def test_preview_stop_ingame_preview_success(tools):
    fns, fake = tools
    fake.set_handler("preview", "stop_ingame_preview",
                     {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_preview"](action="stop_ingame_preview"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "stop_ingame_preview"
    assert fake.call_log[-1][2] == ()


def test_preview_new_actions_blocked_on_old_tool(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_preview"](action="get_playback_state", cue="uuid-1"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_preview_start_ingame_preview_blocked_on_old_tool(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_preview"](
        action="start_ingame_preview", target="tgt1", ip_address="127.0.0.1"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_preview_stop_ingame_preview_blocked_on_old_tool(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_preview"](action="stop_ingame_preview"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_preview_param_check_precedes_connection(tools_disconnected):
    """引数不足はバージョン取得・接続より先に返る(codex指摘12)。

    接続自体を失敗させたtransportで、引数不足のget_playback_stateを呼んでも
    接続が一切試行されず(call_logが空のまま)INVALID_PARAMSで即返ることを確認する。
    """
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_preview"](action="get_playback_state"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_preview_ingame_param_check_precedes_connection(tools_disconnected):
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_preview"](action="start_ingame_preview"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []
