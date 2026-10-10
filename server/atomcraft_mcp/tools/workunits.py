"""ワークユニット管理・プロジェクトファイル操作ツール:
atomcraft_manage_workunit / atomcraft_project_io
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import READ, IDEMPOTENT_WRITE, NON_IDEMPOTENT

WorkunitAction = Literal[
    "create", "delete", "get", "save", "exclude", "include", "get_cuesheet_rootfolder",
]
ProjectIOAction = Literal["create", "open", "save_all"]


def make_tools(t):
    p = t._robot.project

    def atomcraft_manage_workunit(
        action: WorkunitAction,
        workunit_name: Optional[str] = None,
        workunit: Optional[str] = None,
        use_individual_material: bool = False,
        default_busmap: Optional[str] = None,
    ) -> str:
        """ワークユニットの作成・削除・保存・除外・取り込みを行う。

        action: create, delete, get, save, exclude, include, get_cuesheet_rootfolder
        workunit_name: ワークユニット名 (action=create, delete, get, includeで必須)
        workunit: ワークユニットUUID (action=save, exclude, get_cuesheet_rootfolderで必須)
        use_individual_material: 個別マテリアルフォルダ使用 (action=createで任意)
        default_busmap: デフォルトバスマップUUID (action=createで任意)
        """
        if action == "create":
            if not workunit_name:
                return make_error(
                    "workunit_name is required", "INVALID_PARAMS",
                    hint="action=createにはworkunit_nameが必要です")
            result = t.call(p.create_workunit, workunit_name, use_individual_material, default_busmap,
                            idempotency=NON_IDEMPOTENT)

        elif action == "delete":
            if not workunit_name:
                return make_error(
                    "workunit_name is required", "INVALID_PARAMS",
                    hint="action=deleteにはworkunit_nameが必要です")
            result = t.call(p.delete_workunit, workunit_name, idempotency=NON_IDEMPOTENT)

        elif action == "get":
            if not workunit_name:
                return make_error(
                    "workunit_name is required", "INVALID_PARAMS",
                    hint="action=getにはworkunit_nameが必要です")
            result = t.call(p.get_workunit, workunit_name, idempotency=READ)

        elif action == "save":
            if not workunit:
                return make_error(
                    "workunit (UUID) is required", "INVALID_PARAMS",
                    hint="action=saveにはworkunit（UUID）が必要です")
            result = t.call(p.save_workunit, workunit, idempotency=IDEMPOTENT_WRITE)

        elif action == "exclude":
            if not workunit:
                return make_error(
                    "workunit (UUID) is required", "INVALID_PARAMS",
                    hint="action=excludeにはworkunit（UUID）が必要です")
            result = t.call(p.exclude_workunit, workunit, idempotency=IDEMPOTENT_WRITE)

        elif action == "include":
            if not workunit_name:
                return make_error(
                    "workunit_name is required", "INVALID_PARAMS",
                    hint="action=includeにはworkunit_nameが必要です")
            result = t.call(p.include_workunit, workunit_name, idempotency=IDEMPOTENT_WRITE)

        elif action == "get_cuesheet_rootfolder":
            if not workunit:
                return make_error(
                    "workunit (UUID) is required", "INVALID_PARAMS",
                    hint="action=get_cuesheet_rootfolderにはworkunit（UUID）が必要です")
            result = t.call(p.get_cuesheet_rootfolder, workunit, idempotency=READ)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(WorkunitAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    def atomcraft_project_io(
        action: ProjectIOAction,
        project_root_folder: Optional[str] = None,
        project_name: Optional[str] = None,
        overwrite: bool = False,
        file_path: Optional[str] = None,
    ) -> str:
        """プロジェクトの新規作成・開く・全保存を行う。

        action: create (新規作成), open (開く), save_all (全保存)
        project_root_folder: プロジェクトルートフォルダパス (action=createで必須)
        project_name: プロジェクト名 (action=createで必須)
        overwrite: 既存上書きするか (action=createで任意, デフォルトfalse)
        file_path: プロジェクトファイルパス (.atmcproject) (action=openで必須)
        """
        if action == "create":
            if not project_root_folder or not project_name:
                return make_error(
                    "project_root_folder and project_name are required", "INVALID_PARAMS",
                    hint="action=createにはproject_root_folderとproject_nameが必要です")
            result = t.call(p.create_project, project_root_folder, project_name, overwrite,
                            idempotency=NON_IDEMPOTENT)

        elif action == "open":
            if not file_path:
                return make_error(
                    "file_path is required", "INVALID_PARAMS",
                    hint="action=openにはfile_path（.atmcproject）が必要です")
            result = t.call(p.open_project, file_path, idempotency=IDEMPOTENT_WRITE)

        elif action == "save_all":
            result = t.call(p.save_project_all, idempotency=IDEMPOTENT_WRITE)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(ProjectIOAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    return [atomcraft_manage_workunit, atomcraft_project_io]
