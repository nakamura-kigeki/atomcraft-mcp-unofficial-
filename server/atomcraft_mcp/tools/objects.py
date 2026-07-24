"""オブジェクトのCRUDツール: get_object / create_object / modify_object

legacy/server.py:58-236 (atomcraft_get_object, atomcraft_create_object,
atomcraft_modify_object) の変換版。
"""
import json as _json
from typing import Literal, Optional

from ..envelope import from_result, make_error, make_success, classify
from ..transport import READ, IDEMPOTENT_WRITE, NON_IDEMPOTENT
from .. import catalog

GetObjectMethod = Literal[
    "find_by_name", "find_all_by_type", "get_by_path", "get_children",
    "get_child_by_name", "get_parent", "get_selected", "get_root",
    "get_global_folder", "get_workunit", "get_cuesheet_rootfolder",
    "get_material_rootfolder", "get_project_material_rootfolder",
]
ModifyAction = Literal["copy", "duplicate", "move", "delete", "select"]


def paginated_ids(result: dict, limit: int, offset: int) -> str:
    """ids配列を返すAPI結果をページングしてenvelope JSONにする（他toolsモジュールからも利用）。"""
    if not result.get("succeed"):
        return from_result(result)
    ids = result.get("data") or []
    return make_success(data={
        "ids": ids[offset:offset + limit],
        "total": len(ids),
        "truncated": len(ids) > offset + limit,
    })


def with_type_hint(response_json: str, object_type: str) -> str:
    """INVALID_TYPEエラーのhintをcatalog.type_hintの近似候補で上書きする（他toolsモジュールからも利用）。"""
    r = _json.loads(response_json)
    if not r.get("success") and r.get("code") == "INVALID_TYPE" and object_type:
        r["hint"] = catalog.type_hint(object_type)
    return _json.dumps(r, ensure_ascii=False)


