"""ツールバージョンの解析と機能ゲート。

新機能ツールは実APIを呼ぶ前に2つの条件を確認する:
  (1) robot Python側に対象関数が存在するか(hasattr) — 無ければ確実にブロック
  (2) 接続先ツールのバージョンが下限以上か — 取得できない場合はブロックしない
      (fail-open。バージョン取得が失敗する主因は接続断であり、その場合は
      実API呼び出しが同じエラー封筒で返るため二重ブロックは不要)
"""
import re
from .envelope import make_error

_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(s):
    m = _VER_RE.search(s or "")
    return tuple(int(g) for g in m.groups()) if m else None


def normalize_version_data(data):
    """get_tool_version の data は文字列("3.41.01")と辞書({"version": "Ver.3.57.02"})の
    両形状が確認されているため、どちらも受ける。"""
    if isinstance(data, str):
        return parse_version(data)
    if isinstance(data, dict):
        return parse_version(data.get("version", ""))
    return None


def _fmt(v):
    return ".".join(str(x) for x in v)


def require_feature(t, module_obj, func_name, min_version, feature):
    """(エラー封筒 or None, 実関数 or None) を返す機能ゲート。"""
    fn = getattr(module_obj, func_name, None)
    if not callable(fn):
        return make_error(
            f"{feature} は現在の Robot API に存在しません(robot-path の指す Python が古い可能性)",
            "UNSUPPORTED_VERSION",
            hint="ATOMCRAFT_ROBOT_PATH(または robot-path.txt)が、使用中の Atom Craft と"
                 f"同バージョンの robot\\remote\\Python を指しているか確認してください。"
                 f"{feature} には Ver.{_fmt(min_version)} 以降が必要です。",
            details={"required": _fmt(min_version), "probe": "callable_missing"}), None
    v = t.tool_version()
    if v is not None and v < min_version:
        return make_error(
            f"{feature} は Ver.{_fmt(min_version)} 以降の Atom Craft が必要です"
            f"(接続先: Ver.{_fmt(v)})",
            "UNSUPPORTED_VERSION",
            hint="接続先の CRI Atom Craft のバージョンが古いためこの機能は使えません。"
                 "ツールを更新するか、GUIで手動操作してください。",
            details={"required": _fmt(min_version), "detected": _fmt(v),
                     "probe": "version_too_old"}), None
    return None, fn
