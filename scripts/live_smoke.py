"""実機スモークテスト: 起動中の CRI Atom Craft スクリプトサーバーに対して、

atomcraft_mcp のツール関数を MCP を介さず直接呼び出し、新旧APIが実機で
動作することを確認する。

前提:
- CRI Atom Craft が起動しており、スクリプトメニュー > サーバー > スクリプトサーバーが
  有効になっていること
- server/robot-path.txt (または ATOMCRAFT_ROBOT_PATH 環境変数) が接続中の
  Atom Craft と同バージョンの robot\\remote\\Python を指していること

安全対策(プロジェクト汚染防止):
- 作成系のlabelには mcp_smoke_ プレフィックスを付ける
- 作成したオブジェクトは可能な限りその場で削除を試みる(ベストエフォート)
- 既存オブジェクトのプロパティを一時的に書き換える場合は、必ず元の値を
  読み取ってから書き換え、最後に元の値へ復元する
- プロジェクト保存の検証(project_io save_all)は、%TEMP% 配下に新規作成した
  プロジェクトに対してのみ行い、デモプロジェクト自体は保存しない
- 終了時に transport.finalize() で接続を明示的に切断する
  (切断せずにプロセスを終了すると、スクリプトサーバー側が旧クライアント接続を
  握ったままになり、次回起動時のping接続が失敗し続けることがある)

このスクリプトはリポジトリにコミットされる成果物のため、個人パスやNG語を
コード内に直接書かない。robot-path の解決は atomcraft_mcp.robot と同じ
resolve_robot_path / robot.load をそのまま再利用する。
"""
import json
import os
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.join(_HERE, "..", "server")
sys.path.insert(0, _SERVER_DIR)

# Windowsコンソール(既定cp932)でも日本語メッセージが文字化けしないようにする
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from atomcraft_mcp import config, robot  # noqa: E402
from atomcraft_mcp.robot import RobotPathError  # noqa: E402
from atomcraft_mcp.transport import AtomCraftTransport, READ, IDEMPOTENT_WRITE, NON_IDEMPOTENT  # noqa: E402
from atomcraft_mcp.tools import debug as debug_tools  # noqa: E402
from atomcraft_mcp.tools import tree as tree_tools  # noqa: E402
from atomcraft_mcp.tools import objects as object_tools  # noqa: E402
from atomcraft_mcp.tools import build_preview as build_preview_tools  # noqa: E402
from atomcraft_mcp.tools import beatsync as beatsync_tools  # noqa: E402
from atomcraft_mcp.tools import properties as properties_tools  # noqa: E402

LABEL_PREFIX = "mcp_smoke_"
PING_MAX_ATTEMPTS = 3  # 初回 + リトライ2回まで(無限リトライ禁止)
PING_RETRY_DELAY_SEC = 2
# project_io系(create_project/save_all)はGUIモーダルで応答がブロックされうるため、
# 既定の30秒より長め・かつ明示的な上限を設ける(タイムアウトしたら諦めて次へ進む)
PROJECT_IO_TIMEOUT_SEC = 60

RESULTS = []  # [{"tool", "action", "success", "code", "note"}]
_RESULTS_DUMP_PATH = os.path.join(tempfile.gettempdir(), "atomcraft_mcp_live_smoke_last_run.txt")


def dump_results_to_file() -> None:
    """途中で処理が止まっても進捗を失わないよう、随時ファイルへも書き出す
    (Bashツールの出力キャプチャに依存しない独立の記録先)。"""
    try:
        with open(_RESULTS_DUMP_PATH, "w", encoding="utf-8") as f:
            for r in RESULTS:
                f.write(f"{r['tool']}\t{r['action']}\t{r['success']}\t{r['code']}\t{r['note']}\n")
    except OSError:
        pass


def record(tool: str, action: str, success: bool, code: str = "", note: str = "") -> None:
    RESULTS.append({
        "tool": tool,
        "action": action,
        "success": bool(success),
        "code": code or "",
        "note": (note or "")[:160],
    })
    dump_results_to_file()  # 1件ごとに書き出す(途中停止しても進捗が残るように)


def envelope(raw_json: str) -> dict:
    try:
        return json.loads(raw_json)
    except (TypeError, ValueError):
        return {"success": False, "code": "PARSE_ERROR", "error": "envelope JSON decode failed"}


