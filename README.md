# CRI Atom Craft MCP (非公式)

> **本プロジェクトは非公式です。** CRI・ミドルウェア株式会社による公式製品ではなく、同社とは無関係です。詳細は末尾の[免責事項](#免責事項)を参照してください。

CRI Atom Craft のサウンドオーサリング操作(キューシート作成・マテリアル登録・ミキサー設定・ビルド等)を、LLMエージェントからMCP(Model Context Protocol)経由でリモート操作できるようにするサーバーです。
Atom Craft付属のRobot Python APIを薄くラップし、21個のMCPツールとして公開します。
Claude Code・Codex CLIの両方に対応し、CRIWARE公式ドキュメント横断検索用のスキルも同梱しています。

## どちらから読むか

- 🎵 **サウンド制作の方** → [docs/guide/START.md](docs/guide/START.md) からどうぞ。このREADMEの残りは読まなくてOKです
- 🔧 **エンジニアの方** → このREADMEと `docs/dev/` 配下のドキュメントへどうぞ

## 対応クライアント

| クライアント | 導入方法 | 手順 |
|---|---|---|
| Claude Code | プラグインマーケットプレイス経由 | [docs/dev/clients/claude-code.md](docs/dev/clients/claude-code.md) |
| Codex CLI | `codex mcp add`(TOML手編集は代替手順) | [docs/dev/clients/codex.md](docs/dev/clients/codex.md) |

## 導入(Claude Code・最短2コマンド)

```
/plugin marketplace add nakamura-kigeki/atomcraft-mcp
/plugin install atomcraft-mcp@atomcraft-mcp-marketplace
```

インストール後は `/reload-plugins`(または Claude Code の再起動)→ `/mcp` で接続とツール数を確認してください。
robot-path(後述)が未設定のままだとMCPサーバープロセス自体が起動時に`RobotPathError`で終了し、
`/mcp` では `atomcraft` サーバーが failed / ツール0件と表示されます。読み方は
[docs/dev/clients/claude-code.md](docs/dev/clients/claude-code.md) を参照してください。

Codex CLIから使う場合は [docs/dev/clients/codex.md](docs/dev/clients/codex.md) を参照してください。

## 構成図

```
┌─────────────────┐        MCP (stdio)        ┌──────────────────────┐        TCP :9000        ┌────────────────┐
│ Claude Code /    │ ─────────────────────────▶ │ atomcraft-mcp server │ ────────────────────────▶ │ CRI Atom Craft  │
│ Codex CLI 等の    │ ◀───────────────────────── │ (server/server.py)   │ ◀──────────────────────── │ (スクリプト       │
│ MCPクライアント   │        21ツール応答         │  robot.py が Robot   │     Robot Python API      │  サーバー起動済み) │
└─────────────────┘                            │  Python APIをロード   │                            └────────────────┘
                                                └──────────────────────┘
```

MCPサーバーは起動時にAtom Craftへ接続しません(遅延接続)。ツール一覧の表示自体はAtom Craft未起動でも可能で、実際の操作を呼び出した時点で初めて `127.0.0.1:9000` への接続を試みます。

## ドキュメント一覧

### 🎵 サウンドの人向け(甘口・専門用語は初出で説明)

- [docs/guide/START.md](docs/guide/START.md) — これは何か・できることの例・導入の全体像
- [docs/guide/SETUP.md](docs/guide/SETUP.md) — やさしいセットアップ手順
- [docs/guide/USING.md](docs/guide/USING.md) — 使い方実例集・あるあるトラブルと対処
- [docs/guide/FAQ.md](docs/guide/FAQ.md) — つまずき集

### 🔧 エンジニア向け(辛口・技術的詳細をそのまま記載。すべて `docs/dev/` 配下)

- [docs/dev/SETUP.md](docs/dev/SETUP.md) — 共通セットアップ手順(Python導入・依存インストール・robot-path設定・疎通確認・つまずき集)
- [docs/dev/clients/claude-code.md](docs/dev/clients/claude-code.md) — Claude Code向け導入手順
- [docs/dev/clients/codex.md](docs/dev/clients/codex.md) — Codex CLI向け導入手順
- [docs/dev/HANDBOOK.md](docs/dev/HANDBOOK.md) — 運用ハンドブック(接続の仕組み・エラー封筒・UUID解決・大量呼び出しの委譲方針・制作運用の知見など)
- [docs/dev/CAPABILITIES.md](docs/dev/CAPABILITIES.md) — 21ツールの機能マトリクス(できること・危険度・必要バージョン・実機検証状況)
- [docs/dev/VERSION-NOTES.md](docs/dev/VERSION-NOTES.md) — Atom Craftのバージョン別の概念差分・既知不具合
- [docs/dev/CRI-DOC-MAP.md](docs/dev/CRI-DOC-MAP.md) — CRIWARE公式ドキュメント横断検索の地図(`skills/cri-doc-search` から辿れる)
- [docs/dev/SKILL-AUTHORING.md](docs/dev/SKILL-AUTHORING.md) — プロジェクト固有の定型作業をスキル化する際のヒント
- [docs/dev/api-versions.md](docs/dev/api-versions.md) — API採用値の根拠一覧
- [docs/dev/verification-3.57.02.md](docs/dev/verification-3.57.02.md) — 実機検証記録(Ver.3.57.02)
- [AGENTS.md](AGENTS.md) — Codex CLI向けのコンテキストサマリー

## 動作要件

- Windows(CRI Atom Craft自体がWindows専用のため)
- uv(推奨。必要なPythonと依存を自動管理)または Python 3.10/3.11 + pip(代替)。Atom Craft Ver.3.55.00以降のRobot PythonがPython 3.10/3.11のみに対応しているため。詳細は [docs/dev/VERSION-NOTES.md](docs/dev/VERSION-NOTES.md)、導入手順は [docs/dev/SETUP.md](docs/dev/SETUP.md)
- CRI Atom Craft本体、およびそのRobot Python API(`robot\remote\Python`)— いずれも各自のCRIライセンスで入手してください。本リポジトリには含まれません

## 免責事項

**本ツールは実験的な段階です。** CRIツールのバージョンや環境により不安定な挙動をすることがあります。また、プロジェクトの構造・名称等の情報がAI(クラウド)に送信されるため、機密情報の扱いは各組織のAI利用ポリシーに従ってください。

**本プロジェクトは非公式であり、CRI・ミドルウェア株式会社とは無関係です。** CRI社のコード・ドキュメントは一切含まれていません。CRI Atom Craft本体とそのRobot APIは、利用者ご自身のCRIライセンスに基づいて別途入手してください。本リポジトリが提供するのは、既に入手済みのRobot Python APIをMCP経由で呼び出す薄いラッパー(サーバー実装)のみです。

配布物の性質について、念のため明示します。

- 本リポジトリは**CRI社のランタイムライブラリ・DLL・実行ファイルを一切同梱・再配布していません**。利用者自身がライセンスに基づいてインストールした `robot\remote\Python` を、実行時に環境変数 `ATOMCRAFT_ROBOT_PATH` 経由で参照するだけの構成です
- 逆コンパイル・逆アセンブル等は行っていません。本リポジトリの知見は、**公開されている公式マニュアルの記載**と、**公式に提供されているRobot API(ロボット機能)を通常の方法で呼び出した際の応答**にのみ基づいています
- ドキュメント内の型名・フィールド名等の一覧は、CRI公式マニュアルを出典とし、本プロジェクトの利用に必要な範囲で選択・再構成したものです。原文の著作権はCRI・ミドルウェア株式会社に帰属します。完全な情報は各自のCRIツール同梱マニュアル・公式ドキュメントを参照してください

## 商標について

CRI Atom Craft、CRIWARE、CRI ADX、ADX2 は、CRI・ミドルウェア株式会社の商標または登録商標です。本リポジトリでは、対応する製品を示す目的でのみこれらの名称を使用しています。

## ライセンス

[MIT License](LICENSE)
