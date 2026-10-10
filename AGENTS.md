# AGENTS.md — Codex CLI 用コンテキスト

本リポジトリは、CRI Atom Craftのサウンドオーサリング操作をLLMエージェントから
リモート実行するためのMCPサーバー(`server/`)と、その運用ドキュメント・スキル一式です。
サーバー本体は21個のMCPツールを公開し、Atom Craft付属のRobot Python APIを
薄くラップして呼び出します。詳細な機能一覧・運用知見・バージョン差分は
本ファイル末尾の「詳細ドキュメントへのポインタ」を参照してください。

## 21ツールのカテゴリ別要約

すべて `mcp__<サーバー登録名>__atomcraft_*` の形で呼ばれます(登録名はクライアント
設定に依存するため決め打ちしない)。各ツールの危険度(読み取り/冪等書き込み/
非冪等作成/ビルド・保存)とバージョン要件・実機検証状況の詳細は
`docs/dev/CAPABILITIES.md` の機能マトリクスを参照。

- **接続・診断**: `atomcraft_debug`
  ping/reconnect/status/log/warning/clear_log/get_version。作業開始前に
  `action='ping'` で疎通確認する。
- **読み取り・探索**: `atomcraft_get_object` / `atomcraft_get_property` /
  `atomcraft_get_tree` / `atomcraft_bulk_property`(action=get)
  名前からのUUID解決(`find_by_name`等)、単一/複数フィールドのプロパティ取得、
  フォルダ階層の一括取得。`atomcraft_bulk_property` の `action=get` は3.57.02実機で
  未解決のAPI_ERRORが確認されているため、個別取得(`atomcraft_get_property`)を
  優先する(詳細は `docs/dev/CAPABILITIES.md`)。
- **作成・編集(汎用オブジェクト)**: `atomcraft_create_object` /
  `atomcraft_modify_object` / `atomcraft_set_property` /
  `atomcraft_bulk_property`(action=set)
  copy/duplicate/move/delete/select、単一/複数フィールドの一括設定。
  作成・削除・移動は非冪等作成に分類され、`UNKNOWN_OUTCOME` の対象になりうる。
- **キュー・マテリアル・カテゴリ**: `atomcraft_create_cue` /
  `atomcraft_manage_material` / `atomcraft_manage_category`
  マテリアルからのキュー作成、波形マテリアルの登録、カテゴリの取得・置換・付与。
- **サウンド機能設定**: `atomcraft_setup_aisac` / `atomcraft_setup_automation` /
  `atomcraft_setup_mixer` / `atomcraft_manage_busmap` / `atomcraft_manage_beatsync`
  AISAC・オートメーション・ミキサー(バスセンド等)・バスマップ・ビート同期トラックの
  作成/設定。いずれも非冪等作成が中心。
- **プロジェクト管理**: `atomcraft_manage_workunit` / `atomcraft_project_io` /
  `atomcraft_manage_bookmark`
  ワークユニットの作成/削除/保存/除外/包含、プロジェクトの作成/オープン/全保存、
  ブックマークの追加/削除/一覧。
- **ビルド・プレビュー**: `atomcraft_build` / `atomcraft_preview`
  キューシートビルド・ビルドキャッシュクリーン、再生・停止・再生状態取得・
  インゲームプレビューの開始/停止。

## 接続前提

- Atom Craft本体を起動し、**スクリプトメニュー > サーバー > スクリプトサーバーを起動**
  した状態でないと、いずれのツールも接続できない(既定 `127.0.0.1:9000`)。
- **実機検証で確認済みの接続断の挙動**: 通常のクリーン切断後は再接続できる
  (毎回の手動再起動は不要)。ただしスクリプトサーバーが停止して新規接続を
  受け付けなくなることがある(異常切断・プロトコルエラーの後に起きやすい傾向は
  あるが、条件は完全には特定できていない)。つながらなくなったら、ユーザーに
  Atom Craft側で**スクリプトサーバーを手動で再起動**(スクリプトメニュー >
  サーバー > スクリプトサーバーを起動)を依頼すること。MCPサーバー側の
  `atomcraft_debug(action='reconnect')` はサーバー側状態のリセットのみで、
  Atom Craft側のリスナー停止には効かない。
