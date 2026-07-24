import json
import pytest
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools.properties import make_tools
from atomcraft_mcp import config


@pytest.fixture
def tools(fake_robot):
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fake_robot.set_handler("project", "get_object_path", {"succeed": True, "data": "/WU/S1/c1", "message": ""})
    fake_robot.set_handler("project", "get_type_name", {"succeed": True, "data": "Cue", "message": ""})
    fake_robot.set_handler("project", "get_color", {"succeed": True, "data": None, "message": ""})
    return {f.__name__: f for f in make_tools(t)}, fake_robot


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
def tools_missing_get_value_from_targets(fake_robot):
    """接続先ツールは新しい(Ver.3.57.02)が、robot-pathが指すPython側には
    get_value_from_targets が存在しない(旧robot Pythonを指しているケース)を再現する。

    conftest.py の transport_357_old_robot_python と同じパターンを、
    project.get_value_from_targets 向けに流用したもの。
    """
    fake_robot.set_missing("project", "get_value_from_targets")
    fake_robot.set_handler("debug", "get_tool_version",
                           {"succeed": True, "data": {"version": "Ver.3.57.02"}, "message": ""})
    t = AtomCraftTransport(fake_robot, config.load(env={}))
    fns = {f.__name__: f for f in make_tools(t)}
    return fns, fake_robot


def test_partial_success_on_invalid_field(tools):
    """無効フィールド混在→自動除外して取れた分を返す（投げなおし根絶の本丸）"""
    fns, fake = tools

    def get_values(target, fields):
        if "Category" in fields:
            return {"succeed": False,
                    "message": "指定したフィールド [Category] は利用できません。"}
        return {"succeed": True, "data": {f: f"v_{f}" for f in fields}, "message": ""}
    fake.set_handler("project", "get_values", get_values)

    r = json.loads(fns["atomcraft_get_property"](target="u1",
                                                 fields=["Name", "Category", "Volume"]))
    assert r["success"] is True
    assert r["data"]["properties"] == {"Name": "v_Name", "Volume": "v_Volume"}
    assert r["data"]["invalid_fields"] == ["Category"]
    assert any("Category" in w for w in r["warnings"])


def test_all_fields_invalid_returns_error_with_catalog_hint(tools):
    fns, fake = tools

    def get_values(target, fields):
        return {"succeed": False,
                "message": f"指定したフィールド [{fields[0]}] は利用できません。"}
    fake.set_handler("project", "get_values", get_values)
    fake.set_handler("project", "get_value",
                     {"succeed": False, "message": "指定したフィールド [Pan] は利用できません。"})

    r = json.loads(fns["atomcraft_get_property"](target="u1", fields=["Pan", "Categn"]))
    assert r["success"] is False
    assert r["code"] == "INVALID_FIELD"
    assert "CueID" in r["hint"]  # Cueの有効フィールド一覧を提示(先頭12件までに切り詰め)
    assert "ほか" in r["hint"]  # 切り詰めた残数を伝える


def test_single_field_success(tools):
    fns, fake = tools
    fake.set_handler("project", "get_value", {"succeed": True, "data": "attack_a", "message": ""})
    r = json.loads(fns["atomcraft_get_property"](target="u1", fields=["Name"]))
    assert r["data"]["properties"] == {"Name": "attack_a"}


def test_single_field_invalid_returns_error_with_catalog_hint(tools):
    """単一フィールド指定でも無効なら部分成功にならずエラー（全滅と同じ扱い）"""
    fns, fake = tools
    fake.set_handler("project", "get_value",
                     {"succeed": False, "message": "指定したフィールド [Pan] は利用できません。"})
    r = json.loads(fns["atomcraft_get_property"](target="u1", fields=["Pan"]))
    assert r["success"] is False
    assert r["code"] == "INVALID_FIELD"
    assert "CueID" in r["hint"]


def test_use_actual_value_partial_success(tools):
    """use_actual_value=True でも1件ずつのINVALID_FIELDはinvalid_fieldsに集めて続行する"""
    fns, fake = tools

    def get_actual_value(target, field, target_config):
        if field == "Category":
            return {"succeed": False,
                    "message": "指定したフィールド [Category] は利用できません。"}
        return {"succeed": True, "data": f"v_{field}", "message": ""}
    fake.set_handler("project", "get_actual_value", get_actual_value)

    r = json.loads(fns["atomcraft_get_property"](target="u1",
                                                 fields=["Name", "Category", "Volume"],
                                                 use_actual_value=True))
    assert r["success"] is True
    assert r["data"]["properties"] == {"Name": "v_Name", "Volume": "v_Volume"}
    assert r["data"]["invalid_fields"] == ["Category"]


