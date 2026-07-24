"""ビート同期ツール: atomcraft_manage_beatsync

ビート同期トラック(create_beatsync_track)とビート同期情報(create_beatsync)の
作成を行う。どちらもrequire_featureによる機能ゲート付きで、対応バージョン未満の
接続先やrobot Python側に対象関数が存在しない場合はUNSUPPORTED_VERSIONを返す。
引数検証(parent/time_ms/bpm/numeratorの妥当性)はrequire_feature（バージョン取得・
接続を伴いうる）より先に行う（引数検証 → require_feature → t.call の順を厳守）。
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import NON_IDEMPOTENT
from ..versioning import require_feature

BeatsyncAction = Literal["create_track", "create"]

# 根拠は docs/api-versions.md の採用値(確度: 推定/低め)。
# create_beatsync / create_beatsync_track とも履歴文書に関数名の明記はなく、
# Ver.3.41.01には存在せずVer.3.57.02には存在することのみ確認済み。
# 安全側としてrequire_featureの関数存在チェック(callable_missing)を実質的な
# 防波堤とし、MIN_VERは低めのVer.3.45.0を暫定下限として採用する。
MIN_VER_BEATSYNC = (3, 45, 0)


def make_tools(t):
    pj = t._robot.project

    def atomcraft_manage_beatsync(
        action: BeatsyncAction,
        parent: str,
        time_ms: Optional[int] = None,
        bpm: float = 120.0,
        numerator: int = 4,
        beat_pattern: Optional[list] = None,
        label: Optional[str] = None,
    ) -> str:
        """ビート同期トラック・ビート同期情報を作成する。

        action: create_track (トラック作成。parent=タイムライン系オブジェクトのUUID),
                create (ビート同期情報作成。parent=ビート同期トラックのUUID, time_ms必須)
        beat_pattern: 拍パターン文字列のリスト (action=createで任意)
        label: ビート同期ラベル (任意)
        """
        if not parent:
            return make_error("parent is required", "INVALID_PARAMS",
                              hint="親オブジェクトのUUIDを指定してください")

        if action == "create_track":
            err, fn = require_feature(t, pj, "create_beatsync_track",
                                      MIN_VER_BEATSYNC, "ビート同期")
            if err:
                return err
            result = t.call(fn, parent, label, idempotency=NON_IDEMPOTENT)

        elif action == "create":
            if time_ms is None or time_ms < 0:
                return make_error("time_ms (>= 0) is required for create", "INVALID_PARAMS",
                                  hint="action=createにはtime_ms(配置時刻ミリ秒)が必要です")
            if bpm <= 0 or numerator <= 0:
                return make_error("bpm and numerator must be positive", "INVALID_PARAMS",
                                  hint="bpmとnumeratorは正の値である必要があります")
            err, fn = require_feature(t, pj, "create_beatsync",
                                      MIN_VER_BEATSYNC, "ビート同期")
            if err:
                return err
            result = t.call(fn, parent, time_ms, bpm, numerator,
                            beat_pattern or [], label, idempotency=NON_IDEMPOTENT)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(BeatsyncAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    return [atomcraft_manage_beatsync]
