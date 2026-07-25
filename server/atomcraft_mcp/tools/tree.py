"""汎用ツリー展開ツール: atomcraft_get_tree

legacy/server.py:1039-1297 (atomcraft_get_tree) の変換版。

legacyからの主な変更差分（brief内の番号に対応）:
  1. output_dir省略時のデフォルトが settings.output_base_dir（%TEMP%\\atomcraft_mcp）になった
     （mcp-serverディレクトリへの出力は廃止）
  2. output_format="json" で構築したツリーが settings.tree_json_budget を超える場合、
     APIを再呼び出しせずメモリ上のツリーをCSV行＋構造JSONに変換し（_tree_to_rows）、
     CSVモードと同形式のレスポンス＋auto_fallback=Trueで返す
  3. JSONレスポンスの形は data={"tree": ..., "timed_out": ..., "truncated": ...}
     （破壊的変更: 旧形式はtreeが直接data直下だった）
  4. max_depthは0-50、max_childrenは1-10000の範囲外はAPI呼び出し前にINVALID_PARAMS
  5. API呼び出し回数が5000回を超えたら走査を打ち切りtruncated=Trueにする（安全弁）
  6. CSV/構造JSON書き出し前に、出力先ディレクトリの古い tree_data_*.csv /
     tree_structure_*.json（更新日時7日超）をベストエフォートで削除する
  7. 走査内の全API呼び出しは idempotency=READ で行う
"""
import csv
import glob
import json
import os
import time
from datetime import datetime
from typing import Optional

from ..envelope import classify, infra_hint, make_error, make_success
from ..transport import READ

_MAX_TOTAL_CALLS = 5000
_OLD_FILE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_CSV_META_COLUMNS = ["depth", "type", "path", "parent_path", "uuid"]
_INFRA_CODES = {"TIMEOUT", "CONNECTION_LOST", "PARSE_ERROR", "SERVER_UNREACHABLE", "UNKNOWN_OUTCOME"}


def _tree_to_rows(tree: dict, fields: list) -> tuple:
    """メモリ上のJSONツリー(_build_nodeが構築したもの)をCSV行＋構造ツリーに変換する。

    APIの再呼び出しは一切行わない純粋関数。
    children を持つノード → 構造ノード（type/path/name/comment/depth/leaf_count）
    children を持たないノード → CSV行（depth/type/path/parent_path/uuid + fields各列）
    """
    csv_rows = []

    def _walk(node: dict, depth: int, parent_path: str) -> Optional[dict]:
        children = node.get("children")
        type_name = node.get("type", "")
        path = node.get("path", "")
        if children:
            props = node.get("properties") or {}
            struct_node = {
                "type": type_name,
                "path": path,
                "name": props.get("Name", ""),
                "comment": props.get("Comment", ""),
                "depth": depth,
            }
            leaf_count = 0
            child_structs = []
            for child in children:
                child_result = _walk(child, depth + 1, path)
                if child_result is not None:
                    child_structs.append(child_result)
                else:
                    leaf_count += 1
            struct_node["leaf_count"] = leaf_count
            if child_structs:
                struct_node["children"] = child_structs
            return struct_node
        else:
            properties = node.get("properties") or {}
            row = {
                "depth": depth,
                "type": type_name,
                "path": path,
                "parent_path": parent_path,
                "uuid": node.get("uuid", ""),
            }
            for f in fields:
                row[f] = properties.get(f, "")
            csv_rows.append(row)
            return None

    structure = _walk(tree, 0, "")
    return csv_rows, structure


def _resolve_output_dir(output_dir: Optional[str], settings) -> str:
    base_dir = output_dir if output_dir else settings.output_base_dir
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _cleanup_old_files(base_dir: str) -> None:
    """出力先の古いtree_*ファイルをベストエフォートで削除する（失敗しても呼び出しは継続）。"""
    try:
        cutoff = time.time() - _OLD_FILE_MAX_AGE_SECONDS
        for pattern in ("tree_data_*.csv", "tree_structure_*.json"):
            for path in glob.glob(os.path.join(base_dir, pattern)):
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except OSError:
                    pass
    except Exception:
        pass


