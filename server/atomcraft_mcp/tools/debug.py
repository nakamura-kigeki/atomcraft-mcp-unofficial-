"""デバッグ・診断ツール: atomcraft_debug

action="reconnect"は `t.full_reset()` → `t.connect()` を行い、pingで再接続を確認する。
action="status"はtransportのstatus()（dll_statusを含む）をそのまま返す。
"""
from typing import Literal, Optional

from ..envelope import HINT_CONNECTION_RECOVERY, from_result, make_error, make_success
from ..transport import READ, IDEMPOTENT_WRITE

DebugAction = Literal[
    "ping", "reconnect", "status", "log", "warning", "clear_log", "get_version",
]


def make_tools(t):
    d = t._robot.debug

    def atomcraft_debug(
        action: DebugAction,
        message: Optional[str] = None,
    ) -> str:
        """Atom Craftへの接続確認、再接続、ログ出力、バージョン情報取得を行う。

        action:
          - ping: 接続確認
          - reconnect: 切断→再接続（スクリプトサーバー再起動後に使用）
          - status: 接続状態の詳細を取得
          - log: ログ送信 (message必須)
          - warning: 警告送信 (message必須)
          - clear_log: ログクリア
          - get_version: バージョン取得
        message: ログ/警告メッセージ (action=log, warningで必須)
        """
        if action == "ping":
            result = t.call(d.ping, idempotency=READ)
            if result.get("succeed"):
                return make_success(message="Connection alive")
            return from_result(result)

        elif action == "reconnect":
            t.full_reset()
            if t.connect():
                result = t.call(d.ping, idempotency=READ)
                if result.get("succeed"):
                    return make_success(
                        message=f"Reconnected to Atom Craft at {t.host}:{t.port}")
                return make_error(
                    "Reconnected but ping failed. Check if script server is running.",
                    "SERVER_UNREACHABLE", hint=HINT_CONNECTION_RECOVERY)
            return make_error(
                f"Failed to reconnect to {t.host}:{t.port}. "
                "Ensure Atom Craft is running and script server is enabled.",
                "SERVER_UNREACHABLE", hint=HINT_CONNECTION_RECOVERY)

        elif action == "status":
            return make_success(data=t.status())

        elif action == "log":
            if not message:
                return make_error(
                    "message is required", "INVALID_PARAMS",
                    hint="action=logにはmessageが必要です")
            result = t.call(d.log, message, idempotency=IDEMPOTENT_WRITE)
            return from_result(result)

        elif action == "warning":
            if not message:
                return make_error(
                    "message is required", "INVALID_PARAMS",
                    hint="action=warningにはmessageが必要です")
            result = t.call(d.warning, message, idempotency=IDEMPOTENT_WRITE)
            return from_result(result)

        elif action == "clear_log":
            result = t.call(d.clear_log, idempotency=IDEMPOTENT_WRITE)
            return from_result(result)

        elif action == "get_version":
            result = t.call(d.get_tool_version, idempotency=READ)
            if result.get("succeed"):
                return make_success(data={"version": result.get("data")})
            return from_result(result)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(DebugAction.__args__)}",
                "INVALID_PARAMS")

    return [atomcraft_debug]
