"""有効値カタログと近似候補サジェスト。

CRI Atom Craft Robot API のオブジェクトタイプ名・プロパティフィールド名は、
コード上から静的に列挙する手段がない（サーバー側の内部定義に依存する）。
このモジュールは、これまでの利用実績から蓄積した「既知の有効値」を
純粋なデータテーブルとして保持し、呼び出し元LLMが typo や無効な値を
渡した際にエラーメッセージへ付加するヒント文字列を生成する。

ここに定義するテーブルは知見の蓄積によって拡張されていく前提であり、
ロジック自体は単純に保つ（difflibによる近似マッチのみ）。
"""

from __future__ import annotations

import difflib

# CRI Atom Craft Robot API で扱う既知のオブジェクトタイプ一覧
OBJECT_TYPES: list[str] = [
    "Project",
    "WorkUnit",
    "CueSheet",
    "CueSheetFolder",
    "CueFolder",
    "Cue",
    "Track",
    "Synth",
    "WaveformRegion",
    "Material",
    "MaterialFolder",
    "MaterialSubFolder",
    "MaterialRootFolder",
    "Bus",
    "BusMaster",
    "Mixer",
    "AISAC",
    "AISACControl",
    "SelectorLabel",
    "Selector",
    "Category",
    "CategoryGroup",
    "CategoryFolder",
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
    """無効なオブジェクトタイプ名向けのヒント文字列を生成する。"""
    candidates = suggest(bad_type, OBJECT_TYPES)
    return (
        f"'{bad_type}' は利用できません。"
        f"近い候補: {', '.join(candidates)}。"
        f"有効なタイプ例: {', '.join(OBJECT_TYPES)}"
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