def _write_tree_files(base_dir: str, rows: list, fields: list, structure) -> tuple:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(base_dir, f"tree_data_{timestamp}.csv")
    json_path = os.path.join(base_dir, f"tree_structure_{timestamp}.json")
    csv_columns = _CSV_META_COLUMNS + fields

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    return csv_path, json_path, csv_columns


def make_tools(t, settings):
    p = t._robot.project

    def atomcraft_get_tree(
        root: str,
        child_types: list,
        fields: Optional[list] = None,
        max_depth: int = 10,
        max_children: int = 500,
        output_format: str = "json",
        output_dir: Optional[str] = None,
    ) -> str:
        """オブジェクトツリーを再帰的に展開し、一括で取得する。

        1回の呼び出しでフォルダ階層を再帰走査し、全ノードのプロパティをまとめて返す。
        CueSheetFolder/CueFolder/MaterialSubFolder等あらゆるフォルダ型に対応する汎用ツール。

        root: 起点オブジェクトのUUID
        child_types: 展開する子タイプ名のリスト。リスト内の全タイプについて子要素を検索する。
            例: ["CueSheetFolder","CueSheet","CueFolder","Cue"]
            例: ["CategoryGroup","Category"]
            例: ["MaterialSubFolder","Material"]
        fields: 各ノードから取得するプロパティ名のリスト (例: ["Name","CueID","Volume","Comment"])
            省略時はNameのみ取得
        max_depth: 最大再帰深度 (デフォルト10、0で起点のみ。範囲: 0-50)
        max_children: 1ノードあたりの最大子要素数 (デフォルト500、巨大ツリーの安全弁。範囲: 1-10000)
        output_format: 出力形式。
            "json" (デフォルト): ツリー構造JSONをそのまま返す
            "csv": 2ファイル出力（structure.json + data.csv）
                - structure.json: フォルダ階層のみの軽量ツリー（AIが読んで全体把握用）
                - data.csv: リーフノードのフラットデータ（DuckDBで直接クエリ用）
                CSVカラム: depth, type, path, parent_path, uuid, {fields各列}
        output_dir: CSV出力先ディレクトリ (output_format=csvで使用。省略時は settings.output_base_dir
            = %TEMP%\\atomcraft_mcp 配下。output_dirを明示指定した場合、古いファイルの自動削除は
            行わない — 削除は settings.output_base_dir を使う既定ディレクトリのときのみ行う)

        使用例:
          SEキューシートの全構造 (CSV):
            root=<CueSheet UUID>, child_types=["CueFolder","Cue"],
            fields=["Name","CueID","Volume","Comment"], output_format="csv"
          → 2ファイルが生成される:
            structure.json — AIが読んで全体把握
            data.csv — DuckDBでクエリ:
              SELECT * FROM read_csv_auto('data.csv') WHERE parent_path LIKE '%attack%' ORDER BY CAST(CueID AS INT)

        返却値の注意:
          data.invalid_child_types — child_types のうち**無効な型名だったもの**の一覧。
            空でなければ、その型は検索すらされていない(「その型の子が0件だった」のでは
            ない)。走査自体は続行し、有効な型の子要素は通常どおり取得する。
            **`partial` は無効型があってもFalseのままなので、走査が完全だったかを
            判断するときは partial だけでなく invalid_child_types も必ず確認すること。**
            (partial は timed_out / truncated / インフラエラーによる「途中で止まった」を
            表す既存の意味を保つ。型名ミスは走査の中断ではないため混ぜない。)
            warnings にも同じ内容が1行入る。

        --- Task 11での変更点 ---
        - JSONレスポンスの形は data={"tree": ..., "timed_out": bool, "truncated": bool}
          （破壊的変更: 旧形式はtreeが直接data直下だった）
        - json.dumps(tree) が settings.tree_json_budget 文字を超えると、APIを再呼び出しせず
          メモリ上のツリーをCSV+構造JSONに自動変換して書き出す（data.auto_fallback=True）
        - output_dir省略時は settings.output_base_dir（%TEMP%\\atomcraft_mcp）に出力する
          （明示的にoutput_dirを渡した場合はそちらが優先される）
        - max_depthは0-50、max_childrenは1-10000の範囲外だとAPI呼び出し前にINVALID_PARAMS
        - output_formatは"json"/"csv"以外だとAPI呼び出し前にINVALID_PARAMS
        - output_dirを明示指定した場合、古いファイルの自動削除は行わない(書き込み自体は行う)。
          削除は settings.output_base_dir を使う既定ディレクトリのときのみ行う
        """
        if not isinstance(max_depth, int) or not (0 <= max_depth <= 50):
            return make_error(
                f"max_depth must be an integer between 0 and 50, got {max_depth}",
                "INVALID_PARAMS",
                hint="max_depthは0〜50の範囲で指定してください")
        if not isinstance(max_children, int) or not (1 <= max_children <= 10000):
            return make_error(
                f"max_children must be an integer between 1 and 10000, got {max_children}",
                "INVALID_PARAMS",
                hint="max_childrenは1〜10000の範囲で指定してください")
        if output_format not in ("json", "csv"):
            return make_error(
                f"output_format must be 'json' or 'csv', got {output_format!r}",
                "INVALID_PARAMS",
                hint="output_formatは'json'または'csv'を指定してください")

        if fields is None:
            fields = ["Name"]

        csv_rows = []

        _state = {"timed_out": False, "truncated": False, "call_count": 0, "budget_tripped": False,
                   "infra_code": None, "invalid_child_types": []}

        def _call(func, *args):
            _state["call_count"] += 1
            result = t.call(func, *args, idempotency=READ)
            if _state["call_count"] > _MAX_TOTAL_CALLS and not _state["budget_tripped"]:
                _state["budget_tripped"] = True
                _state["truncated"] = True
            return result

        def _stopped() -> bool:
            return _state["timed_out"] or _state["budget_tripped"] or _state["infra_code"] is not None

        def _check_timeout(result: dict) -> bool:
            """走査中のAPI呼び出し結果がインフラ系失敗かを判定し、そうであれば走査を打ち切る。

            TIMEOUT/CONNECTION_LOST/PARSE_ERROR/SERVER_UNREACHABLE/UNKNOWN_OUTCOME は
            いずれも「途中のサブツリーが黙って欠落する」原因になるため、_stopped()経由で
            以降のAPI呼び出しを止める。timed_outフラグはTIMEOUT時のみ立てる
            （他のコードはタイムアウトではないため区別する）。
            成功=Falseだが_codeが付いていないビジネス失敗（NOT_FOUND等）は対象外
            （従来通り黙ってスキップ）。
            """
            code = result.get("_code")
            if code in _INFRA_CODES:
                if _state["infra_code"] is None:
                    _state["infra_code"] = code
                if code == "TIMEOUT":
                    _state["timed_out"] = True
                return True
            return False

        def _get_properties(obj_id: str, target_fields: list) -> dict:
            if _stopped():
                return {}
            properties = {}
            if len(target_fields) == 1:
                prop_result = _call(p.get_value, obj_id, target_fields[0])
                if _check_timeout(prop_result):
                    return {}
                if prop_result.get("succeed"):
                    properties[target_fields[0]] = prop_result.get("data", "")
            else:
                prop_result = _call(p.get_values, obj_id, target_fields)
                if _check_timeout(prop_result):
                    return {}
                if prop_result.get("succeed"):
                    properties = prop_result.get("data", {})
                else:
                    for field in target_fields:
                        if _stopped():
                            break
                        fr = _call(p.get_value, obj_id, field)
                        if _check_timeout(fr):
                            break
                        if fr.get("succeed"):
                            properties[field] = fr.get("data", "")
            return properties

        def _get_meta(obj_id: str) -> tuple:
            if _stopped():
                return "", ""
            type_name = ""
            path = ""
            type_result = _call(p.get_type_name, obj_id)
            if _check_timeout(type_result):
                return "", ""
            if type_result.get("succeed"):
                type_name = type_result.get("data", "")
            path_result = _call(p.get_object_path, obj_id)
            if _check_timeout(path_result):
                return type_name, ""
            if path_result.get("succeed"):
                path = path_result.get("data", "")
            return type_name, path

        def _get_children_ids(obj_id: str) -> list:
            if _stopped():
                return []
            all_children = []
            for ctype in child_types:
                if _stopped():
                    break
                child_result = _call(p.get_child_objects, obj_id, ctype)
                if _check_timeout(child_result):
                    break
                if child_result.get("succeed"):
                    child_ids = child_result.get("data", [])
                    if isinstance(child_ids, list):
                        if len(child_ids) > max_children:
                            _state["truncated"] = True
                        all_children.extend(child_ids[:max_children])
                elif classify(child_result.get("message", "")).code == "INVALID_TYPE":
                    # 無効な型名は「その型の子が0件」と区別できないまま黙って捨てられると、
                    # 呼び出し側が「網羅できた」と誤認する。走査は続けつつ(supersetを投げて
                    # 使える型だけ拾う呼び出し方はバージョン差の吸収として正当)、
                    # 型名を集めてレスポンスで必ず通知する。
                    # 同じ型が全ノードで失敗するため、ここで重複排除する。
                    if ctype not in _state["invalid_child_types"]:
                        _state["invalid_child_types"].append(ctype)
            return all_children

        def _build_node(obj_id: str, depth: int, parent_path: str = "") -> dict:
            """JSON出力用: ツリーノードを構築（uuidフィールドを保持: フォールバック変換用）"""
            node = {"uuid": obj_id}
            type_name, path = _get_meta(obj_id)
            node["type"] = type_name
            node["path"] = path
            properties = _get_properties(obj_id, fields)
            if properties:
                node["properties"] = properties

            if depth < max_depth:
                children = []
                for cid in _get_children_ids(obj_id):
                    child_node = _build_node(cid, depth + 1, path)
                    children.append(child_node)
                if children:
                    node["children"] = children
                    node["child_count"] = len(children)
            return node

        def _collect_dual(obj_id: str, depth: int, parent_path: str = ""):
            """CSV+Structure出力用: 子を持つノード→構造JSON、子なしノード→CSV行に振り分け。"""
            type_name, path = _get_meta(obj_id)
            child_ids = _get_children_ids(obj_id)

            if len(child_ids) > 0:
                folder_fields = ["Name", "Comment"]
                props = _get_properties(obj_id, folder_fields)
                struct_node = {
                    "type": type_name,
                    "path": path,
                    "name": props.get("Name", ""),
                    "comment": props.get("Comment", ""),
                    "depth": depth,
                }

                leaf_count = 0
                child_structs = []
                for cid in child_ids:
                    child_result = _collect_dual(cid, depth + 1, path)
                    if child_result is not None:
                        child_structs.append(child_result)
                    else:
                        leaf_count += 1

                struct_node["leaf_count"] = leaf_count
                if child_structs:
                    struct_node["children"] = child_structs
                return struct_node
            else:
                _collect_leaf(obj_id, depth, parent_path, type_name, path)
                return None

        def _collect_leaf(obj_id: str, depth: int, parent_path: str,
                           type_name: str = None, path: str = None):
            if _stopped():
                # 走査停止後のノードは行を追加しない（全滅時にプレースホルダ行で
                # 成功偽装になるのを防ぐ。停止前に収集済みの行はそのまま残る）
                return
            if type_name is None or path is None:
                type_name, path = _get_meta(obj_id)
            properties = _get_properties(obj_id, fields)
            row = {
                "depth": depth,
                "type": type_name,
                "path": path,
                "parent_path": parent_path,
                "uuid": obj_id,
            }
            for f in fields:
                row[f] = properties.get(f, "")
            csv_rows.append(row)

        def _warnings() -> list:
            """予算超過と無効child_typesの警告をまとめて返す。"""
            out = []
            if _state["budget_tripped"]:
                out.append(f"API call budget ({_MAX_TOTAL_CALLS}) exceeded; traversal stopped early.")
            if _state["invalid_child_types"]:
                names = ", ".join(_state["invalid_child_types"])
                out.append(
                    f"child_types のうち {names} は無効な型名のため検索されませんでした"
                    "(その型のオブジェクトが0件だったのではありません)。"
                    "有効な型名は docs/dev/CAPABILITIES.md または"
                    "atomcraft_get_object のobject_type例を参照してください。")
            return out

        def _is_partial() -> bool:
            return bool(_state["timed_out"] or _state["truncated"] or _state["infra_code"])

        def _infra_message_suffix() -> str:
            if _state["infra_code"]:
                return f"走査がインフラエラー({_state['infra_code']})で中断されました。結果は不完全です。"
            return ""

        def _infra_total_failure_error() -> str:
            """走査が最初から何も収集できずインフラエラーで終わった場合のエラー封筒。

            部分的にでも収集できていれば（partial=True の）成功として返すのが従来挙動
            （呼び出し側が中断位置を判断できるように）。何も収集できていない場合まで
            success:true の空スタブを返すと、呼び出し側が「空ツリーだった」と誤読しうるため、
            この場合のみエラーとして返す。
            """
            code = _state["infra_code"]
            retryable, hint = infra_hint(code)
            return make_error(
                f"走査がインフラエラー({code})で失敗しました。",
                code, hint=hint, retryable=retryable)

        try:
            if output_format == "csv":
                structure = _collect_dual(root, 0)

                if _state["infra_code"] and not csv_rows and (structure is None or not structure.get("children")):
                    return _infra_total_failure_error()

                base_dir = _resolve_output_dir(output_dir, settings)
                if not output_dir:
                    _cleanup_old_files(base_dir)
                csv_path, json_path, csv_columns = _write_tree_files(base_dir, csv_rows, fields, structure)

                infra_suffix = f" {_infra_message_suffix()}" if _state["infra_code"] else ""
                return make_success(
                    data={
                        "csv_file": csv_path,
                        "structure_file": json_path,
                        "csv_rows": len(csv_rows),
                        "csv_columns": csv_columns,
                        "structure": structure,
                        "timed_out": _state["timed_out"],
                        "truncated": _state["truncated"],
                        "partial": _is_partial(),
                        "invalid_child_types": list(_state["invalid_child_types"]),
                    },
                    message=f"Exported: {len(csv_rows)} data rows to CSV, structure to JSON{infra_suffix}",
                    warnings=_warnings() or None,
                )
            else:
                tree = _build_node(root, 0)

                if _state["infra_code"] and not tree.get("children") and not tree.get("properties"):
                    return _infra_total_failure_error()

                tree_json = json.dumps(tree, ensure_ascii=False)

                if len(tree_json) > settings.tree_json_budget:
                    fallback_rows, structure = _tree_to_rows(tree, fields)

                    base_dir = _resolve_output_dir(output_dir, settings)
                    if not output_dir:
                        _cleanup_old_files(base_dir)
                    csv_path, json_path, csv_columns = _write_tree_files(base_dir, fallback_rows, fields, structure)

                    fallback_message = ("JSONが予算超過のためCSV出力に自動切替。"
                                        "structure確認後、data.csvをDuckDB等で読んでください")
                    if _state["infra_code"]:
                        fallback_message = f"{fallback_message} {_infra_message_suffix()}"
                    return make_success(
                        data={
                            "csv_file": csv_path,
                            "structure_file": json_path,
                            "csv_rows": len(fallback_rows),
                            "csv_columns": csv_columns,
                            "structure": structure,
                            "timed_out": _state["timed_out"],
                            "truncated": _state["truncated"],
                            "auto_fallback": True,
                            "partial": _is_partial(),
                            "invalid_child_types": list(_state["invalid_child_types"]),
                        },
                        message=fallback_message,
                        warnings=_warnings() or None,
                    )

                return make_success(
                    data={
                        "tree": tree,
                        "timed_out": _state["timed_out"],
                        "truncated": _state["truncated"],
                        "partial": _is_partial(),
                        "invalid_child_types": list(_state["invalid_child_types"]),
                    },
                    message=_infra_message_suffix(),
                    warnings=_warnings() or None,
                )
        except Exception as e:
            return make_error(f"Tree traversal failed: {str(e)}", "API_ERROR")

    return [atomcraft_get_tree]
