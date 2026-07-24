"""CRI robotライブラリ（cri.atomcraft）の解決と束ね。

CRIライブラリはバージョン依存パスにあり、サーバー本体とは別の場所に置かれるため、
以下の3段階でパスを解決する（上ほど優先）:

1. 環境変数 ATOMCRAFT_ROBOT_PATH
2. server.py と同じディレクトリの robot-path.txt（1行ポインタ）
3. %USERPROFILE%\\.atomcraft-mcp\\robot-path.txt（1行ポインタ）

Claude Code のプラグインはユーザーの plugin cache にコピーされて動くため、
リポジトリ同梱の robot-path.txt はインストール後には見えない。
そのため環境変数を第一の設定手段とする。
"""
import os
import sys
from dataclasses import dataclass


class RobotPathError(Exception):
    pass


@dataclass
class RobotAPI:
    connectlib: object
    project: object
    build: object
    preview: object
    debug: object


def _read_pointer_file(pointer: str) -> str:
    # utf-8-sig: メモ帳等でBOM付きUTF-8保存された場合でも、BOMを不可視文字として
    # パス先頭に残さないようにする(BOM無しファイルもそのまま読める)。
    with open(pointer, encoding="utf-8-sig") as f:
        return f.read().strip()


def resolve_robot_path(server_dir: str) -> str:
    """robot-path を3段階(env → server隣接ポインタ → ホームポインタ)で解決する。

    見つかったパスは存在確認まで行う。どの手段でも解決できない場合は、
    3つの設定手段すべてを案内する RobotPathError を送出する。
    """
    env_value = os.environ.get("ATOMCRAFT_ROBOT_PATH")
    if env_value:
        if not os.path.isdir(env_value):
            raise RobotPathError(
                f"環境変数 ATOMCRAFT_ROBOT_PATH の指す {env_value} が存在しません。"
                "CRIツールの robot\\remote\\Python のフルパスを設定し直してください。")
        return env_value

    local_pointer = os.path.join(server_dir, "robot-path.txt")
    if os.path.isfile(local_pointer):
        robot_path = _read_pointer_file(local_pointer)
        if not os.path.isdir(robot_path):
            raise RobotPathError(
                f"{local_pointer} の指す {robot_path} が存在しません。"
                "CRIツールのバージョンアップ後はこのファイルを更新してください。")
        return robot_path

    home_pointer = os.path.join(
        os.environ.get("USERPROFILE", ""), ".atomcraft-mcp", "robot-path.txt")
    if os.path.isfile(home_pointer):
        robot_path = _read_pointer_file(home_pointer)
        if not os.path.isdir(robot_path):
            raise RobotPathError(
                f"{home_pointer} の指す {robot_path} が存在しません。"
                "CRIツールのバージョンアップ後はこのファイルを更新してください。")
        return robot_path

    raise RobotPathError(
        "robot-path が解決できません。以下のいずれかで CRIツールの "
        r"robot\remote\Python のフルパスを設定してください: "
        f"(1) 環境変数 ATOMCRAFT_ROBOT_PATH  "
        f"(2) {local_pointer} に1行で記述  "
        f"(3) {home_pointer} に1行で記述")


def load(server_dir: str) -> RobotAPI:
    robot_path = resolve_robot_path(server_dir)

    # cri/atomcraft 配下のCRI提供モジュール(project.py等)は内部で
    # `import criatomcraft_api_lib` を非修飾（cri.atomcraft.を付けない形）で行っている。
    # そのため robot_path（Python直下）だけでなく cri/atomcraft ディレクトリ自体も
    # sys.path に加えないと、`from cri.atomcraft import project` の時点で
    # ModuleNotFoundError: No module named 'criatomcraft_api_lib' になる
    # （実機(Ver.3.57.02)で確認済みの既知の挙動）。
    atomcraft_dir = os.path.join(robot_path, "cri", "atomcraft")
    if not os.path.isdir(atomcraft_dir):
        raise RobotPathError(
            f"robot-path の指す {robot_path} の下に cri\\atomcraft がありません。"
            "robot-path が robot\\remote\\Python を正しく指しているか確認してください。")

    # 汎用名モジュール(build/debug/project等)を隠さないよう、sys.pathへの追加は
    # 先頭(insert(0))ではなく末尾(append)にする。cri/atomcraft ディレクトリには
    # build.py / debug.py / project.py のような極めて一般的な名前のモジュールが
    # 並んでおり、先頭に挿入すると同一プロセス内の他コードが
    # `import build`（PyPA公式パッケージ等）を行った際にCRI版が誤って解決される
    # 危険がある。末尾に追加すればstdlib/site-packagesが常に優先され、
    # 衝突は「そのモジュールが他に存在しない場合」だけに限定される。
    for p in (robot_path, atomcraft_dir):
        if p not in sys.path:
            sys.path.append(p)

    from cri.atomcraft import criatomcraft_api_lib as connectlib
    from cri.atomcraft import project, build, preview, debug
    return RobotAPI(connectlib=connectlib, project=project, build=build,
                    preview=preview, debug=debug)