def make_tools(t):
    p = t._robot.project

    def atomcraft_get_object(
        method: GetObjectMethod,
        object_type: Optional[str] = None,
        object_name: Optional[str] = None,
        search_root: Optional[str] = None,
        parent: Optional[str] = None,
        target: Optional[str] = None,
        object_path: Optional[str] = None,
        workunit: Optional[str] = None,
        workunit_name: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> str:
        """CRI Atom Craftプロジェクト内のオブジェクトを検索・取得する。

        method:
          - find_by_name: 名前とタイプで検索(object_type, object_name必須, search_root任意)
          - find_all_by_type: タイプで全件検索(object_type必須, search_root任意)
          - get_by_path: パス指定で取得(object_path必須)
          - get_children: 子オブジェクト列挙(parent, object_type必須)
          - get_child_by_name: 名前指定で子取得(parent, object_type, object_name必須)
          - get_parent: 親オブジェクト取得(target, object_type必須)
          - get_selected: UI上で選択中のオブジェクト取得(object_type必須)
          - get_root: プロジェクトルート取得(引数不要)
          - get_global_folder: グローバルフォルダ取得(object_type必須)
          - get_workunit: ワークユニット取得(workunit_name必須)
          - get_cuesheet_rootfolder: キューシートルートフォルダ(workunit必須)
          - get_material_rootfolder: マテリアルルートフォルダ(workunit必須)
          - get_project_material_rootfolder: プロジェクトマテリアルルートフォルダ(引数不要)

        object_type例: Project, WorkUnit, CueSheet, CueSheetFolder, Cue, Track, Synth,
                       Material, MaterialFolder, Bus, BusMaster, Mixer, AISAC, AISACControl,
                       SelectorLabel, Category, CategoryFolder

        limit/offset: リスト返却method（find_all_by_type, get_children, get_selected）の
                     ページング。data.total/data.truncatedで全件数・切り詰めの有無を返す。
        """
        if method == "find_by_name":
            if not object_type or not object_name:
                return make_error(
                    "object_type and object_name are required for find_by_name",
                    "INVALID_PARAMS",
                    hint="find_by_nameにはobject_type（例: CueSheet）とobject_nameが必要です")
            result = t.call(p.find_object, search_root, object_type, object_name, idempotency=READ)
            return with_type_hint(from_result(result), object_type)

        elif method == "find_all_by_type":
            if not object_type:
                return make_error(
                    "object_type is required for find_all_by_type", "INVALID_PARAMS",
                    hint="find_all_by_typeにはobject_type（例: Cue）が必要です")
            result = t.call(p.find_objects, search_root, object_type, idempotency=READ)
            return with_type_hint(paginated_ids(result, limit, offset), object_type)

        elif method == "get_by_path":
            if not object_path:
                return make_error(
                    "object_path is required for get_by_path", "INVALID_PARAMS",
                    hint="get_by_pathにはobject_pathが必要です")
            result = t.call(p.get_object_from_path, object_path, idempotency=READ)
            return from_result(result)

        elif method == "get_children":
            if not parent or not object_type:
                return make_error(
                    "parent and object_type are required for get_children", "INVALID_PARAMS",
                    hint="get_childrenにはparent（UUID）とobject_typeが必要です")
            result = t.call(p.get_child_objects, parent, object_type, idempotency=READ)
            return with_type_hint(paginated_ids(result, limit, offset), object_type)

        elif method == "get_child_by_name":
            if not parent or not object_type or not object_name:
                return make_error(
                    "parent, object_type, and object_name are required for get_child_by_name",
                    "INVALID_PARAMS",
                    hint="get_child_by_nameにはparent、object_type、object_nameが必要です")
            result = t.call(p.get_child_object, parent, object_type, object_name, idempotency=READ)
            return with_type_hint(from_result(result), object_type)

        elif method == "get_parent":
            if not target or not object_type:
                return make_error(
                    "target and object_type are required for get_parent", "INVALID_PARAMS",
                    hint="get_parentにはtarget（UUID）とobject_typeが必要です")
            result = t.call(p.get_parent, target, object_type, idempotency=READ)
            return with_type_hint(from_result(result), object_type)

        elif method == "get_selected":
            if not object_type:
                return make_error(
                    "object_type is required for get_selected", "INVALID_PARAMS",
                    hint="get_selectedにはobject_typeが必要です")
            result = t.call(p.get_selected_objects, object_type, idempotency=READ)
            return with_type_hint(paginated_ids(result, limit, offset), object_type)

        elif method == "get_root":
            result = t.call(p.get_root, idempotency=READ)
            return from_result(result)

        elif method == "get_global_folder":
            if not object_type:
                return make_error(
                    "object_type is required for get_global_folder", "INVALID_PARAMS",
                    hint="get_global_folderにはobject_typeが必要です")
            result = t.call(p.get_global_folder, object_type, idempotency=READ)
            return with_type_hint(from_result(result), object_type)

        elif method == "get_workunit":
            if not workunit_name:
                return make_error(
                    "workunit_name is required for get_workunit", "INVALID_PARAMS",
                    hint="get_workunitにはworkunit_nameが必要です")
            result = t.call(p.get_workunit, workunit_name, idempotency=READ)
            return from_result(result)

        elif method == "get_cuesheet_rootfolder":
            if not workunit:
                return make_error(
                    "workunit (UUID) is required for get_cuesheet_rootfolder", "INVALID_PARAMS",
                    hint="get_cuesheet_rootfolderにはworkunit（UUID）が必要です")
            result = t.call(p.get_cuesheet_rootfolder, workunit, idempotency=READ)
            return from_result(result)

        elif method == "get_material_rootfolder":
            if not workunit:
                return make_error(
                    "workunit (UUID) is required for get_material_rootfolder", "INVALID_PARAMS",
                    hint="get_material_rootfolderにはworkunit（UUID）が必要です")
            result = t.call(p.get_material_rootfolder, workunit, idempotency=READ)
            return from_result(result)

        elif method == "get_project_material_rootfolder":
            result = t.call(p.get_project_material_rootfolder, idempotency=READ)
            return from_result(result)

        else:
            return make_error(
                f"Unknown method: {method}. Valid methods: {', '.join(GetObjectMethod.__args__)}",
                "INVALID_PARAMS")

    def atomcraft_create_object(
        parent: str,
        object_type: str,
        object_name: str,
    ) -> str:
        """CRI Atom Craftプロジェクトに新しいオブジェクトを作成する。

        parent: 親オブジェクトのUUID
        object_type: 作成するタイプ名 (CueSheet, Cue, Track, CueSheetFolder, Bus, SelectorLabel, Category等)
        object_name: 作成するオブジェクトの名前
        """
        result = t.call(p.create_object, parent, object_type, object_name, idempotency=NON_IDEMPOTENT)
        return with_type_hint(from_result(result), object_type)

    def atomcraft_modify_object(
        action: ModifyAction,
        target: str,
        destination_parent: Optional[str] = None,
        destination_object: Optional[str] = None,
    ) -> str:
        """既存オブジェクトの複製、コピー、移動、削除、選択を行う。

        action: copy, duplicate, move, delete, select
        target: 操作対象のオブジェクトUUID
        destination_parent: コピー/移動先の親UUID (action=copy, moveで使用)
        destination_object: 移動先の位置指定UUID (action=moveで任意)
        """
        if action == "copy":
            if not destination_parent:
                return make_error(
                    "destination_parent is required for copy", "INVALID_PARAMS",
                    hint="action=copyにはdestination_parent（コピー先の親UUID）が必要です")
            result = t.call(p.copy_object, target, destination_parent, idempotency=NON_IDEMPOTENT)
        elif action == "duplicate":
            result = t.call(p.duplicate_object, target, idempotency=NON_IDEMPOTENT)
        elif action == "move":
            result = t.call(p.move_object, target, destination_parent, destination_object,
                            idempotency=NON_IDEMPOTENT)
        elif action == "delete":
            result = t.call(p.delete_object, target, idempotency=NON_IDEMPOTENT)
        elif action == "select":
            result = t.call(p.select_object, target, idempotency=IDEMPOTENT_WRITE)
        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(ModifyAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    return [atomcraft_get_object, atomcraft_create_object, atomcraft_modify_object]
