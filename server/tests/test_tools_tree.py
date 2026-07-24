import csv
import json
import os
import tempfile
import time

import pytest

from atomcraft_mcp.config import Settings
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.tree import make_tools

DEFAULT_SETTINGS = Settings(
    host="127.0.0.1", port=9000, api_timeout=5.0,
    tree_json_budget=50000,
    output_base_dir=os.path.join(tempfile.gettempdir(), "atomcraft_mcp_test_tree"),
)


def _make_tools(fake_robot, settings=None):
    settings = settings or DEFAULT_SETTINGS
    t = AtomCraftTransport(fake_robot, settings)
    fns = {f.__name__: f for f in make_tools(t, settings)}
    return fns


@pytest.fixture
def tools(fake_robot):
    return _make_tools(fake_robot), fake_robot


def _setup_star_tree(fake, root="root", child_ids=None, child_type="Cue",
                      root_type="CueSheet", leaf_type="Cue"):
    """root -> child_idsの葉、というシンプルな星型ツリーのハンドラを設定する。"""
    child_ids = list(child_ids or [])

    def type_name(obj_id):
        t = root_type if obj_id == root else leaf_type
        return {"succeed": True, "data": t, "message": ""}

    def object_path(obj_id):
        return {"succeed": True, "data": f"/{obj_id}", "message": ""}

    def child_objects(obj_id, ctype):
        if obj_id == root and ctype == child_type:
            return {"succeed": True, "data": list(child_ids), "message": ""}
        return {"succeed": True, "data": [], "message": ""}

    def value(obj_id, field):
        return {"succeed": True, "data": f"{field}-{obj_id}", "message": ""}

    def values(obj_id, fields_list):
        return {"succeed": True, "data": {f: f"{f}-{obj_id}" for f in fields_list}, "message": ""}

    fake.set_handler("project", "get_type_name", type_name)
    fake.set_handler("project", "get_object_path", object_path)
    fake.set_handler("project", "get_child_objects", child_objects)
    fake.set_handler("project", "get_value", value)
    fake.set_handler("project", "get_values", values)


def test_json_within_budget_returns_tree_with_flags(tools):
    fns, fake = tools
    _setup_star_tree(fake, root="root", child_ids=["c1", "c2"])

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"]))

    assert r["success"] is True
    assert r["data"]["tree"]["type"] == "CueSheet"
    assert r["data"]["tree"]["child_count"] == 2
    assert r["data"]["timed_out"] is False
    assert r["data"]["truncated"] is False
    assert r["data"]["partial"] is False


def test_json_over_budget_auto_falls_back_to_csv(tmp_path, fake_robot):
    settings = Settings(host="127.0.0.1", port=9000, api_timeout=5.0,
                         tree_json_budget=1000, output_base_dir=str(tmp_path))
    fns = _make_tools(fake_robot, settings)

    n = 30
    child_ids = [f"c{i}" for i in range(n)]
    _setup_star_tree(fake_robot, root="root", child_ids=child_ids)

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"]))

    assert r["success"] is True
    assert r["data"]["auto_fallback"] is True
    assert r["data"]["csv_rows"] == n
    assert os.path.exists(r["data"]["csv_file"])
    assert os.path.exists(r["data"]["structure_file"])

    with open(r["data"]["csv_file"], newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) - 1 == n  # header + n data rows

    # フォールバック変換はAPIを再呼び出ししない:
    # root(meta2+prop1+children1=4) + n * (meta2+prop1+children1=4)
    expected_calls = 4 + n * 4
    assert len(fake_robot.call_log) == expected_calls


def test_max_children_truncation_flag(fake_robot):
    child_ids = [f"c{i}" for i in range(600)]
    _setup_star_tree(fake_robot, root="root", child_ids=child_ids, child_type="Track",
                      root_type="CueSheet", leaf_type="Track")
    fns = _make_tools(fake_robot)

    r = json.loads(fns["atomcraft_get_tree"](
        root="root", child_types=["Track"], max_depth=1, max_children=500))

    assert r["success"] is True
    assert r["data"]["truncated"] is True
    assert r["data"]["tree"]["child_count"] == 500


def test_output_dir_defaults_to_temp(tmp_path, fake_robot):
    settings = Settings(host="127.0.0.1", port=9000, api_timeout=5.0,
                         tree_json_budget=50000, output_base_dir=str(tmp_path))
    fns = _make_tools(fake_robot, settings)
    _setup_star_tree(fake_robot, root="root", child_ids=[])

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"], output_format="csv"))

    assert r["success"] is True
    assert os.path.commonpath([r["data"]["csv_file"], str(tmp_path)]) == str(tmp_path)
    assert os.path.exists(r["data"]["csv_file"])