def test_set_property_is_idempotent_write(tools):
    fns, fake = tools
    fake.set_handler("project", "set_values", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_set_property"](target="u1", properties={"Volume": "0.8"}))
    assert r["success"] is True


def test_set_property_color_unset(tools):
    fns, fake = tools
    fake.set_handler("project", "unset_color", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_set_property"](target="u1", color="unset"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "unset_color"


def test_manage_category_get(tools):
    fns, fake = tools
    fake.set_handler("project", "get_categories", {"succeed": True, "data": ["c1", "c2"], "message": ""})
    r = json.loads(fns["atomcraft_manage_category"](action="get", cue="u1"))
    assert r["success"] is True
    assert r["data"]["category_ids"] == ["c1", "c2"]
    assert fake.call_log[-1][1] == "get_categories"


def test_manage_category_set(tools):
    fns, fake = tools
    fake.set_handler("project", "set_categories", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_category"](action="set", cue="u1", category_list=["c1"]))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "set_categories"


def test_manage_category_add(tools):
    fns, fake = tools
    fake.set_handler("project", "add_category_to_cues", {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_manage_category"](action="add", cue_list=["u1", "u2"], category="c1"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "add_category_to_cues"


def test_manage_category_unknown_action_rejected(tools):
    fns, _ = tools
    r = json.loads(fns["atomcraft_manage_category"](action="explode"))
    assert r["code"] == "INVALID_PARAMS"


def test_partial_success_over_multiple_exclusion_rounds(tools):
    """複数の無効フィールドが1個ずつ報告されても、除外を重ねて最終的に成功する"""
    fns, fake = tools

    def get_values(target, fields):
        if "Categn" in fields:
            return {"succeed": False,
                    "message": "指定したフィールド [Categn] は利用できません。"}
        if "LoopType" in fields:
            return {"succeed": False,
                    "message": "指定したフィールド [LoopType] は利用できません。"}
        return {"succeed": True, "data": {f: f"v_{f}" for f in fields}, "message": ""}
    fake.set_handler("project", "get_values", get_values)

    r = json.loads(fns["atomcraft_get_property"](
        target="u1", fields=["Name", "Categn", "Volume", "LoopType"]))
    assert r["success"] is True
    assert r["data"]["properties"] == {"Name": "v_Name", "Volume": "v_Volume"}
    assert sorted(r["data"]["invalid_fields"]) == ["Categn", "LoopType"]


def test_no_progress_round_fails_fast(tools):
    """除外が進まない想定外メッセージ（remainingに含まれないフィールド名）では
    同一呼び出しを繰り返さない"""
    fns, fake = tools

    def get_values(target, fields):
        return {"succeed": False,
                "message": "指定したフィールド [Nonexistent] は利用できません。"}
    fake.set_handler("project", "get_values", get_values)

    r = json.loads(fns["atomcraft_get_property"](target="u1", fields=["Category", "Pan"]))
    assert r["success"] is False
    calls = [c for c in fake.call_log if c[1] == "get_values"]
    assert len(calls) == 1  # 空回りしない


def test_multi_field_bracket_partial_success(tools):
    """[Category, Pan] のように複数フィールドが1メッセージの角括弧にまとめて
    列挙されても、split後は両方を除外し、残りのフィールドは部分成功として返る"""
    fns, fake = tools

    def get_values(target, fields):
        bad_present = [f for f in ("Category", "Pan") if f in fields]
        if bad_present:
            return {"succeed": False,
                    "message": f"指定したフィールド [{', '.join(bad_present)}] は利用できません。"}
        return {"succeed": True, "data": {f: f"v_{f}" for f in fields}, "message": ""}
    fake.set_handler("project", "get_values", get_values)

    r = json.loads(fns["atomcraft_get_property"](
        target="u1", fields=["Name", "Category", "Pan"]))
    assert r["success"] is True
    assert r["data"]["properties"] == {"Name": "v_Name"}
    assert sorted(r["data"]["invalid_fields"]) == ["Category", "Pan"]


# --- atomcraft_bulk_property ---

def test_bulk_property_get_is_disabled_without_server_call(tools):
    """action=get は意図的な無効化(Ver.3.57.02実機で、リモート経由の
    get_value_from_targets が応答解析失敗→接続断を起こすことを確認済み)。
    サーバーを一切呼ばず、代替手段(get_property)を案内するエラー封筒を返す。"""
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](
        action="get", targets=["u1", "u2"], field_names=["Volume"]))
    assert r["success"] is False
    assert r["code"] == "API_ERROR"
    assert "無効化" in r["error"]
    assert "get_property" in r["hint"]
    assert fake.call_log == []


def test_bulk_property_set_success(tools):
    fns, fake = tools
    fake.set_handler("project", "set_value_to_targets",
                     {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1", "u2"], field_name="Volume", value="0.8"))
    assert r["success"] is True
    assert fake.call_log[-1][1] == "set_value_to_targets"
    assert fake.call_log[-1][2] == (["u1", "u2"], "Volume", "0.8")


def test_bulk_property_set_value_zero_string_is_valid(tools):
    """value="0"は偽値的な文字列だがNoneではないため有効
    (Robot APIがstr(value)する仕様上、"0"も正当な値として送られる)"""
    fns, fake = tools
    fake.set_handler("project", "set_value_to_targets",
                     {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], field_name="Volume", value="0"))
    assert r["success"] is True
    assert fake.call_log[-1][2] == (["u1"], "Volume", "0")


def test_bulk_property_set_value_false_string_is_valid(tools):
    """value="false"も同様に偽値的だが有効な文字列値として扱う"""
    fns, fake = tools
    fake.set_handler("project", "set_value_to_targets",
                     {"succeed": True, "data": None, "message": ""})
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], field_name="Mute", value="false"))
    assert r["success"] is True
    assert fake.call_log[-1][2] == (["u1"], "Mute", "false")


def test_bulk_property_targets_empty_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](
        action="get", targets=[], field_names=["Volume"]))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert r["hint"]
    assert fake.call_log == []