def print_table() -> None:
    headers = ["tool", "action", "success", "code", "note"]
    rows = [[str(r[h]) for h in headers] for r in RESULTS]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells):
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


def _get_property(prop_fns, target, field):
    return envelope(prop_fns["atomcraft_get_property"](target=target, fields=[field]))


def _discover(t, object_fns, tree_fns, settings):
    """get_root / get_tree(浅め) / 既存Cue・Track列挙。戻り値: (root_uuid, existing_cues, existing_track)"""
    root_uuid = None
    env = envelope(object_fns["atomcraft_get_object"](method="get_root"))
    record("atomcraft_get_object", "get_root", env.get("success", False), env.get("code", ""))
    if env.get("success"):
        root_uuid = env.get("data")

    if root_uuid:
        env = envelope(tree_fns["atomcraft_get_tree"](
            root=root_uuid, child_types=["WorkUnit"], fields=["Name"],
            max_depth=1, max_children=50))
        note = ""
        if env.get("success"):
            tree_data = env.get("data", {})
            children = (tree_data.get("tree") or {}).get("children") or []
            note = f"WorkUnit数={len(children)}"
        record("atomcraft_get_tree", "get_tree(WorkUnit,depth=1)", env.get("success", False),
               env.get("code", ""), note)
    else:
        record("atomcraft_get_tree", "get_tree(WorkUnit,depth=1)", False, "SKIPPED",
               "get_rootが失敗したため未実行")

    existing_cues = []
    env = envelope(object_fns["atomcraft_get_object"](method="find_all_by_type", object_type="Cue"))
    record("atomcraft_get_object", "find_all_by_type(Cue)", env.get("success", False), env.get("code", ""))
    if env.get("success"):
        ids = (env.get("data") or {}).get("ids") or []
        existing_cues = ids[:2]

    existing_track = None
    env = envelope(object_fns["atomcraft_get_object"](method="find_all_by_type", object_type="Track"))
    record("atomcraft_get_object", "find_all_by_type(Track)", env.get("success", False), env.get("code", ""))
    if env.get("success"):
        ids = (env.get("data") or {}).get("ids") or []
        if ids:
            existing_track = ids[0]

    return root_uuid, existing_cues, existing_track


def _bulk_property_get_safe(prop_fns, existing_cues):
    """(a) 現行ラッパー経由(field_names=リスト)。前回・前々回と同一の失敗を
    再現するだけの、接続への影響が少ない安全な実験。"""
    if not existing_cues:
        record("atomcraft_bulk_property", "get", False, "SKIPPED", "対象Cueが見つからず")
        return
    env = envelope(prop_fns["atomcraft_bulk_property"](
        action="get", targets=existing_cues, field_names=["Name"]))
    note = "" if env.get("success") else env.get("error", "")
    record("atomcraft_bulk_property", "(a)現行ラッパー get(field_names=[Name])",
           env.get("success", False), env.get("code", ""), note)


def _bulk_property_get_risky(t, existing_cues):
    """bulk_property get の引数形式を実機で切り分ける、接続断リスクのある実験。

    CRIローカルマニュアル/公式Webリファレンスの調査で、
    get_value_from_targets(targets, field_name) の field_name は単一文字列であり、
    リストではないことが判明している(properties.pyの現行実装はリストを渡している)。
    前回の実行では単一文字列での直接呼び出しがPARSE_ERRORとなり、直後から
    接続がSERVER_UNREACHABLEになった(切り分け未了)。そのため、この実験は
    playback/beatsync等の重要な検証を済ませたあと、接続が失われても影響が
    小さい順序で最後の方に実行する。
    """
    if not existing_cues:
        record("atomcraft_mcp.robot.project", "(b)直接呼び出し get_value_from_targets",
               False, "SKIPPED", "対象Cueが見つからず")
        return

    # (b) ロボットAPI関数を単一文字列で直接呼び出し(ラッパーをバイパス)
    raw = t.call(t._robot.project.get_value_from_targets, existing_cues, "Name", idempotency=READ)
    note_b = "" if raw.get("succeed") else raw.get("message", "")
    record("atomcraft_mcp.robot.project", '(b)直接呼び出し get_value_from_targets(targets,"Name")',
           raw.get("succeed", False), raw.get("_code", "") or "", note_b)

    if not raw.get("succeed"):
        # (c) 単一文字列でも失敗する場合のみ、common.call_api を直接叩いて
        # 引数キーのバリエーションを切り分ける(通常はここまで到達しない想定)
        try:
            from cri.atomcraft import common as cri_common
            variants = [
                {"target_list": existing_cues, "field_name": "Name"},
                {"targets": existing_cues, "field_name": "Name"},
                {"target_list": existing_cues, "field_names": "Name"},
            ]
            for i, args in enumerate(variants):
                r = t.call(cri_common.call_api, "project", "get_value_from_targets", args, True,
                          idempotency=READ)
                record("cri.atomcraft.common", f"(c)call_api直接 variant{i}",
                       r.get("succeed", False), r.get("_code", "") or "",
                       "" if r.get("succeed") else r.get("message", ""))
                if r.get("succeed"):
                    break
        except Exception as e:  # pragma: no cover - 実機診断用のベストエフォート経路
            record("cri.atomcraft.common", "(c)call_api直接", False, "EXCEPTION", str(e))