- **作業は必ず直列で行うこと。** 理由は2つある。
  - スクリプトサーバーは同時に1つの接続しか受け付けない。実機(Ver.3.56.01 LE)で、
    MCPサーバーの接続中に別プロセスから接続すると拒否されることを確認している
    (Ver.3.57.02では未確認)。複数のセッション・エージェント(並列サブエージェント、
    Codexとの併用等)から同時に操作しないこと
  - 1つのセッション内でも、ツールを並列に呼ばないこと。サーバー側でDLL呼び出しを
    1つずつに直列化しているため壊れはしないが、並列に呼んでも速くはならず、
    書き込みの実行順が読めなくなる
  - 複数の作業単位(キャラクター/ユニット等)にまたがる大量呼び出しは、単位ごとに
    完全に完走させてから次へ進む。数十〜100回超のMCPコールが必要な作業は
    サブエージェントへの逐次委譲を検討する
- クライアント側のツール呼び出しタイムアウト設定にも注意。長時間かかる
  `atomcraft_build` 等を呼ぶ際は、クライアント側のタイムアウトも緩めないと
  Atom Craft側の処理継続中にクライアントが先に打ち切ることがある。

## エラー封筒の読み方

すべてのツールはJSON文字列を1つ返す。成功時は
`{"success": true, "data": ..., "message": ...}`、失敗時は
`{"success": false, "code": ..., "error": ..., "hint": ..., "retryable": ..., "details": ...}`
という統一フォーマット。

- **code**: `SERVER_UNREACHABLE` / `CONNECTION_LOST` / `TIMEOUT` / `INVALID_PARAMS` /
  `INVALID_FIELD` / `INVALID_TYPE` / `NOT_FOUND` / `ALREADY_EXISTS` / `PARSE_ERROR` /
  `UNKNOWN_OUTCOME` / `API_ERROR` / `UNSUPPORTED_VERSION` の12種類に分類される。
- **hint**: 次にどう動けばよいかの具体的な案内(有効フィールド一覧、代替の取得
  経路など)。エラーになったら必ず読む。
- **retryable**: `true` なら機械的に再実行してよい。`TIMEOUT` / `CONNECTION_LOST` /
  `PARSE_ERROR` は読み取り系であれば1回だけ自動リトライ済み。
- **UNKNOWN_OUTCOME**: 非冪等な書き込み操作(作成・削除等)の送信後に接続断・
  タイムアウトが起きた場合に返る。成功したか失敗したかサーバー側でも判別できて
  いないため、そのまま再実行せず、先に `atomcraft_get_object(method='find_by_name')`
  等で対象の存在を確認してから、存在すればそれを使い、存在しなければ再実行する。

## 詳細ドキュメントへのポインタ

- `docs/dev/HANDBOOK.md` — 接続の仕組み、エラー封筒、UUID解決、日本語パスの罠、
  大量呼び出しの委譲方針など、運用ハンドブック。
- `docs/dev/CAPABILITIES.md` — 21ツールの機能マトリクス(できること・危険度・
  必要バージョン・実機検証状況)、未対応の機能一覧。
- `docs/dev/VERSION-NOTES.md` — Atom Craftのバージョン別の概念差分・既知不具合。
- `docs/dev/CRI-DOC-MAP.md` — CRIWARE公式ドキュメント(game.criware.jp)横断検索の
  地図。ADX/Atom Craft/Sofdec/LipSync等の仕様・APIそのものを調べたいときはこちら
  (`.agents/skills/cri-doc-search/SKILL.md` から辿れる)。
- `docs/dev/SKILL-AUTHORING.md` — プロジェクト固有の定型作業をスキル化する際の
  ヒント(Claude Codeの`skills/`とCodexの`.agents/skills/`の両対応の書き方)。
