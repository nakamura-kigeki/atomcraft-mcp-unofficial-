from atomcraft_mcp import catalog


def test_suggest_close_match():
    assert "CueSheet" in catalog.suggest("CueSheat", catalog.OBJECT_TYPES)


def test_type_hint_contains_suggestion():
    h = catalog.type_hint("MaterialSubFolde")
    assert "MaterialSubFolder" in h
    # 全件ダンプはしない(84件時代のヒント肥大化対策)
    assert "TargetConfigWebGl" not in h


def test_type_hint_no_candidates_shows_representatives():
    h = catalog.type_hint("zzzzzz")
    assert "近い候補も見つかりませんでした" in h
    assert "CueSheet" in h  # 代表例
    assert "refobject" in h  # 公式リファレンスへの誘導


def test_type_hint_aisac_case_fix():
    """v0.2.2で修正した旧表記(全大文字)にも近似候補が出ること"""
    h = catalog.type_hint("AISACControl")
    assert "AisacControl" in h


def test_field_hint_known_type():
    h = catalog.field_hint("Cue", ["Category"])
    assert "CuePriority" in h            # 有効フィールド一覧を含む
    assert "manage_category" in h        # 代替経路を含む


def test_field_hint_unknown_type_falls_back():
    h = catalog.field_hint("Bus", ["Foo"])
    assert "Name" in h  # "*"フォールバック