def _set_value_to_targets_roundtrip(prop_fns, existing_cues):
    """set_value_to_targets の実機動作確認。既存Cueの無害なフィールド(Comment)を
    退避→書き換え→get_propertyで確認→元の値へ復元する。"""
    if not existing_cues:
        record("atomcraft_bulk_property", "set(Comment roundtrip)", False, "SKIPPED",
               "対象Cueが見つからず")
        return

    target = existing_cues[0]
    field = "Comment"
    probe_value = f"{LABEL_PREFIX}bulk_set_probe"

    backup_env = _get_property(prop_fns, target, field)
    original_value = None
    if backup_env.get("success"):
        original_value = (backup_env.get("data", {}).get("properties") or {}).get(field, "")
    record("atomcraft_get_property", "backup(Comment)", backup_env.get("success", False),
           backup_env.get("code", ""))

    set_env = envelope(prop_fns["atomcraft_bulk_property"](
        action="set", targets=[target], field_name=field, value=probe_value))
    record("atomcraft_bulk_property", "set(Comment=probe)", set_env.get("success", False),
           set_env.get("code", ""), "" if set_env.get("success") else set_env.get("error", ""))

    verify_env = _get_property(prop_fns, target, field)
    verified = False
    if verify_env.get("success"):
        got = (verify_env.get("data", {}).get("properties") or {}).get(field, "")
        verified = (got == probe_value)
    record("atomcraft_get_property", "verify(Comment==probe)", verified, verify_env.get("code", ""))

    if original_value is not None:
        restore_env = envelope(prop_fns["atomcraft_bulk_property"](
            action="set", targets=[target], field_name=field, value=original_value))
        record("atomcraft_bulk_property", "restore(Comment=original)",
               restore_env.get("success", False), restore_env.get("code", ""))


def _get_playback_state_positive(bp_fns, existing_cues):
    """既存Cueをplay→get_playback_state(再生中の状態を取得できるか)→stop_all。"""
    if not existing_cues:
        record("atomcraft_preview", "play->get_playback_state->stop_all", False, "SKIPPED",
               "対象Cueが見つからず")
        return

    cue = existing_cues[0]
    play_env = envelope(bp_fns["atomcraft_preview"](action="play", cue=cue))
    record("atomcraft_preview", "play", play_env.get("success", False), play_env.get("code", ""))

    state_env = envelope(bp_fns["atomcraft_preview"](action="get_playback_state", cue=cue))
    note = ""
    if state_env.get("success"):
        note = json.dumps(state_env.get("data"), ensure_ascii=False)[:120]
    record("atomcraft_preview", "get_playback_state(再生中)", state_env.get("success", False),
           state_env.get("code", ""), note)

    stop_env = envelope(bp_fns["atomcraft_preview"](action="stop_all"))
    record("atomcraft_preview", "stop_all", stop_env.get("success", False), stop_env.get("code", ""))


