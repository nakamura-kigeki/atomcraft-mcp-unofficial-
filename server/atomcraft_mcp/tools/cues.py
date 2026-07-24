"""キュー作成・ブックマーク管理ツール: atomcraft_create_cue / atomcraft_manage_bookmark

legacy/server.py:580-662 (atomcraft_manage_bookmark, atomcraft_create_cue) の変換版。

manage_bookmarkのaction=listはlegacyでは{"ids": ...}を裸で返していたが、
ブックマーク件数が多い場合の切り詰め安全性のためobjects.paginated_idsに合わせた
（total/truncatedが付与される。ids配下の内容自体はlegacyと同一）。
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import READ, NON_IDEMPOTENT
from .objects import paginated_ids

CreateCueMethod = Literal["simple", "cuelink", "external_cuelink", "waveform_region"]
BookmarkAction = Literal["add", "remove", "list"]


def make_tools(t):
    p = t._robot.project

    def atomcraft_create_cue(
        method: CreateCueMethod,
        parent: str,
        material: Optional[str] = None,
        cue: Optional[str] = None,
        link_cue_name: Optional[str] = None,
        link_cue_id: Optional[int] = None,
    ) -> str:
        """キューを作成する。

        method:
          - simple: マテリアルからシンプルキュー作成 (parent=CueSheet/CueFolder, material必須)
          - cuelink: 既存キューへのリンク (parent, cue必須)
          - external_cuelink: 外部キューリンク (parent, link_cue_nameかlink_cue_id必須)
          - waveform_region: 既存トラックにウェーブフォームリージョン追加 (parent=Track, material必須)
        """
        if method == "simple":
            if not material:
                return make_error(
                    "material is required for simple cue", "INVALID_PARAMS",
                    hint="method=simpleにはmaterialが必要です")
            result = t.call(p.create_simple_cue, parent, material, idempotency=NON_IDEMPOTENT)

        elif method == "cuelink":
            if not cue:
                return make_error(
                    "cue is required for cuelink", "INVALID_PARAMS",
                    hint="method=cuelinkにはcue（リンク先キューUUID）が必要です")
            result = t.call(p.create_cuelink, parent, cue, idempotency=NON_IDEMPOTENT)

        elif method == "external_cuelink":
            if not link_cue_name and link_cue_id is None:
                return make_error(
                    "link_cue_name or link_cue_id is required", "INVALID_PARAMS",
                    hint="method=external_cuelinkにはlink_cue_nameかlink_cue_idのいずれかが必要です")
            result = t.call(p.create_external_cuelink, parent, link_cue_name, link_cue_id,
                            idempotency=NON_IDEMPOTENT)

        elif method == "waveform_region":
            if not material:
                return make_error(
                    "material is required for waveform_region", "INVALID_PARAMS",
                    hint="method=waveform_regionにはmaterialが必要です")
            result = t.call(p.create_waveform_region, parent, material, idempotency=NON_IDEMPOTENT)

        else:
            return make_error(
                f"Unknown method: {method}. Valid methods: {', '.join(CreateCueMethod.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    def atomcraft_manage_bookmark(
        action: BookmarkAction,
        target: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> str:
        """ブックマークの追加・削除・一覧取得を行う。

        action: add (追加), remove (削除), list (一覧取得)
        target: 対象オブジェクトUUID (action=add, removeで必須)
        limit/offset: action=listの結果ページング。data.total/data.truncatedで全件数・切り詰めの有無を返す。
        """
        if action == "add":
            if not target:
                return make_error(
                    "target is required", "INVALID_PARAMS",
                    hint="action=addにはtarget（UUID）が必要です")
            result = t.call(p.add_bookmark, target, idempotency=NON_IDEMPOTENT)
            return from_result(result)

        elif action == "remove":
            if not target:
                return make_error(
                    "target is required", "INVALID_PARAMS",
                    hint="action=removeにはtarget（UUID）が必要です")
            result = t.call(p.remove_bookmark, target, idempotency=NON_IDEMPOTENT)
            return from_result(result)

        elif action == "list":
            result = t.call(p.get_bookmarks, idempotency=READ)
            return paginated_ids(result, limit, offset)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(BookmarkAction.__args__)}",
                "INVALID_PARAMS")

    return [atomcraft_create_cue, atomcraft_manage_bookmark]
