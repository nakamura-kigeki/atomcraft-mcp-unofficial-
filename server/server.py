"""CRI Atom Craft Robot API MCP Server"""
import atexit
import logging
import os

from fastmcp import FastMCP

from atomcraft_mcp import config, robot
from atomcraft_mcp.transport import AtomCraftTransport
from atomcraft_mcp.tools import register_all

logging.basicConfig(level=logging.INFO)

_HERE = os.path.dirname(os.path.abspath(__file__))

settings = config.load()
api = robot.load(_HERE)  # robot-path解決(env ATOMCRAFT_ROBOT_PATH→隣接txt→ホーム)。失敗時はRobotPathErrorの明確なメッセージで停止
transport = AtomCraftTransport(api, settings)
atexit.register(transport.finalize)

mcp = FastMCP(
    name="CRI Atom Craft Robot",
    instructions=(
        "CRI Atom Craft のサウンドオーサリングツールをリモート操作するMCPサーバーです。\n"
        "使用前に CRI Atom Craft を起動し、スクリプトメニュー > サーバー > スクリプトサーバーを起動 してください。\n"
        "オブジェクトはUUID文字列で識別されます。まず atomcraft_debug(action='ping') で接続確認してください。\n"
        "エラー時は code / hint / retryable を確認: retryable=true なら再実行可、"
        "UNKNOWN_OUTCOME は対象の存在確認後に再実行してください。\n"
        "型名・フィールド名・graph_type は推測で指定せず、エラーの hint に出る近似候補に"
        "従ってください(公式ドキュメントには不完全な箇所があり、実機の応答が正です)。"
    ),
)
register_all(mcp, transport, settings)

if __name__ == "__main__":
    mcp.run()
