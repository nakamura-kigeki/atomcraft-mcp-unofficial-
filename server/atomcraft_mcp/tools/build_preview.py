"""ビルド・プレビューツール: atomcraft_build / atomcraft_preview

legacy/server.py:845-904 の変換版。

atomcraft_buildはlegacyにない新規引数timeout_secを公開する（NON_IDEMPOTENTかつ
長時間かかり得るため、呼び出し側でtransportのデフォルトタイムアウトを上書きできるように
している）。

atomcraft_previewはVer.3.47.0以降で追加された3アクション
（get_playback_state / start_ingame_preview / stop_ingame_preview）に対応する。
これらはrequire_featureによる機能ゲート付きで、対応バージョン未満の接続先や
robot Python側に対象関数が存在しない場合はUNSUPPORTED_VERSIONを返す。
引数不足の場合はrequire_feature（バージョン取得・接続を伴いうる）より先に
INVALID_PARAMSで返す（引数検証 → require_feature → t.call の順を厳守）。
"""
import math
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import IDEMPOTENT_WRITE, NON_IDEMPOTENT, READ
from ..versioning import require_feature

BuildAction = Literal["build", "clean_all"]
PreviewAction = Literal["play", "stop_all", "get_playback_state",
                        "start_ingame_preview", "stop_ingame_preview"]

# 根拠は docs/api-versions.md の採用値。
# start_ingame_preview / stop_ingame_preview は変更履歴に関数名が明記され確定。
# get_playback_state は同時期追加の推定（安全側で同じ下限を採用し、
# 実際の防波堤はrequire_featureの関数存在チェックに委ねる）。
MIN_VER_PREVIEW_STATE = (3, 47, 0)
MIN_VER_INGAME = (3, 47, 0)


def make_tools(t):
    b = t._robot.build
    pv = t._robot.preview

    def atomcraft_build(
        action: BuildAction,
        cuesheet: Optional[str] = None,
        target: Optional[str] = None,
        language: Optional[str] = None,
        timeout_sec: Optional[float] = None,
    ) -> str:
        """キューシートのビルドまたはビルドキャッシュのクリーンを実行する。

        action: build (キューシートビルド), clean_all (全ビルドキャッシュクリーン)
        cuesheet: ビルド対象キューシートのUUID (action=buildで必須)
        target: ターゲットコンフィグのUUID (action=buildで必須)
        language: 言語設定のUUID (action=buildで任意)
        timeout_sec: ビルドのタイムアウト秒数 (action=buildで任意。省略時はサーバー既定値。
            0より大きい有限の数値のみ許可。0・負数・NaN・infはINVALID_PARAMS)
        """
        if action == "build":
            if not cuesheet or not target:
                return make_error(
                    "cuesheet and target are required for build", "INVALID_PARAMS",
                    hint="action=buildにはcuesheetとtargetが必要です")
            if timeout_sec is not None:
                if (isinstance(timeout_sec, bool)
                        or not isinstance(timeout_sec, (int, float))
                        or not math.isfinite(timeout_sec)
                        or timeout_sec <= 0):
                    return make_error(
                        f"timeout_sec must be a positive finite number, got {timeout_sec}",
                        "INVALID_PARAMS",
                        hint="timeout_secは0より大きい有限の数値を指定してください")
            result = t.call(b.build_cuesheet, cuesheet, target, language,
                            idempotency=NON_IDEMPOTENT, timeout=timeout_sec)

        elif action == "clean_all":
            result = t.call(b.clean_all, idempotency=NON_IDEMPOTENT)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(BuildAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    def atomcraft_preview(
        action: PreviewAction,
        cue: Optional[str] = None,
        target: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """キューの再生プレビューを開始・停止、または再生状態・インゲームプレビューを操作する。

        action:
          play (キュー再生開始), stop_all (全再生停止),
          get_playback_state (再生状態取得。Ver.3.47.0以降),
          start_ingame_preview (インゲームプレビュー開始。Ver.3.47.0以降),
          stop_ingame_preview (インゲームプレビュー停止。Ver.3.47.0以降)
        cue: 再生する/状態を取得するキューのUUID (action=play, get_playback_stateで必須)
        target: ターゲットコンフィグ種別のUUID (action=start_ingame_previewで必須)
        ip_address: 接続先IPアドレス (action=start_ingame_previewで必須)
        """
        if action == "play":
            if not cue:
                return make_error(
                    "cue is required for play", "INVALID_PARAMS",
                    hint="action=playにはcueが必要です")
            result = t.call(pv.start_playback_cue, cue, idempotency=IDEMPOTENT_WRITE)

        elif action == "stop_all":
            result = t.call(pv.stop_all, idempotency=IDEMPOTENT_WRITE)

        elif action == "get_playback_state":
            if not cue:
                return make_error(
                    "cue is required for get_playback_state", "INVALID_PARAMS",
                    hint="action=get_playback_stateにはcueが必要です")
            err, fn = require_feature(t, pv, "get_playback_state",
                                      MIN_VER_PREVIEW_STATE, "再生状態取得")
            if err:
                return err
            result = t.call(fn, cue, idempotency=READ)

        elif action == "start_ingame_preview":
            if not target or not ip_address:
                return make_error(
                    "target and ip_address are required for start_ingame_preview",
                    "INVALID_PARAMS",
                    hint="action=start_ingame_previewにはtargetとip_addressが必要です")
            err, fn = require_feature(t, pv, "start_ingame_preview",
                                      MIN_VER_INGAME, "インゲームプレビュー")
            if err:
                return err
            result = t.call(fn, target, ip_address, idempotency=IDEMPOTENT_WRITE)

        elif action == "stop_ingame_preview":
            err, fn = require_feature(t, pv, "stop_ingame_preview",
                                      MIN_VER_INGAME, "インゲームプレビュー")
            if err:
                return err
            result = t.call(fn, idempotency=IDEMPOTENT_WRITE)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(PreviewAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    return [atomcraft_build, atomcraft_preview]
