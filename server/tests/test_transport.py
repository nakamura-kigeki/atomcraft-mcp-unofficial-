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


# --- DLL呼び出しの直列化(_call_lock) ---
# DLLはスレッドセーフではなく、FastMCPは同期関数のツールをスレッドプールで並行実行する。
# ツールが並列に呼ばれても、DLLに同時に入る呼び出しが常に1つであることを保証する。

import threading


def test_concurrent_calls_never_overlap_in_dll(transport, fake_robot):
    state = {"active": 0, "max_active": 0}
    guard = threading.Lock()

    def tracked(*args):
        with guard:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        with guard:
            state["active"] -= 1
        return {"succeed": True, "data": "x", "message": ""}

    fake_robot.set_handler("project", "get_value", tracked)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(
            transport.call(fake_robot.project.get_value, "u", "Name", idempotency=READ)))
        for _ in range(8)
    ]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=10)
    assert not any(th.is_alive() for th in threads)
    assert len(results) == 8 and all(r["succeed"] for r in results)
    assert state["max_active"] == 1


def test_timeout_releases_lock_for_waiting_call(transport, fake_robot):
    """先行呼び出しがタイムアウトしても、待っていた別スレッドの呼び出しが固まらない。"""
    first_started = threading.Event()

    def slow_then_fast(*args):
        if not first_started.is_set():
            first_started.set()
            time.sleep(1.0)  # timeout(0.2)を超えて居座る(停止できないDLL呼び出しの再現)
        return {"succeed": True, "data": None, "message": ""}

    fake_robot.set_handler("debug", "ping", slow_then_fast)
    out = {}
    a = threading.Thread(target=lambda: out.__setitem__("a", transport.call(
        fake_robot.debug.ping, idempotency=NON_IDEMPOTENT, timeout=0.2)))
    a.start()
    assert first_started.wait(timeout=5)
    b = threading.Thread(target=lambda: out.__setitem__("b", transport.call(
        fake_robot.debug.ping, idempotency=READ, timeout=2)))
    b.start()
    a.join(timeout=5)
    b.join(timeout=5)
    assert not a.is_alive() and not b.is_alive()
    assert out["a"]["_code"] == "UNKNOWN_OUTCOME"
    assert out["b"]["succeed"] is True


def test_finalize_does_not_hang_when_lock_is_held(transport, fake_robot, monkeypatch):
    """終了処理(atexit)は、ロックが握られたままでも上限時間内に戻る。"""
    import atomcraft_mcp.transport as tr
    monkeypatch.setattr(tr, "_FINALIZE_LOCK_TIMEOUT", 0.2)
    transport.connect()
    holding, release = threading.Event(), threading.Event()

    def hold():
        with transport._call_lock:
            holding.set()
            release.wait(timeout=5)

    h = threading.Thread(target=hold)
    h.start()
    assert holding.wait(timeout=5)
    t0 = time.monotonic()
    transport.finalize()
    elapsed = time.monotonic() - t0
    release.set()
    h.join(timeout=5)
    assert elapsed < 2
    assert fake_robot.connectlib.connected is False  # ロックが取れなくても切断は試みる


def test_status_returns_quickly_and_keeps_shape_while_busy(transport, fake_robot, monkeypatch):
    """他の呼び出しの実行中でも status はすぐ返り、応答のキー構成は変わらない。"""
    import atomcraft_mcp.transport as tr
    monkeypatch.setattr(tr, "_STATUS_LOCK_TIMEOUT", 0.1)
    holding, release = threading.Event(), threading.Event()

    def hold():
        with transport._call_lock:
            holding.set()
            release.wait(timeout=5)

    h = threading.Thread(target=hold)
    h.start()
    assert holding.wait(timeout=5)
    t0 = time.monotonic()
    s = transport.status()
    elapsed = time.monotonic() - t0
    release.set()
    h.join(timeout=5)
    assert elapsed < 1
    assert set(s.keys()) == {"host", "port", "initialized", "connected", "dll_status"}
    assert s["dll_status"] is None
    # ロックが空いていれば通常どおりDLLの状態を返す
    assert transport.status()["dll_status"] == fake_robot.connectlib.status_value
