"""atomcraft_mcp.tools: 各カテゴリのMCPツールをmake_tools(t)で公開するモジュール群。

paginated_ids / with_type_hint は objects.py で定義され、他のtoolsモジュールから
共有ヘルパーとして再利用される。
"""
from . import (
    objects, properties, materials, workunits, cues, audio_setup,
    build_preview, debug, tree, beatsync,
)
from .objects import paginated_ids, with_type_hint

__all__ = ["paginated_ids", "with_type_hint", "register_all"]


def register_all(mcp, t, settings) -> list:
    """全10モジュールのmake_toolsを呼び出し、生成された関数をmcpに登録する。

    tree.make_tools のみ settings も受け取る（output_dir解決・JSON文字数予算のため）。
    戻り値は登録した関数名のリスト（テスト・起動ログでの件数確認用）。
    """
    fns = []
    for mod in (objects, properties, materials, workunits, cues,
                audio_setup, build_preview, debug, beatsync):
        fns.extend(mod.make_tools(t))
    fns.extend(tree.make_tools(t, settings))
    for fn in fns:
        mcp.tool(fn)
    return [f.__name__ for f in fns]
