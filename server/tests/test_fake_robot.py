# tests/test_fake_robot.py
from tests.fake_robot import FakeRobot

def test_handler_returns_canned_response():
    fake = FakeRobot()
    fake.set_handler("project", "find_object", {"succeed": True, "data": "uuid-123", "message": ""})
    result = fake.project.find_object(None, "CueSheet", "MySheet")
    assert result == {"succeed": True, "data": "uuid-123", "message": ""}
    assert fake.call_log == [("project", "find_object", (None, "CueSheet", "MySheet"))]

def test_fail_times_then_success():
    fake = FakeRobot()
    fake.set_handler("project", "get_value", {"succeed": True, "data": "attack_a", "message": ""})
    fake.fail_times("project", "get_value", 1, {"succeed": False, "message": "Failed to parse response"})
    r1 = fake.project.get_value("u1", "Name")
    r2 = fake.project.get_value("u1", "Name")
    assert r1["succeed"] is False
    assert r2["succeed"] is True

def test_connectlib_controls():
    fake = FakeRobot()
    assert fake.connectlib.initialize() == 0
    assert fake.connectlib.connect("127.0.0.1", 9000) == 0
    fake.connectlib.connect_result = 1
    assert fake.connectlib.connect("127.0.0.1", 9000) == 1
