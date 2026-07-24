from atomcraft_mcp import catalog


def test_suggest_close_match():
    assert "CueSheet" in catalog.suggest("CueSheat", catalog.OBJECT_TYPES)


def test_type_hint_contains_suggestion_and_list():
    h = catalog.type_hint("MaterialFolde")
    assert "MaterialFolder" in h


def test_field_hint_known_type():
    h = catalog.field_hint("Cue", ["Category"])
    assert "CuePriority" in h            # 有効フィールド一覧を含む
    assert "manage_category" in h        # 代替経路を含む


def test_field_hint_unknown_type_falls_back():
    h = catalog.field_hint("Bus", ["Foo"])
    assert "Name" in h  # "*"フォールバック
