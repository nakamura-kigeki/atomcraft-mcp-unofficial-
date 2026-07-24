import json
from atomcraft_mcp import envelope


def test_classify_invalid_field():
    c = envelope.classify("指定したフィールド [Category] は利用できません。")
    assert c.code == "INVALID_FIELD"
    assert c.details == {"invalid_fields": ["Category"]}
    assert c.retryable is False
    assert "manage_category" in c.hint  # Category系はhintで別経路を案内


def test_classify_invalid_type():
    c = envelope.classify("指定したタイプ [MaterialFolder] は現在利用できません。")
    assert c.code == "INVALID_TYPE"
    assert c.details == {"invalid_type": "MaterialFolder"}


def test_classify_material_register():
    c = envelope.classify("マテリアルの登録に失敗しました。 C:/foo/bar.wav")
    assert c.code == "ALREADY_EXISTS"
    assert "find_by_name" in c.hint  # 既登録の可能性→既存UUID検索を案内


def test_classify_parse_error():
    c = envelope.classify("Failed to parse response")
    assert c.code == "PARSE_ERROR"
    assert c.retryable is True


def test_classify_fallback():
    c = envelope.classify("このターゲットの色を編集することはできません。")
    assert c.code == "API_ERROR"
    assert c.retryable is False


def test_from_result_success_and_error_envelope():
    ok = json.loads(envelope.from_result({"succeed": True, "data": "uuid-1"}))
    assert ok == {"success": True, "data": "uuid-1", "message": ""}

    err = json.loads(envelope.from_result(
        {"succeed": False, "message": "指定したフィールド [LoopType] は利用できません。"}))
    assert err["success"] is False
    assert err["code"] == "INVALID_FIELD"
    assert err["retryable"] is False
    assert "hint" in err and err["hint"]


def test_from_result_infra_code_wins():
    err = json.loads(envelope.from_result(
        {"succeed": False, "message": "API call timed out after 30s.", "_code": "TIMEOUT"}))
    assert err["code"] == "TIMEOUT"
    assert err["retryable"] is True


def test_make_error_shape():
    err = json.loads(envelope.make_error("x", code="INVALID_PARAMS", hint="do y"))
    assert set(err.keys()) == {"success", "code", "error", "hint", "retryable"}


def test_classify_empty_and_none_fall_back_to_api_error():
    assert envelope.classify("").code == "API_ERROR"
    assert envelope.classify(None).code == "API_ERROR"


def test_classify_business_message_containing_connection_word():
    # "connection"という語を含むビジネスエラーをCONNECTION_LOSTに誤分類しない
    c = envelope.classify("Bus connection type is invalid.")
    assert c.code == "API_ERROR"


def test_classify_multi_field_bracket_splits():
    c = envelope.classify("指定したフィールド [Category, Pan] は利用できません。")
    assert c.details == {"invalid_fields": ["Category", "Pan"]}


def test_from_result_parse_error_infra():
    err = json.loads(envelope.from_result(
        {"succeed": False, "message": "API returned non-dict result", "_code": "PARSE_ERROR"}))
    assert err["code"] == "PARSE_ERROR"
    assert err["retryable"] is True
