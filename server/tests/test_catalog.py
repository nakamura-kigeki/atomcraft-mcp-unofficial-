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


# --- graph_type / バスエフェクト / エイリアス(v0.2.4で追加) ---

def test_graph_types_contains_verified_values():
    assert "Volume" in catalog.GRAPH_TYPES
    assert "AisacControl15" in catalog.GRAPH_TYPES
    assert "BusSendLevel8" in catalog.GRAPH_TYPES
    # 公式表記の "Spread" は実機で拒否されるため採用せず、PanSpreadを採る
    assert "PanSpread" in catalog.GRAPH_TYPES
    assert "Spread" not in catalog.GRAPH_TYPES


def test_graph_type_hint_suggests_and_stays_short():
    h = catalog.graph_type_hint("Volumee")
    assert "Volume" in h
    assert "AisacControl9" not in h  # 全件ダンプしない
    h2 = catalog.graph_type_hint("zzzzzz")
    assert "refobject" in h2


def test_bus_effect_hint_suggests_and_stays_short():
    h = catalog.bus_effect_hint("Reverbb")
    assert "Reverb" in h
    assert "HeadphoneVirtualSurround" not in h  # 全件ダンプしない


def test_bus_effect_types_include_numeric_prefixed():
    # 数字始まりの型名は転記時に落としやすいので明示的に守る
    assert "3BandEQ" in catalog.BUS_EFFECT_TYPES
    assert "32BandEQ" in catalog.BUS_EFFECT_TYPES


def test_aliases_are_not_in_object_types():
    """未文書エイリアスは実体型と同じオブジェクトを返すためカタログに入れない"""
    assert "Waveform" not in catalog.OBJECT_TYPES
    assert "LanguageSettingFolder" not in catalog.OBJECT_TYPES
    assert catalog.OBJECT_TYPE_ALIASES["Waveform"] == "Material"


def test_undocumented_types_present():
    """公式未記載だが実機が受理する型(公式∪実機)"""
    for t in ("ParameterAction", "DspBusMaster", "BusMapRootFolder", "CueSheetSubFolder"):
        assert t in catalog.OBJECT_TYPES


def test_known_fields_expanded_from_official_reference():
    assert len(catalog.KNOWN_FIELDS["Cue"]) > 50
    assert "PlaybackPositionBehavior" in catalog.KNOWN_FIELDS["Track"]
    # 概念グルーピングの見出しは型名ではないので鍵にしない
    for heading in ("Action", "Marker", "InternalCueLink"):
        assert heading not in catalog.KNOWN_FIELDS
    # 実機で型ごとに差が出たものは分けて保持する
    assert "CallbackId" in catalog.KNOWN_FIELDS["CallbackMarker"]
    assert "CallbackId" not in catalog.KNOWN_FIELDS["LoopMarker"]
