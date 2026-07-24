import pytest
from atomcraft_mcp import config
from atomcraft_mcp.robot import RobotPathError, load as load_robot


def test_defaults():
    s = config.load(env={})
    assert s.host == "127.0.0.1"
    assert s.port == 9000
    assert s.api_timeout == 30.0
    assert s.tree_json_budget == 50000
    assert s.output_base_dir.lower().endswith("atomcraft_mcp")


def test_invalid_values_fall_back_to_default():
    s = config.load(env={"ATOMCRAFT_PORT": "abc", "ATOMCRAFT_API_TIMEOUT": "-5"})
    assert s.port == 9000
    assert s.api_timeout == 30.0


def test_valid_overrides():
    s = config.load(env={"ATOMCRAFT_PORT": "9100", "ATOMCRAFT_API_TIMEOUT": "60"})
    assert s.port == 9100
    assert s.api_timeout == 60.0


def test_robot_load_missing_pointer(tmp_path):
    with pytest.raises(RobotPathError) as ei:
        load_robot(str(tmp_path))
    assert "robot-path.txt" in str(ei.value)


def test_robot_load_nonexistent_target(tmp_path):
    (tmp_path / "robot-path.txt").write_text(r"C:\no\such\dir", encoding="utf-8")
    with pytest.raises(RobotPathError):
        load_robot(str(tmp_path))
