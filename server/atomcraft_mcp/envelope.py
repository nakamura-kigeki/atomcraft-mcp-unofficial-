"""レスポンス封筒とエラー分類。

Atom Craft側の生エラーメッセージをパターン表で12種のコードに分類し、
呼び出し側LLMが次の一手を判断できる hint / retryable を必ず付ける。
"""
import json
import re
from dataclasses import dataclass, field

CODES = frozenset({
    "SERVER_UNREACHABLE", "CONNECTION_LOST", "TIMEOUT", "INVALID_PARAMS",
    "INVALID_FIELD", "INVALID_TYPE", "NOT_FOUND", "ALREADY_EXISTS",
    "PARSE_ERROR", "UNKNOWN_OUTCOME", "API_ERROR", "UNSUPPORTED_VERSION",
})

HINT_CONNECTION_RECOVERY = (
    "復旧手順: (1) Atom Craft側でスクリプトサーバーが起動しているか確認"
    "（スクリプトメニュー > サーバー > スクリプトサーバーを起動） "
    "(2) atomcraft_debug(action='reconnect') を実行 "
    "(3) それでも失敗する場合はMCPクライアントを再起動"
)

_HINT_INVALID_FIELD = (
    "フィールド名を確認してください。Cueで利用可能: Name, Comment, CueID, Volume, Pitch, "
    "SequenceType, UserData, CuePriority。カテゴリは atomcraft_manage_category(action='get')、"
    "バスマップは atomcraft_manage_busmap(action='get_for_cue') で取得します（get_propertyでは取れません）。"
)

_HINT_ALREADY_EXISTS = (
    "既に登録済みの可能性があります。atomcraft_get_object(method='find_by_name') で"
    "既存オブジェクトのUUIDを検索し、見つかればそれを流用してください。"
)


@dataclass
class Classified:
    code: str
    hint: str = ""
    retryable: bool = False
    details: dict = field(default_factory=dict)


# (正規表現, code, retryable, hint, detailsキー名) のパターン表。上から順に評価。
_PATTERNS = [
    (re.compile(r"指定したフィールド \[(?P<v>[^\]]+)\] は利用できません"),
     "INVALID_FIELD", False, _HINT_INVALID_FIELD, "invalid_fields"),
    (re.compile(r"指定したタイプ \[(?P<v>[^\]]+)\] は現在利用できません"),
     "INVALID_TYPE", False,
     "このmethodでは使えないタイプ名です。docstringのobject_type例から選ぶか、"
     "ルートフォルダ系は専用method（get_project_material_rootfolder等）を使ってください。",
     "invalid_type"),
    (re.compile(r"マテリアルの登録に失敗しました"),
     "ALREADY_EXISTS", False, _HINT_ALREADY_EXISTS, None),
    (re.compile(r"failed to parse", re.IGNORECASE),
     "PARSE_ERROR", True,
     "Atom Craft応答の解析に失敗しました。読み取り系なら自動リトライ済みです。"
     "繰り返す場合は日本語パス起因の可能性があります。", None),
    (re.compile(r"見つかりません|存在しません|not found", re.IGNORECASE),
     "NOT_FOUND", False,
     "対象が存在しません。UUIDは atomcraft_get_object(method='find_by_name') で取得した値を使ってください。",
     None),
    (re.compile(r"not connected|lost connection|connection reset|connection refused|connection closed", re.IGNORECASE),
     "CONNECTION_LOST", True, HINT_CONNECTION_RECOVERY, None),
]


def classify(message: str) -> Classified:
    message = message or ""
    for pattern, code, retryable, hint, details_key in _PATTERNS:
        m = pattern.search(message)
        if m:
            details = {}
            if details_key:
                value = m.group("v")
                if details_key.endswith("s"):
                    details[details_key] = [part.strip() for part in value.split(", ")]
                else:
                    details[details_key] = value
            return Classified(code=code, hint=hint, retryable=retryable, details=details)
    return Classified(code="API_ERROR", hint="", retryable=False)


def make_success(data=None, message: str = "", warnings=None) -> str:
    payload = {"success": True, "data": data, "message": message}
    if warnings:
        payload["warnings"] = warnings
    return json.dumps(payload, ensure_ascii=False)


def make_error(error: str, code: str = "API_ERROR", hint: str = None,
               retryable: bool = False, details: dict = None) -> str:
    if code not in CODES:
        raise ValueError(f"unknown error code: {code}")
    payload = {"success": False, "code": code, "error": error,
               "hint": hint or "", "retryable": retryable}
    if details:
        payload["details"] = details
    return json.dumps(payload, ensure_ascii=False)


# インフラ系_codeに対応する retryable / hint（transportが設定する）
_INFRA = {
    "TIMEOUT": (True, "タイムアウトしました。接続はリセット済みです。読み取り系なら再実行してください。"
                      "書き込み系は先に対象の存在を確認してから再実行してください。"),
    "SERVER_UNREACHABLE": (False, HINT_CONNECTION_RECOVERY),
    "CONNECTION_LOST": (True, HINT_CONNECTION_RECOVERY),
    "UNKNOWN_OUTCOME": (False,
        "書き込み操作の結果が確認できませんでした（送信後に接続断/タイムアウト）。"
        "atomcraft_get_object(method='find_by_name')等で作成済みかを確認してから再実行してください。"),
    "PARSE_ERROR": (True, "Atom Craft応答の解析に失敗しました。読み取り系なら自動リトライ済みです。"
                          "繰り返す場合は日本語パス起因の可能性があります。"),
}


def infra_hint(code: str) -> tuple:
    """インフラ系_codeに対応する (retryable, hint) を返す公開アクセサ。

    _INFRA は本モジュール内でtransportが設定する_codeの意味を集約したテーブルであり、
    private命名（アンダースコア始まり）のため他モジュールから直接参照させず、
    このアクセサ経由で読ませる。未知のcodeには (False, "") を返す。
    """
    return _INFRA.get(code, (False, ""))


def from_result(result: dict) -> str:
    if result.get("succeed"):
        return make_success(data=result.get("data"), message=result.get("message", ""))
    message = result.get("message", "Unknown error")
    infra_code = result.get("_code")
    if infra_code in _INFRA:
        retryable, hint = _INFRA[infra_code]
        return make_error(message, infra_code, hint=hint, retryable=retryable)
    c = classify(message)
    return make_error(message, c.code, hint=c.hint, retryable=c.retryable,
                      details=c.details or None)