def test_old_files_cleaned(tmp_path, fake_robot):
    settings = Settings(host="127.0.0.1", port=9000, api_timeout=5.0,
                         tree_json_budget=50000, output_base_dir=str(tmp_path))
    old_csv = tmp_path / "tree_data_19990101_000000.csv"
    old_csv.write_text("depth,type\n", encoding="utf-8")
    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_csv, (old_time, old_time))

    fns = _make_tools(fake_robot, settings)
    _setup_star_tree(fake_robot, root="root", child_ids=[])

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"], output_format="csv"))

    assert r["success"] is True
    assert not old_csv.exists()


def test_invalid_output_format_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"], output_format="xml"))

    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]
    assert len(fake.call_log) == 0


def test_explicit_output_dir_old_files_not_cleaned(tmp_path, fake_robot):
    """output_dirを明示指定した場合は、7日超の古いファイルがあっても削除しない
    (利用者指定の任意ディレクトリでのファイル削除という副作用を除去するため)。
    settings.output_base_dirはoutput_dirとは別の場所にして、既定ディレクトリ経由でない
    ことを明確にする。"""
    settings = Settings(
        host="127.0.0.1", port=9000, api_timeout=5.0, tree_json_budget=50000,
        output_base_dir=os.path.join(tempfile.gettempdir(), "atomcraft_mcp_test_tree_unused"))
    old_csv = tmp_path / "tree_data_19990101_000000.csv"
    old_csv.write_text("depth,type\n", encoding="utf-8")
    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_csv, (old_time, old_time))

    fns = _make_tools(fake_robot, settings)
    _setup_star_tree(fake_robot, root="root", child_ids=[])

    r = json.loads(fns["atomcraft_get_tree"](
        root="root", child_types=["Cue"], output_format="csv", output_dir=str(tmp_path)))

    assert r["success"] is True
    assert old_csv.exists()  # 明示指定ディレクトリでは削除されない


def test_json_auto_fallback_explicit_output_dir_old_files_not_cleaned(tmp_path, fake_robot):
    """JSON予算超過による自動CSVフォールバック経路(output_format省略時のjson→csv
    自動切替)でも、output_dirを明示指定した場合は7日超の古いファイルを削除しない。
    explicit output_format="csv"経路(test_explicit_output_dir_old_files_not_cleaned)
    と同じ保証を、auto_fallback経路でも担保することを確認する。"""
    settings = Settings(
        host="127.0.0.1", port=9000, api_timeout=5.0, tree_json_budget=1000,
        output_base_dir=os.path.join(tempfile.gettempdir(), "atomcraft_mcp_test_tree_unused2"))
    old_csv = tmp_path / "tree_data_19990101_000000.csv"
    old_csv.write_text("depth,type\n", encoding="utf-8")
    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_csv, (old_time, old_time))

    fns = _make_tools(fake_robot, settings)
    n = 30
    child_ids = [f"c{i}" for i in range(n)]
    _setup_star_tree(fake_robot, root="root", child_ids=child_ids)

    r = json.loads(fns["atomcraft_get_tree"](
        root="root", child_types=["Cue"], output_dir=str(tmp_path)))

    assert r["success"] is True
    assert r["data"]["auto_fallback"] is True
    assert old_csv.exists()  # 明示指定ディレクトリでは自動フォールバック時も削除されない


def test_invalid_max_depth_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"], max_depth=999))

    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]
    assert len(fake.call_log) == 0


def test_invalid_max_children_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"], max_children=0))

    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert len(fake.call_log) == 0


def test_csv_explicit_mode_writes_structure_and_data(tmp_path, fake_robot):
    _setup_star_tree(fake_robot, root="root", child_ids=["c1", "c2"])
    fns = _make_tools(fake_robot)

    r = json.loads(fns["atomcraft_get_tree"](
        root="root", child_types=["Cue"], output_format="csv", output_dir=str(tmp_path)))

    assert r["success"] is True
    data = r["data"]
    for key in ("csv_file", "structure_file", "csv_rows", "csv_columns", "structure",
                "timed_out", "truncated", "partial"):
        assert key in data
    assert data["csv_rows"] == 2
    assert data["structure"]["type"] == "CueSheet"
    assert data["structure"]["leaf_count"] == 2
    assert os.path.exists(data["csv_file"])
    assert os.path.exists(data["structure_file"])
    with open(data["csv_file"], newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


def test_timeout_mid_traversal_sets_timed_out_and_partial(tools):
    """走査中盤でget_child_objectsがTIMEOUTを返したら、timed_out/partialが立ち、
    それ以降のget_child_objects呼び出しが発生しない（=打ち切りが機能している）ことを確認する。"""
    fns, fake = tools
    root = "root"
    calls = {"n": 0}

    def type_name(obj_id):
        return {"succeed": True, "data": "CueSheet" if obj_id == root else "Cue", "message": ""}

    def object_path(obj_id):
        return {"succeed": True, "data": f"/{obj_id}", "message": ""}

    def child_objects(obj_id, ctype):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"succeed": True, "data": ["c1", "c2"], "message": ""}
        return {"succeed": False, "message": "timed out", "_code": "TIMEOUT"}

    def value(obj_id, field):
        return {"succeed": True, "data": f"{field}-{obj_id}", "message": ""}

    fake.set_handler("project", "get_type_name", type_name)
    fake.set_handler("project", "get_object_path", object_path)
    fake.set_handler("project", "get_child_objects", child_objects)
    fake.set_handler("project", "get_value", value)

    r = json.loads(fns["atomcraft_get_tree"](root=root, child_types=["Cue"]))

    assert r["success"] is True
    assert r["data"]["timed_out"] is True
    assert r["data"]["partial"] is True

    # transport.call()はREAD冪等性のインフラ失敗を1回だけ自動リトライするため、
    # c1向けget_child_objectsは(初回+リトライ)の2回ディスパッチされる。
    # 重要なのは c2 に対する get_child_objects が一切発生しない(=打ち切りが機能)こと。
    child_call_ids = [c[2][0] for c in fake.call_log if c[1] == "get_child_objects"]
    assert child_call_ids == ["root", "c1", "c1"]


