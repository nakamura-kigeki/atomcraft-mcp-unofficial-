"""音声ファイル(マテリアル)の登録・情報取得ツール: atomcraft_manage_material

legacy/server.py:399-453 の変換版。

action="register" の失敗は envelope.classify の既存パターン
（"マテリアルの登録に失敗しました" → ALREADY_EXISTS）でそのまま分類される。
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import READ, NON_IDEMPOTENT

MaterialAction = Literal[
    "register", "register_unregistered", "get_info", "get_project_info",
    "get_root_folder", "get_project_root_folder",
]


def make_tools(t):
    p = t._robot.project

    def atomcraft_manage_material(
        action: MaterialAction,
        parent: Optional[str] = None,
        file_path: Optional[str] = None,
        material_folder: Optional[str] = None,
        workunit: Optional[str] = None,
    ) -> str:
        """音声ファイル(マテリアル)の登録・情報取得を行う。

        action:
          - register: ファイルをマテリアル登録 (parent, file_path必須)
          - register_unregistered: 未登録マテリアルを一括登録 (material_folder必須)
          - get_info: ワークユニットのマテリアル情報取得 (workunit必須)
          - get_project_info: プロジェクト全体のマテリアル情報取得
          - get_root_folder: ワークユニットのマテリアルルートフォルダ取得 (workunit必須)
          - get_project_root_folder: プロジェクトマテリアルルートフォルダ取得
        """
        if action == "register":
            if not parent or not file_path:
                return make_error(
                    "parent and file_path are required", "INVALID_PARAMS",
                    hint="action=registerにはparent（登録先フォルダUUID）とfile_pathが必要です")
            result = t.call(p.register_material, parent, file_path, idempotency=NON_IDEMPOTENT)

        elif action == "register_unregistered":
            if not material_folder:
                return make_error(
                    "material_folder is required", "INVALID_PARAMS",
                    hint="action=register_unregisteredにはmaterial_folder（UUID）が必要です")
            result = t.call(p.register_unregistered_materials, material_folder, idempotency=NON_IDEMPOTENT)

        elif action == "get_info":
            if not workunit:
                return make_error(
                    "workunit is required", "INVALID_PARAMS",
                    hint="action=get_infoにはworkunit（UUID）が必要です")
            result = t.call(p.get_materialinfo, workunit, idempotency=READ)

        elif action == "get_project_info":
            result = t.call(p.get_project_materialinfo, idempotency=READ)

        elif action == "get_root_folder":
            if not workunit:
                return make_error(
                    "workunit is required", "INVALID_PARAMS",
                    hint="action=get_root_folderにはworkunit（UUID）が必要です")
            result = t.call(p.get_material_rootfolder, workunit, idempotency=READ)

        elif action == "get_project_root_folder":
            result = t.call(p.get_project_material_rootfolder, idempotency=READ)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(MaterialAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    return [atomcraft_manage_material]
