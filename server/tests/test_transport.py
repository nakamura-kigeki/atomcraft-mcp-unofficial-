import time
import pytest
from atomcraft_mcp.transport import AtomCraftTransport, READ, NON_IDEMPOTENT
from atomcraft_mcp import config


@pytest.fixture
def transport(fake_robot):
    return AtomCraftTransport(fake_robot, config.load(env={}))


def test_auto_connect_on_first_call(transport, fake_robot):
    fake_robot.set_handler("debug", "ping", {"succeed": True, "data": None, "message": ""})
    result = transport.call(fake_robot.debug.ping, idempotency=READ)
    assert result["succeed"] is True
    assert fake_robot.connectlib.connected is True


def test_unreachable_when_connect_fails(transport, fake_robot):
    fake_robot.connectlib.connect_result = 1
    result = transport.call(fake_robot.debug.ping, idempotency=READ)
    assert result["succeed"] is False
    assert result["_code"] == "SERVER_UNREACHABLE"


def test_read_retries_once_on_parse_error(transport, fake_robot):
    fake_robot.set_handler("project", "get_value", {"succeed": True, "data": "x", "message": ""})
    fake_robot.fail_times("project", "get_value", 1,
                          {"succeed": False, "message": "Failed to parse response"})
    result = transport.call(fake_robot.project.get_value, "u1", "Name", idempotency=READ)
    assert result["succeed"] is True
    calls = [c for c in fake_robot.call_log if c[1] == "get_value"]
    assert len(calls) == 2  # 1回失敗 + 1回リトライ


def test_non_idempotent_never_retries(transport, fake_robot):
    fake_robot.set_handler("project", "create_object", {"succeed": True, "data": "u", "message": ""})
    fake_robot.fail_times("project", "create_object", 1,
                          {"succeed": False, "message": "Failed to parse response"})
    result = transport.call(fake_robot.project.create_object, "p", "Cue", "n",
                            idempotency=NON_IDEMPOTENT)
    assert result["succeed"] is False
    assert result["_code"] == "UNKNOWN_OUTCOME"
    calls = [c for c in fake_robot.call_log if c[1] == "create_object"]
    assert len(calls) == 1  # リトライしない


def test_business_error_no_retry_for_read(transport, fake_robot):
    fake_robot.set_handler("project", "get_value",
                           {"succeed": False, "message": "指定したフィールド [Pan] は利用できません。"})
    result = transport.call(fake_robot.project.get_value, "u1", "Pan", idempotency=READ)
    assert result["succeed"] is False
    calls = [c for c in fake_robot.call_log if c[1] == "get_value"]
    assert len(calls) == 1  # ビジネスエラーはリトライしない


def test_timeout_resets_and_reports(transport, fake_robot):
    def slow(*args):
        time.sleep(2)
        return {"succeed": True, "data": None, "message": ""}
    fake_robot.set_handler("debug", "ping", slow)
    result = transport.call(fake_robot.debug.ping, idempotency=NON_IDEMPOTENT, timeout=0.2)
    assert result["_code"] == "UNKNOWN_OUTCOME"
    assert fake_robot.connectlib.initialized is False or fake_robot.connectlib.connected is False


def test_non_dict_result_read_retries_and_non_idempotent_unknown(transport, fake_robot):
    """非dict応答はPARSE_ERROR扱い: READは1回リトライ、非冪等はUNKNOWN_OUTCOME"""
    calls = {"n": 0}

    def bad_then_good(*args):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 非dict
        return {"succeed": True, "data": "ok", "message": ""}
    fake_robot.set_handler("project", "get_value", bad_then_good)
    r = transport.call(fake_robot.project.get_value, "u", "Name", idempotency=READ)
    assert r["succeed"] is True and r["data"] == "ok"
    assert calls["n"] == 2

    fake_robot.set_handler("project", "create_object", lambda *a: None)
    r2 = transport.call(fake_robot.project.create_object, "p", "Cue", "n",
                        idempotency=NON_IDEMPOTENT)
    assert r2["_code"] == "UNKNOWN_OUTCOME"


def test_read_timeout_retries_once_after_full_reset(transport, fake_robot):
    """READのタイムアウトはfull_reset後に再接続して1回だけ再試行される"""
    import time as _time
    calls = {"n": 0}

    def slow_then_fast(*args):
        calls["n"] += 1
        if calls["n"] == 1:
            _time.sleep(1.0)
            return {"succeed": True, "data": "SLOW", "message": ""}
        return {"succeed": True, "data": "FAST", "message": ""}
    fake_robot.set_handler("project", "get_value", slow_then_fast)
    r = transport.call(fake_robot.project.get_value, "u", "Name",
                       idempotency=READ, timeout=0.2)
    assert r["succeed"] is True and r["data"] == "FAST"
    assert calls["n"] == 2
    assert fake_robot.connectlib.connected is True  # full_reset後に再接続済み


def test_stale_thread_result_discarded(transport, fake_robot):
    """呼び出し分離（holderのローカル性）を検証する。世代チェックは防御の二重化。
    タイムアウト後に旧スレッドが完了しても、その結果が次の呼び出しに混ざらないこと"""
    def slow_then_fast(*args):
        if len([c for c in fake_robot.call_log if c[1] == "get_value"]) == 1:
            time.sleep(1.0)
            return {"succeed": True, "data": "STALE", "message": ""}
        return {"succeed": True, "data": "FRESH", "message": ""}
    fake_robot.set_handler("project", "get_value", slow_then_fast)
    r1 = transport.call(fake_robot.project.get_value, "u", "Name", idempotency=READ, timeout=0.2)
    time.sleep(1.2)  # 旧スレッド完了を待つ
    r2 = transport.call(fake_robot.project.get_value, "u", "Name", idempotency=READ, timeout=5)
    assert r2["data"] == "FRESH"


def test_status_shape(transport, fake_robot):
    s = transport.status()
    assert set(s.keys()) == {"host", "port", "initialized", "connected", "dll_status"}


def test_tool_version_missing_attribute_fails_open(transport, fake_robot):
    """get_tool_version自体が存在しない旧robot Python(Ver.3.46.04未満)でも例外を出さず、
    取得失敗(None)としてfail-openになること(直接属性参照によるAttributeErrorの生漏れ防止)。"""
    fake_robot.set_missing("debug", "get_tool_version")
    assert transport.tool_version() is None
    # インフラ呼び出し自体が発生していないこと(属性チェックの時点で打ち切られる)
    assert all(c[1] != "get_tool_version" for c in fake_robot.call_log)