def test_bulk_property_get_missing_field_names_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](action="get", targets=["u1"]))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_bulk_property_set_missing_value_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], field_name="Volume"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_bulk_property_set_missing_field_name_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], value="0.8"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_bulk_property_unknown_action_rejected(tools):
    fns, fake = tools
    r = json.loads(fns["atomcraft_bulk_property"](action="explode", targets=["u1"]))
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


# --- バージョンゲート ---

def test_bulk_property_get_disabled_even_on_old_tool_version(tools_341):
    """getの無効化はバージョンに関係なく最優先で返る(接続もバージョン取得も発生しない)"""
    fns, fake = tools_341
    r = json.loads(fns["atomcraft_bulk_property"](
        action="get", targets=["u1"], field_names=["Volume"]))
    assert r["success"] is False
    assert r["code"] == "API_ERROR"
    assert "無効化" in r["error"]


def test_bulk_property_set_blocked_on_old_tool_version(tools_341):
    fns, _ = tools_341
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], field_name="Volume", value="0.8"))
    assert r["success"] is False
    assert r["code"] == "UNSUPPORTED_VERSION"


def test_bulk_property_get_disabled_when_callable_missing(tools_missing_get_value_from_targets):
    """robot Python側に関数が無い場合も、getの無効化エラーが先に返る
    (require_featureまで到達しない)。"""
    fns, fake = tools_missing_get_value_from_targets
    r = json.loads(fns["atomcraft_bulk_property"](
        action="get", targets=["u1"], field_names=["Volume"]))
    assert r["success"] is False
    assert r["code"] == "API_ERROR"
    assert "無効化" in r["error"]
    assert fake.call_log == []


# --- 引数検証が接続より先行 ---

def test_bulk_property_get_param_check_precedes_connection(tools_disconnected):
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_bulk_property"](
        action="get", targets=[], field_names=["Volume"]))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []


def test_bulk_property_set_param_check_precedes_connection(tools_disconnected):
    fns, fake = tools_disconnected
    r = json.loads(fns["atomcraft_bulk_property"](
        action="set", targets=["u1"], field_name="Volume"))
    assert r["success"] is False
    assert r["code"] == "INVALID_PARAMS"
    assert fake.call_log == []