def _beatsync_full_cycle(object_fns, beatsync_fns, existing_cues):
    """Cueにcreate_track→そのtrackにcreate(time_ms=0,bpm=120)→両方削除。"""
    if not existing_cues:
        record("atomcraft_manage_beatsync", "create_track->create->delete", False, "SKIPPED",
               "対象Cueが見つからず")
        return

    cue = existing_cues[0]
    track_env = envelope(beatsync_fns["atomcraft_manage_beatsync"](
        action="create_track", parent=cue, label=f"{LABEL_PREFIX}beat_track"))
    note = "" if track_env.get("success") else track_env.get("error", "")
    record("atomcraft_manage_beatsync", "create_track(parent=Cue)", track_env.get("success", False),
           track_env.get("code", ""), note)

    track_uuid = track_env.get("data") if track_env.get("success") else None
    point_uuid = None
    if track_uuid:
        point_env = envelope(beatsync_fns["atomcraft_manage_beatsync"](
            action="create", parent=track_uuid, time_ms=0, bpm=120.0,
            label=f"{LABEL_PREFIX}beat_point"))
        note2 = "" if point_env.get("success") else point_env.get("error", "")
        record("atomcraft_manage_beatsync", "create(time_ms=0,bpm=120)",
               point_env.get("success", False), point_env.get("code", ""), note2)
        if point_env.get("success"):
            point_uuid = point_env.get("data")

    # cleanup: 子(beatsync point)から先に削除
    if point_uuid:
        env = envelope(object_fns["atomcraft_modify_object"](action="delete", target=point_uuid))
        record("atomcraft_modify_object", "delete(cleanup beatsync point)",
               env.get("success", False), env.get("code", ""))
    if track_uuid:
        env = envelope(object_fns["atomcraft_modify_object"](action="delete", target=track_uuid))
        record("atomcraft_modify_object", "delete(cleanup beatsync track)",
               env.get("success", False), env.get("code", ""))


def _project_io_save_verification(t):
    """%TEMP%配下に新規プロジェクトをcreate→save_allし、ファイルが実際に
    書かれたかを確認する。デモプロジェクト自体は保存しない(最後に実行する)。

    create_project / save_project_all はAtom Craft側のGUIモーダル(未保存の
    変更の確認ダイアログ等)で応答がブロックされる可能性があるため、ツール
    ラッパーを経由せず robot API 関数を直接、明示的なタイムアウト
    (PROJECT_IO_TIMEOUT_SEC)付きで呼ぶ。タイムアウトした場合は「諦めて次へ進む」
    (transport側でfull_resetされ、以降は未検証のまま記録する)。
    """
    tmp_root = tempfile.mkdtemp(prefix="mcp_smoke_atomcraft_")
    project_name = f"{LABEL_PREFIX}verify_project"
    p = t._robot.project

    create_result = t.call(p.create_project, tmp_root, project_name, True,
                           idempotency=NON_IDEMPOTENT, timeout=PROJECT_IO_TIMEOUT_SEC)
    note = "" if create_result.get("succeed") else create_result.get("message", "")
    record("cri.atomcraft.project", "create_project(temp project, timeout=60s)",
           create_result.get("succeed", False), create_result.get("_code", "") or "", note)

    if not create_result.get("succeed"):
        return

    save_result = t.call(p.save_project_all, idempotency=IDEMPOTENT_WRITE,
                         timeout=PROJECT_IO_TIMEOUT_SEC)
    note2 = "" if save_result.get("succeed") else save_result.get("message", "")
    record("cri.atomcraft.project", "save_project_all(timeout=60s)",
           save_result.get("succeed", False), save_result.get("_code", "") or "", note2)

    written = []
    for root_dir, _dirs, files in os.walk(tmp_root):
        for fname in files:
            written.append(os.path.relpath(os.path.join(root_dir, fname), tmp_root))
    record("atomcraft_project_io", "verify(files written to temp dir)",
           len(written) > 0, "", f"file_count={len(written)}")


