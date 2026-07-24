import os
import pytest
from atomcraft_mcp.robot import resolve_robot_path, RobotPathError

def test_env_var_wins(tmp_path, monkeypatch):
    p = tmp_path / "robot_python"; p.mkdir()
    monkeypatch.setenv("ATOMCRAFT_ROBOT_PATH", str(p))
    assert resolve_robot_path(str(tmp_path)) == str(p)

def test_pointer_file_next(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    target = tmp_path / "robot_python"; target.mkdir()
    (tmp_path / "robot-path.txt").write_text(str(target), encoding="utf-8")
    assert resolve_robot_path(str(tmp_path)) == str(target)

def test_home_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    home = tmp_path / "home"; conf = home / ".atomcraft-mcp"; conf.mkdir(parents=True)
    target = tmp_path / "robot_python"; target.mkdir()
    (conf / "robot-path.txt").write_text(str(target), encoding="utf-8")
    monkeypatch.setenv("USERPROFILE", str(home))
    server_dir = tmp_path / "srv"; server_dir.mkdir()
    assert resolve_robot_path(str(server_dir)) == str(target)

def test_missing_everything_raises_with_all_hints(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(RobotPathError) as e:
        resolve_robot_path(str(tmp_path))
    msg = str(e.value)
    assert "ATOMCRAFT_ROBOT_PATH" in msg and "robot-path.txt" in msg

def test_env_var_nonexistent_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOMCRAFT_ROBOT_PATH", str(tmp_path / "nope"))
    with pytest.raises(RobotPathError):
        resolve_robot_path(str(tmp_path))

def test_pointer_file_with_bom_next(tmp_path, monkeypatch):
    """メモ帳等でBOM付きUTF-8保存されたrobot-path.txtでも正しく解決できること。"""
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    target = tmp_path / "robot_python"; target.mkdir()
    (tmp_path / "robot-path.txt").write_text(str(target), encoding="utf-8-sig")
    assert resolve_robot_path(str(tmp_path)) == str(target)

def test_pointer_file_with_bom_home_fallback(tmp_path, monkeypatch):
    """ホームディレクトリ側のポインタファイルでもBOM付きを正しく解決できること。"""
    monkeypatch.delenv("ATOMCRAFT_ROBOT_PATH", raising=False)
    home = tmp_path / "home"; conf = home / ".atomcraft-mcp"; conf.mkdir(parents=True)
    target = tmp_path / "robot_python"; target.mkdir()
    (conf / "robot-path.txt").write_text(str(target), encoding="utf-8-sig")
    monkeypatch.setenv("USERPROFILE", str(home))
    server_dir = tmp_path / "srv"; server_dir.mkdir()
    assert resolve_robot_path(str(server_dir)) == str(target)
