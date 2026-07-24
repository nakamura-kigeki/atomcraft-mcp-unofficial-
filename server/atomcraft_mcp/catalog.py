"""有効値カタログと近似候補サジェスト。

オブジェクトタイプ名の一次情報はCRI公式のオブジェクトリファレンス:
https://game.criware.jp/manual/adx2_tool/latest/criatom_tools_atomcraft_api_refobject.html

OBJECT_TYPES は上記公式リスト84件を、Atom Craft Ver.3.56.01(LE版)実機の
find_all_by_type に全件照合した結果に基づく(2026-07-25検証。83件有効・
Automationのみ拒否。詳細は docs/dev/CAPABILITIES.md「オブジェクト型名の実機検証」)。

プロパティフィールド名(KNOWN_FIELDS)は静的な公式一覧が確認できていないため、
従来どおり利用実績からの蓄積で拡張する。ヒント生成のロジック自体は単純に保つ
（difflibによる近似マッチのみ）。
"""

from __future__ import annotations

import difflib

# CRI公式オブジェクトリファレンス記載の全型名(モジュールdocstringの出典参照)。
# 実機Ver.3.56.01(LE)の find_all_by_type で全件照合済み(Automationのみ拒否)。
# なお "Waveform" は未文書だが受理される "Material" の別名(返却type_nameはMaterial)
# のため、このリストには載せない。
OBJECT_TYPES: list[str] = [
    # --- プロジェクト設定・ユーザー設定・全体設定 ---
    "Project",
    "UserSettings",
    "GlobalFolder",
    "TargetConfigFolder",
    "TargetConfigPc",
    "TargetConfigPs4",
    "TargetConfigXboxOne",
    "TargetConfigSwitch",
    "TargetConfigiPhone",  # 小文字の i が正
    "TargetConfigAndroid",
    "TargetConfigWebGl",  # WebGL ではなく WebGl が正
    "TargetConfigPublic",
    "LanguageSettingsFolder",
    "LanguageSettings",
    "OutputPortFolder",
    "OutputPort",
    "VoicePoolFolder",
    "VoicePool",
    "MixerFolder",
    "Mixer",
    "MixerSnapshot",
    "Bus",
    "BusMaster",
    "BusMap",
    "CategoryFolder",
    "CategoryGroup",
    "Category",
    "GameVariableFolder",
    "GameVariable",
    "SelectorFolder",
    "Selector",
    "SelectorLabel",
    "ReactFolder",
    "React",
    "VoiceLimitGroupFolder",
    "VoiceLimitGroup",
    "AisacControlFolder",
    "AisacControl",
    "GlobalAisacFolder",
    # --- AISAC ---
    "Aisac",
    "AisacGraph",
    "AisacPoint",
    # --- ワークユニットツリー ---
    "WorkUnitFolder",
    "WorkUnitSubFolder",
    "WorkUnit",
    "ReferenceAisacFolder",
    "CueSheetRootFolder",  # atomcraft_get_tree が返す type 値
    "CueSheetFolder",
    "CueSheet",
    "CueFolder",
    "PrivateCueFolder",
    "Cue",
    "LoopMarker",
    "StartMarker",
    "EndMarker",
    "CallbackMarker",
    "ReactEndMarker",
    # "Automation" は公式リストに記載があるが、実機Ver.3.56.01(LE)では INVALID_TYPE
    # (3回試行して再現。AutomationGraph / AutomationTrack も拒否で代替名は見つからず。
    # 子要素の AutomationPoint は有効なため、親型のみ欠けている状態)。
    # 製品版・新バージョンで有効な可能性を残して保持する。
    "Automation",
    "AutomationPoint",
    "Track",
    "WaveformRegion",
    "SubSequence",
    "CueLink",
    "ExternalCueLink",
    "ActionTrack",
    "ActionStart",
    "ActionStop",
    "ActionPause",
    "ActionResume",
    "ActionMute",
    "ActionSetPlaybackParameter",
    "ActionSetSelectorLabel",
    "PlayerActionTrack",
    "ActionPlayerFader",
    "AisacLink",
    "Block",
    "BeatSync",
    "TrimmingInfo",
    "FadeInfo",
    "StopAction",
    # --- マテリアルツリー ---
    "MaterialInfo",
    "MaterialRootFolder",
    "MaterialSubFolder",
    "Material",
]

# INVALID_TYPE時のヒントで、近似候補が1件も出なかった場合に示す代表例。
_REPRESENTATIVE_TYPES: list[str] = [
    "Project", "WorkUnit", "CueSheet", "CueSheetRootFolder", "Cue", "Track",
    "WaveformRegion", "Material", "MaterialRootFolder", "Bus", "Mixer",
    "Aisac", "AisacControl", "Category", "Selector",
]

# タイプ別の既知有効プロパティフィールド一覧。
# "*" はどのタイプにも該当しない場合のフォールバック。
KNOWN_FIELDS: dict[str, list[str]] = {
    "Cue": [
        "Name",
        "Comment",
        "CueID",
        "Volume",
        "Pitch",
        "SequenceType",
        "UserData",
        "CuePriority",
    ],
    "Material": ["Name"],
    "*": ["Name", "Comment"],
}

# タイプ別の「取得できないフィールド」→代替経路のヒント。
UNAVAILABLE_FIELDS: dict[str, dict[str, str]] = {
    "Cue": {
        "Category": "atomcraft_manage_category(action='get') を使用してください",
        "Categories": "atomcraft_manage_category(action='get') を使用してください",
        "Pan": "利用不可",
        "DSPBusSetting": "atomcraft_manage_busmap(action='get_for_cue') を使用してください",
    },
}


def suggest(value: str, candidates: list[str], n: int = 3) -> list[str]:
    """value に近い候補を candidates から最大 n 件返す。"""
    return difflib.get_close_matches(value, candidates, n=n, cutoff=0.5)


def type_hint(bad_type: str) -> str:
    """無効なオブジェクトタイプ名向けのヒント文字列を生成する。

    84件の全リストをダンプするとエラーのたびに約1,300文字がhintに載って
    LLMの文脈を浪費するため、近似候補のみを返し、候補が1件も無いときだけ
    代表例と公式リファレンスへの誘導を示す。
    """
    candidates = suggest(bad_type, OBJECT_TYPES)
    if candidates:
        return (
            f"'{bad_type}' は利用できません。"
            f"近い候補: {', '.join(candidates)}"
        )
    return (
        f"'{bad_type}' は利用できません。近い候補も見つかりませんでした。"
        f"代表的なタイプ例: {', '.join(_REPRESENTATIVE_TYPES)}。"
        "全一覧はCRI公式のオブジェクトリファレンス"
        "(criatom_tools_atomcraft_api_refobject.html)を参照してください。"
    )


def field_hint(type_name: str, bad_fields: list[str]) -> str:
    """無効なプロパティフィールド向けのヒント文字列を生成する。

    既知の有効フィールド一覧（タイプ別、なければ "*" フォールバック）と、
    UNAVAILABLE_FIELDS に登録された代替経路の案内を連結して返す。
    """
    known = KNOWN_FIELDS.get(type_name, KNOWN_FIELDS["*"])
    parts = [f"'{type_name}' の既知の有効フィールド: {', '.join(known)}"]

    unavailable = UNAVAILABLE_FIELDS.get(type_name, {})
    for field in bad_fields:
        if field in unavailable:
            parts.append(f"'{field}' は取得できません。{unavailable[field]}")

    return "。".join(parts)
