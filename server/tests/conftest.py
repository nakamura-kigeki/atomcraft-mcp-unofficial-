import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_robot import FakeRobot
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp import config


@pytest.fixture(autouse=True)
def _isolate_robot_path_env(monkeypatch, tmp_path):
    """robot-path 解決テストを実行マシンの環境から隔離する。

    利用者には ATOMCRAFT_ROBOT_PATH の設定を推奨しているため、開発者マシン上で
    このテストスイートを実行すると環境変数や %USERPROFILE%\\.atomcraft-mcp\\
    robot-path.txt の有無に結果が左右されうる。テスト内で個別に setenv する
    ケース(test_robot_path.py 等)はこのフィクスチャの後に上書きするため影響しない。
    """
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "isolated-userprofile"))


@pytest.fixture
def fake_robot():
    return FakeRobot()


def _make_transport(fake, tool_version_response):
    fake.set_handler("debug", "get_tool_version", tool_version_response)
    return AtomCraftTransport(fake, config.load(env={}))


@pytest.fixture
def transport_341(fake_robot):
    """接続先ツールが旧バージョン(Ver.3.41.01)を返すtransport。文字列形状のdata。"""
    return _make_transport(fake_robot,
                           {"succeed": True, "data": "3.41.01", "message": ""})


@pytest.fixture
def transport_357(fake_robot):
    """接続先ツールが新バージョン(Ver.3.57.02)を返すtransport。辞書形状のdata。
    robot Python側の関数は全て揃っている(missing_functions未登録)。"""
    return _make_transport(fake_robot,
                           {"succeed": True, "data": {"version": "Ver.3.57.02"}, "message": ""})


@pytest.fixture
def transport_357_old_robot_python(fake_robot):
    """接続先ツールは新しい(Ver.3.57.02)が、robot-pathが指すPython側には
    get_playback_state が存在しない(旧robot Pythonを指しているケース)を再現する。"""
    fake_robot.set_missing("preview", "get_playback_state")
    return _make_transport(fake_robot,
                           {"succeed": True, "data": {"version": "Ver.3.57.02"}, "message": ""})


@pytest.fixture
def transport_version_error(fake_robot):
    """get_tool_version自体が失敗し、バージョンを取得できないtransport(fail-open検証用)。

    メッセージは接続系パターン(CONNECTION_LOST等)に分類されない文言にし、
    READのリトライ(sleep込み)が発生しないようにしている。
    """
    return _make_transport(fake_robot,
                           {"succeed": False, "message": "internal tool error", "data": None})