def test_first_call_infra_failure_returns_error_not_success(tools):
    """走査の最初のAPI呼び出しの時点でAtom Craft未接続（SERVER_UNREACHABLE）の場合、
    空スタブでsuccess:trueを返さず、エラー封筒（code/hint/retryable付き）を返す。
    transportは接続自体に失敗するとfunc呼び出し前にSERVER_UNREACHABLEを返す
    （_attempt/リトライを経由しないため、この形が最も現実に即したシミュレーション）。"""
    fns, fake = tools
    fake.connectlib.connect_result = 1  # Atom Craft未起動/スクリプトサーバー未起動を模す

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"]))

    assert r["success"] is False
    assert r["code"] == "SERVER_UNREACHABLE"
    assert r["hint"]
    assert r["retryable"] is False
    assert len(fake.call_log) == 0  # connect失敗時はfunc呼び出しに到達しない


def test_connection_lost_mid_traversal_sets_partial_not_timed_out(tools):
    """CONNECTION_LOSTはTIMEOUTと区別する: partialは立つがtimed_outは立てず、
    メッセージにインフラエラーの種別(CONNECTION_LOST)が含まれることを確認する。"""
    fns, fake = tools
    root = "root"
    calls = {"n": 0}

    def type_name(obj_id):
        return {"succeed": True, "data": "CueSheet" if obj_id == root else "Cue", "message": ""}

    def object_path(obj_id):
        return {"succeed": True, "data": f"/{obj_id}", "message": ""}

    def child_objects(obj_id, ctype):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"succeed": True, "data": ["c1", "c2"], "message": ""}
        return {"succeed": False, "message": "connection lost", "_code": "CONNECTION_LOST"}

    def value(obj_id, field):
        return {"succeed": True, "data": f"{field}-{obj_id}", "message": ""}

    fake.set_handler("project", "get_type_name", type_name)
    fake.set_handler("project", "get_object_path", object_path)
    fake.set_handler("project", "get_child_objects", child_objects)
    fake.set_handler("project", "get_value", value)

    r = json.loads(fns["atomcraft_get_tree"](root=root, child_types=["Cue"]))

    assert r["success"] is True
    assert r["data"]["timed_out"] is False
    assert r["data"]["partial"] is True
    assert "CONNECTION_LOST" in r["message"]

    # transport.call()はREAD冪等性のインフラ失敗を1回だけ自動リトライするため、
    # c1向けget_child_objectsは(初回+リトライ)の2回ディスパッチされる。
    # 重要なのは c2 に対する get_child_objects が一切発生しない(=打ち切りが機能)こと。
    child_call_ids = [c[2][0] for c in fake.call_log if c[1] == "get_child_objects"]
    assert child_call_ids == ["root", "c1", "c1"]


def test_csv_first_call_infra_failure_returns_error_not_success(tmp_path, fake_robot):
    """CSVモードで走査の最初のAPI呼び出しの時点でAtom Craft未接続（SERVER_UNREACHABLE）の場合、
    空スタブでsuccess:trueを返さず、エラー封筒（code/hint/retryable付き）を返す。
    またCSVファイルも作成されない。"""
    settings = Settings(host="127.0.0.1", port=9000, api_timeout=5.0,
                        tree_json_budget=50000, output_base_dir=str(tmp_path))
    fns = _make_tools(fake_robot, settings)
    fake_robot.connectlib.connect_result = 1  # Atom Craft未起動/スクリプトサーバー未起動を模す

    r = json.loads(fns["atomcraft_get_tree"](root="root", child_types=["Cue"],
                                              output_format="csv", output_dir=str(tmp_path)))

    assert r["success"] is False
    assert r["code"] == "SERVER_UNREACHABLE"
    assert r["hint"]
    assert r["retryable"] is False
    assert len(fake_robot.call_log) == 0  # connect失敗時はfunc呼び出しに到達しない

    # CSVファイルが作成されていないことを確認
    csv_files = list(tmp_path.glob("tree_data_*.csv"))
    assert len(csv_files) == 0
