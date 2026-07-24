import json
from atomcraft_mcp.versioning import parse_version, normalize_version_data


def test_parse_version():
    assert parse_version("Ver.3.57.02") == (3, 57, 2)
    assert parse_version("3.41.01") == (3, 41, 1)   # "Ver."無し文字列も許容
    assert parse_version("") is None
    assert parse_version(None) is None


def test_normalize_version_data_shapes():
    assert normalize_version_data({"version": "Ver.3.57.02"}) == (3, 57, 2)
    assert normalize_version_data("3.41.01") == (3, 41, 1)
    assert normalize_version_data(None) is None
    assert normalize_version_data({"unexpected": 1}) is None


def test_require_feature_blocks_old_tool_version(transport_341):
    # fake: get_tool_version が旧バージョンを返す
    from atomcraft_mcp.versioning import require_feature
    err, fn = require_feature(transport_341, transport_341._robot.preview,
                              "get_playback_state", (3, 55, 0), "再生状態取得")
    assert fn is None
    payload = json.loads(err)
    assert payload["code"] == "UNSUPPORTED_VERSION"
    assert payload["details"]["required"] == "3.55.0"


def test_require_feature_blocks_missing_callable(transport_357_old_robot_python):
    # fake: ツールは新しいがrobot Python側に関数が無い(robot-path違い)
    from atomcraft_mcp.versioning import require_feature
    err, fn = require_feature(transport_357_old_robot_python,
                              transport_357_old_robot_python._robot.preview,
                              "get_playback_state", (3, 55, 0), "再生状態取得")
    assert fn is None
    payload = json.loads(err)
    assert payload["code"] == "UNSUPPORTED_VERSION"
    assert "robot" in payload["hint"].lower() or "ATOMCRAFT_ROBOT_PATH" in payload["hint"]


def test_require_feature_passes(transport_357):
    from atomcraft_mcp.versioning import require_feature
    err, fn = require_feature(transport_357, transport_357._robot.preview,
                              "get_playback_state", (3, 55, 0), "x")
    assert err is None and callable(fn)


def test_require_feature_fail_open_when_version_unknown(transport_version_error):
    # バージョン取得失敗時: 関数が存在すれば通す(実APIの封筒に任せる)
    from atomcraft_mcp.versioning import require_feature
    err, fn = require_feature(transport_version_error,
                              transport_version_error._robot.preview,
                              "get_playback_state", (3, 55, 0), "x")
    assert err is None and callable(fn)


def test_require_feature_blocks_noncallable_attribute(transport_357):
    """robot Python側の属性が存在してもcallableでなければゲートを通過させない。

    _FakeModule.__getattr__ は未登録の属性なら常に呼び出し可能なラムダを生成してしまうため、
    「存在するが呼び出せない」ケースはインスタンス属性を直接上書きして再現する。
    """
    from atomcraft_mcp.versioning import require_feature
    transport_357._robot.preview.get_playback_state = "not-a-function"
    err, fn = require_feature(transport_357, transport_357._robot.preview,
                              "get_playback_state", (3, 55, 0), "再生状態取得")
    assert fn is None
    payload = json.loads(err)
    assert payload["code"] == "UNSUPPORTED_VERSION"


def test_tool_version_cache_and_reset(transport_357):
    v1 = transport_357.tool_version()
    assert v1 == (3, 57, 2)
    transport_357.full_reset()
    assert transport_357._tool_version_cache is transport_357._UNSET  # リセットで再取得