def _run_checks(t: AtomCraftTransport, settings) -> bool:
    """一連のチェックを実行する。ping成功なら True、BLOCKEDなら False を返す。"""
    debug_fns = {f.__name__: f for f in debug_tools.make_tools(t)}
    tree_fns = {f.__name__: f for f in tree_tools.make_tools(t, settings)}
    object_fns = {f.__name__: f for f in object_tools.make_tools(t)}
    bp_fns = {f.__name__: f for f in build_preview_tools.make_tools(t)}
    beatsync_fns = {f.__name__: f for f in beatsync_tools.make_tools(t)}
    prop_fns = {f.__name__: f for f in properties_tools.make_tools(t)}

    # --- ping: 接続確認。失敗時はリトライ2回まで(合計3回)。それでも失敗ならBLOCKED ---
    ping_ok = False
    for attempt in range(1, PING_MAX_ATTEMPTS + 1):
        env = envelope(debug_fns["atomcraft_debug"](action="ping"))
        if env.get("success"):
            record("atomcraft_debug", "ping", True, note=f"attempt {attempt}/{PING_MAX_ATTEMPTS}")
            ping_ok = True
            break
        record("atomcraft_debug", "ping", False, env.get("code", ""),
               note=f"attempt {attempt}/{PING_MAX_ATTEMPTS}: {env.get('error', '')}")
        if attempt < PING_MAX_ATTEMPTS:
            time.sleep(PING_RETRY_DELAY_SEC)

    if not ping_ok:
        return False

    # --- 1. get_version ---
    env = envelope(debug_fns["atomcraft_debug"](action="get_version"))
    version_note = (json.dumps(env.get("data", {}).get("version", ""))
                    if env.get("success") else env.get("error", ""))
    record("atomcraft_debug", "get_version", env.get("success", False), env.get("code", ""), version_note)

    root_uuid, existing_cues, existing_track = _discover(t, object_fns, tree_fns, settings)

    # 接続断リスクの低い(=重要度が高い/安全な)項目から先に実行し、
    # 万一どこかで接続が失われても、より多くの検証結果を確保できるようにする。

    # --- 2a. bulk_property get: 現行ラッパー(リスト)での失敗を再確認(安全) ---
    _bulk_property_get_safe(prop_fns, existing_cues)

    # --- 3. get_playback_state 正常系(play→state→stop_all) ---
    _get_playback_state_positive(bp_fns, existing_cues)

    # --- 4. beatsync 完全系(create_track→create→両方削除) ---
    _beatsync_full_cycle(object_fns, beatsync_fns, existing_cues)

    # --- set_value_to_targets 往復確認(ドキュメント上は正しい単一文字列形式なので安全) ---
    _set_value_to_targets_roundtrip(prop_fns, existing_cues)

    # --- start_ingame_preview: 接続先なしの適当値でエラー封筒が返ることを確認 ---
    env = envelope(bp_fns["atomcraft_preview"](
        action="start_ingame_preview", target="dummy-target-uuid", ip_address="0.0.0.0"))
    note = "" if env.get("success") else env.get("error", "")
    record("atomcraft_preview", "start_ingame_preview", env.get("success", False), env.get("code", ""), note)
    if env.get("success"):
        stop_env = envelope(bp_fns["atomcraft_preview"](action="stop_ingame_preview"))
        record("atomcraft_preview", "stop_ingame_preview(cleanup)",
               stop_env.get("success", False), stop_env.get("code", ""))

    # --- 2b. bulk_property get: 接続断リスクのある実験(前回PARSE_ERROR発生)。
    #     ここまでの重要項目を済ませたあとに実行する ---
    _bulk_property_get_risky(t, existing_cues)

    # --- 5. project_io save検証(最後。デモプロジェクトが閉じる可能性あり) ---
    _project_io_save_verification(t)

    return True


def main() -> int:
    settings = config.load()
    try:
        api = robot.load(_SERVER_DIR)
    except RobotPathError as e:
        print(f"BLOCKED: robot-path解決に失敗しました: {e}")
        return 1

    t = AtomCraftTransport(api, settings)
    try:
        ok = _run_checks(t, settings)
    finally:
        # 接続を明示的に切断する(未切断のままプロセス終了すると、スクリプトサーバー側が
        # 旧クライアント接続を握ったままになり次回のping接続が失敗し続けることがあるため)
        t.finalize()

    print_table()
    print()

    if not ok:
        print(
            "BLOCKED: スクリプトサーバーへのping接続が"
            f"{PING_MAX_ATTEMPTS}回とも失敗しました。Atom Craft側でスクリプトサーバーが"
            "有効か、別のMCPサーバープロセスが同じポートを占有していないか確認してください。"
        )
        return 1

    print("注意: デモプロジェクトの保存API(save系)は呼んでいません。"
          "project_io検証は%TEMP%配下の新規プロジェクトに対してのみ行いました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
