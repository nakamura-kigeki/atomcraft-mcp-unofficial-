"""プロパティ読み取り・書き込みツール: get_property / set_property / manage_category

legacy/server.py:243-392 (atomcraft_get_property, atomcraft_set_property,
atomcraft_manage_category) の変換版。

get_propertyは部分成功アルゴリズムを実装する: get_valuesがINVALID_FIELDで失敗した場合、
無効フィールドを除外して再試行を繰り返し、1件でも取得できれば成功として返す
（実測エラー1位「フィールド1つのtypoで全滅」の根絶）。
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error, make_success, classify
from ..transport import READ, IDEMPOTENT_WRITE, NON_IDEMPOTENT
from ..versioning import require_feature
from .. import catalog

CategoryAction = Literal["get", "set", "add"]

# 根拠は docs/dev/api-versions.md の採用値(確度: 推定/極めて低い)。
MIN_VER_BULK = (3, 42, 0)


class _ApiFailure(Exception):
    """フィールド起因でないAPI失敗を上位のfrom_result処理へ運ぶ内部例外"""
    def __init__(self, result: dict):
        super().__init__(result.get("message", ""))
        self.result = result


def _get_values_partial(t, p, target, fields):
    """無効フィールドを除外しながらget_valuesを繰り返す。(properties, invalid_fields)を返す"""
    remaining = list(fields)
    invalid = []
    for _ in range(len(fields)):
        if not remaining:
            break
        result = t.call(p.get_values, target, remaining, idempotency=READ)
        if result.get("succeed"):
            return result.get("data", {}) or {}, invalid
        c = classify(result.get("message", ""))
        if c.code != "INVALID_FIELD" or not c.details.get("invalid_fields"):
            # フィールド起因でない失敗はそのまま上位へ
            raise _ApiFailure(result)
        bad = c.details["invalid_fields"]
        before = len(remaining)
        remaining = [f for f in remaining if f not in bad]
        if len(remaining) == before:
            # 除外が進まない（メッセージ形式が想定外）→ 同一呼び出しの空回りを防ぐ
            raise _ApiFailure(result)
        invalid.extend(bad)
    return {}, invalid


def make_tools(t):
    p = t._robot.project
    pj = t._robot.project

    def atomcraft_get_property(
        target: str,
        fields: Optional[list[str]] = None,
        use_actual_value: bool = False,
        target_config: Optional[str] = None,
        include_meta: bool = True,
    ) -> str:
        """オブジェクトのプロパティ値を取得する。

        target: 対象オブジェクトのUUID
        fields: 取得するフィールド名の配列 (例: ["Name", "Volume", "CueID"])
        use_actual_value: trueなら継承解決後の実効値を取得
        target_config: ターゲットコンフィグのUUID (use_actual_value=trueの場合に任意)
        include_meta: trueならオブジェクトパスとタイプ名も付加

        存在しない/利用できないフィールドが混在していても、有効なフィールドだけを
        自動的に除外して取得を続行する（部分成功）。除外されたフィールドは
        data.invalid_fields と warnings で通知される。全滅した場合のみエラーになる。
        """
        data = {}
        type_name = "*"

        if include_meta:
            path_result = t.call(p.get_object_path, target, idempotency=READ)
            if path_result.get("succeed"):
                data["object_path"] = path_result.get("data")

            type_result = t.call(p.get_type_name, target, idempotency=READ)
            if type_result.get("succeed"):
                data["type_name"] = type_result.get("data")
                type_name = type_result.get("data") or "*"

        invalid_fields = []

        if fields:
            if len(fields) == 1:
                field = fields[0]
                if use_actual_value:
                    result = t.call(p.get_actual_value, target, field, target_config, idempotency=READ)
                else:
                    result = t.call(p.get_value, target, field, idempotency=READ)
                if result.get("succeed"):
                    data["properties"] = {field: result.get("data")}
                else:
                    c = classify(result.get("message", ""))
                    if c.code == "INVALID_FIELD":
                        return make_error(
                            result.get("message", "Unknown error"), "INVALID_FIELD",
                            hint=catalog.field_hint(type_name, [field]))
                    return from_result(result)
            else:
                if use_actual_value:
                    properties = {}
                    for field in fields:
                        result = t.call(p.get_actual_value, target, field, target_config, idempotency=READ)
                        if result.get("succeed"):
                            properties[field] = result.get("data")
                            continue
                        c = classify(result.get("message", ""))
                        if c.code == "INVALID_FIELD":
                            invalid_fields.append(field)
                        else:
                            return from_result(result)
                else:
                    try:
                        properties, invalid_fields = _get_values_partial(t, p, target, fields)
                    except _ApiFailure as e:
                        return from_result(e.result)

                if not properties:
                    return make_error(
                        "All requested fields are invalid",
                        "INVALID_FIELD",
                        hint=catalog.field_hint(type_name, invalid_fields))
                data["properties"] = properties
                if invalid_fields:
                    data["invalid_fields"] = invalid_fields

        # 色情報も取得（ベストエフォート）
        color_result = t.call(p.get_color, target, idempotency=READ)
        if color_result.get("succeed") and color_result.get("data"):
            data["color"] = color_result.get("data")

        warnings = []
        if invalid_fields:
            warnings.append(
                f"フィールド {', '.join(invalid_fields)} は利用できず除外しました。"
                + catalog.field_hint(type_name, invalid_fields))

        return make_success(data=data, warnings=warnings or None)

    def atomcraft_set_property(
        target: str,
        properties: Optional[dict[str, str]] = None,
        color: Optional[str] = None,
    ) -> str:
        """オブジェクトのプロパティ値を設定する。

        target: 対象オブジェクトのUUID
        properties: フィールド名と値のマップ (例: {"Volume": "0.8", "Name": "NewName"})。値はすべて文字列。
        color: 色を設定する場合の色値。"unset"で色をリセット。
        """
        messages = []

        if properties:
            result = t.call(p.set_values, target, properties, idempotency=IDEMPOTENT_WRITE)
            if not result.get("succeed"):
                return from_result(result)
            messages.append(f"Set {len(properties)} property(ies)")

        if color is not None:
            if color == "unset":
                result = t.call(p.unset_color, target, idempotency=IDEMPOTENT_WRITE)
            else:
                result = t.call(p.set_color, target, color, idempotency=IDEMPOTENT_WRITE)
            if not result.get("succeed"):
                return from_result(result)
            messages.append("Color updated")

        return make_success(message=", ".join(messages) if messages else "No changes")

    def atomcraft_manage_category(
        action: CategoryAction,
        cue: Optional[str] = None,
        cue_list: Optional[list[str]] = None,
        category: Optional[str] = None,
        category_list: Optional[list[str]] = None,
    ) -> str:
        """キューへのカテゴリの取得・設定・追加を行う。

        action: get (カテゴリ一覧取得), set (カテゴリ完全置換), add (カテゴリ追加)
        cue: 対象のキューUUID (action=get, setで必須)
        cue_list: 対象のキューUUIDリスト (action=addで必須)
        category: カテゴリのUUID (action=addで必須)
        category_list: カテゴリUUIDのリスト (action=setで必須)
        """
        if action == "get":
            if not cue:
                return make_error("cue is required", "INVALID_PARAMS",
                                  hint="action=getにはcueが必要です")
            result = t.call(p.get_categories, cue, idempotency=READ)
            if result.get("succeed"):
                return make_success(data={"category_ids": result.get("data", [])})
            return from_result(result)

        elif action == "set":
            if not cue or not category_list:
                return make_error("cue and category_list are required", "INVALID_PARAMS",
                                  hint="action=setにはcueとcategory_listが必要です")
            result = t.call(p.set_categories, cue, category_list, idempotency=IDEMPOTENT_WRITE)
            return from_result(result)

        elif action == "add":
            if not cue_list or not category:
                return make_error("cue_list and category are required", "INVALID_PARAMS",
                                  hint="action=addにはcue_listとcategoryが必要です")
            result = t.call(p.add_category_to_cues, cue_list, category, idempotency=NON_IDEMPOTENT)
            return from_result(result)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(CategoryAction.__args__)}",
                "INVALID_PARAMS")

    def atomcraft_bulk_property(
        action: Literal["get", "set"],
        targets: list,
        field_names: Optional[list] = None,
        field_name: Optional[str] = None,
        value: Optional[str] = None,
    ) -> str:
        """複数オブジェクトのプロパティを一括取得・一括設定する。

        1件ずつ get/set するより大幅に少ない呼び出しで済む。大量編集ではこちらを使う。
        action=get: targets(UUIDリスト) + field_names(フィールド名リスト)
        action=set: targets(UUIDリスト) + field_name + value(全対象に同じ値。
                    値は文字列として送られる。数値・bool も "0.5" "true" のように文字列で渡す)

        既知の問題(action=get, Ver.3.57.02実機で確認, 2026-07-24/25):
        ロボットAPI `get_value_from_targets(targets, field_name)` は、CRIローカル
        マニュアル・公式Webリファレンスとも field_name を単一文字列と定義している
        (リストを取るのは get_values の field_names。CRIクライアント実装の引数名
        `field_names` は紛らわしいが仕様は単数)。実機Ver.3.57.02では
        (a) リストを渡すと `フィールド名が指定されていません` のAPI_ERROR、
        (b) 仕様どおり単一文字列を渡すと応答の解析に失敗(PARSE_ERROR)し、
        **直後から接続そのものが死にスクリプトサーバーも停止する**ことを、
        バッチ実験2回+クリーンな単独接続での再現1回の計3回確認した。
        公式仕様の戻り値が「オブジェクトをキーとする連想配列」であり、これが
        リモートプロトコルで直列化できていない可能性が高い。
        接続を巻き添えにする事故を防ぐため、action=get はサーバーを呼ばず
        ローカルで即エラーを返す(意図的な無効化)。一括取得が必要な場合は
        対象ごとに atomcraft_get_property を呼ぶこと。action=set
        (set_value_to_targets)は実機で動作確認済みで通常どおり使える。
        """
        if not targets:
            return make_error("targets is required", "INVALID_PARAMS",
                              hint="対象オブジェクトのUUIDをリストで指定してください")
        if action == "get":
            if not field_names:
                return make_error("field_names is required for get", "INVALID_PARAMS")
            # 意図的な無効化(docstring「既知の問題」参照): このAPIはVer.3.57.02の
            # リモート経由では応答が解析できず接続ごと落とすため、呼び出さない。
            return make_error(
                "action=get は現在無効化されています(Ver.3.57.02実機で、リモート経由の "
                "get_value_from_targets は応答解析失敗により接続を切断することを確認済み)",
                "API_ERROR",
                hint="対象ごとに atomcraft_get_property を呼んでください。"
                     "一括設定(action=set)は問題なく使えます。")
        elif action == "set":
            if not field_name or value is None:
                return make_error("field_name and value are required for set",
                                  "INVALID_PARAMS")
            err, fn = require_feature(t, pj, "set_value_to_targets",
                                      MIN_VER_BULK, "一括プロパティ設定")
            if err:
                return err
            result = t.call(fn, targets, field_name, value, idempotency=IDEMPOTENT_WRITE)
        else:
            return make_error(f"Unknown action: {action}", "INVALID_PARAMS")
        return from_result(result)

    return [atomcraft_get_property, atomcraft_set_property, atomcraft_manage_category,
            atomcraft_bulk_property]
