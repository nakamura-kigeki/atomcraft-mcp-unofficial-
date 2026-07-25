# CRI-DOC-MAP.md — CRIWAREドキュメント横断検索の地図

CRIWARE(CRI ADX / Atom Craft / Sofdec / LipSync等)の仕様・API・エラーを調べる際の
足がかりです。本MCPサーバー自体の仕様は `CAPABILITIES.md` / `HANDBOOK.md` /
`VERSION-NOTES.md` を参照してください。ここで扱うのはCRI社の公式ドキュメント
(`game.criware.jp`)への効率のよいたどり着き方だけです。

URLは2026-07時点で到達確認したものです。サイト構造は将来変わりうるため、
リンク切れの場合は「検索クエリの型」節のクエリで引き直してください。

## 1. サイト構造マップ

### 入口

- **マニュアル一覧ページ**: https://game.criware.jp/learn/manual/
  製品ごとのマニュアルへのリンクがまとまっている。迷ったらここから辿るのが最も確実。
  日本語・English・中文の切り替えあり(**日本語版のほうが提供製品数が多い**)。

### URLパターン(パスセグメントの意味)

マニュアル本文は `https://game.criware.jp/manual/<製品セグメント>/<版>/<ページ名>.html`
という形式に概ね従う。

| セグメント | 意味 | 例 |
|---|---|---|
| `<製品セグメント>` | 製品・ドキュメント種別を表す(下表参照) | `adx2_tool` / `native/adx2` / `sofdec2` 等 |
| `<版>` | `latest`(最新版、通常はこれでよい) / `v3_44_00` のようなバージョン固定 / 稀に `jpn/contents` という旧形式 | `latest` |
| `_en` サフィックス | 製品セグメントに付くと英語版 | `adx2_tool_en` |

バージョン固定パス(`v3_44_00`等)は「そのバージョン時点の仕様を確認したい」場合に使う。

### 製品別の入口URL

| 製品/ドキュメント | パス(`https://game.criware.jp/manual/` 以下) |
|---|---|
| CRI Atom Craft(ツールマニュアル、GUI操作全般) | `adx2_tool/latest/criatom_tools_atomcraft_about.html`(英語版は `adx2_tool_en/...`) |
| Atom Craft ロボット(自動化API)概要 | `adx2_tool/latest/criatom_tools_atomcraft_api.html` |
| **ロボットAPIリファレンス目次** | `adx2_tool/latest/criatom_tools_atomcraft_api_reference.html` — 本MCPサーバーが呼んでいるRobot APIの一次情報はここ |
| **オブジェクトリファレンス(型名・バスエフェクト名・graph_typeの一次情報)** | `adx2_tool/latest/criatom_tools_atomcraft_api_refobject.html` — `object_type` に使える**全オブジェクト型名**に加え、**「バスエフェクトの種類と名前」**(21種)と**「AISACグラフ・オートメーション・再生パラメーター設定アクションの種類と名前」**(`graph_type` 43種)の節を含む。`catalog.py` の `OBJECT_TYPES` / `BUS_EFFECT_TYPES` / `GRAPH_TYPES` はこのページを出典とする(目次ページからは1階層奥にあり、後半2節はさらに見落としやすい) |
| **パラメーターリファレンス(フィールド名の一次情報)** | `adx2_tool/latest/criatom_tools_atomcraft_api_refparam.html`(Project/UserSettings)と、同名 + `_global` / `_workunittree` / `_aisac` / `_materialtree` の計5ページ。`get_property` / `set_property` で使うフィールド名が型ごとに列挙されている。`catalog.py` の `KNOWN_FIELDS` の出典。**見出しの `Action` / `Marker` / `InternalCueLink` は概念グルーピングであって型名ではない**点に注意 |
| モジュールリファレンス(関数の一次情報) | `adx2_tool/latest/criatom_tools_atomcraft_api_refmodule.html` から、`..._refmodule_{project,preview,build,debug,view,error,connect,profiler}.html` の8本に分かれる |
| CRI ADXネイティブSDK(ライブラリAPI・エラーコード) | `native/adx2/latest/` 配下。エラーは `criatom_trblsht_error.html` |
| CRI Sofdec(ムービー再生) | `native/sofdec2/latest/index.html` |
| CRI LipSync — Unity向け | `lipsync_v/latest/contents/about_lipsync.html` |
| CRI LipSync Tools(解析ツール) | `lipsync_tools/latest/contents/` 配下 |
| Unity Plugin(CRIWARE for Unity) | `unity_plugin/latest/contents/` 配下 |
| Unreal Engine Plugin | `ue_pluginv1/latest/contents/`(v1) / `ue_pluginv2/latest/`(v2) 配下 |

補足: 検索結果には `adx2_tool/jpn/contents/*.html` という旧形式パスも生きたページとして
出てくる。`latest` 側で見つからない場合のフォールバックとして扱う。

## 2. 検索クエリの型(用途別)

`site:game.criware.jp` を付けたWeb検索が最も効率が良い。目的別のクエリ例:

- **API名・関数名で引く**: `site:game.criware.jp <関数名>`(例: `site:game.criware.jp create_cue`)。
  ヒットしない場合は日本語の操作名(「キュー作成」等)でも試す。
- **エラーメッセージで引く**: `site:game.criware.jp "<エラー文言の一部>"`。
  日本語のエラー文言は引用符付き部分一致がヒットしやすい。エラーコード(数値・定数名)は引用符なしでよい。
- **概念・機能名で引く**(「AISAC」「バスセンド」「セレクター」等):
  `site:game.criware.jp <概念語> マニュアル` — 「マニュアル」を足すと仕様ページが優先されやすい。
- **バージョン固有の挙動を引く**: `site:game.criware.jp <機能名> Ver.3.5` のように
  バージョン番号を含めると変更履歴ページがヒットしやすい。
- **製品を跨いだ横断確認**: 製品セグメント名(`adx2_tool` / `sofdec2` / `lipsync_v` 等)を
  検索語に含めて絞り込む。

## 3. 日本語/英語マニュアルの使い分け

- **日本語版を既定にする**。英語版が用意されている製品は一部に限られる。
  英語で検索してヒットしない場合は、必ず日本語版でも再検索する。
- 日英はページ構成・ファイル名が同じことが多く、製品セグメントに `_en` を足すだけで
  英語版に到達できる場合がある(全ページにある保証はない)。

## 4. ローカル同梱ドキュメント(オフライン代替・**一覧の抽出はこちらを推奨**)

CRIツールのインストールフォルダには、Webサイトと同等のマニュアルが同梱されている。
オフライン環境ではこちらを使う。

- 一般形: `<CRIツールインストール先>\cri\tools\ADX2\ver.3\docs\jpn`(英語版は `docs` 直下の別フォルダ)。
  上記のリファレンス各ページのHTMLは `<同ツール>\manual\jpn\contents\` にある
- **型名・フィールド名などの一覧を漏れなく取り込みたい場合は、Web版をAIに要約させるのではなく
  このローカルHTMLを機械抽出すること**。Web要約は同一ページでも件数が揺れる(実測で
  「38件/31件/38件列挙して合計36件」といった不整合が出た)
- ローカル版はインストール済みバージョンの内容を反映している。接続中のAtom Craftの
  実バージョンに対応した仕様を確認したいときは、Web版の `latest` よりローカル版のほうが
  正確な場合がある。

## 5. 出典と権利関係

本ページで案内しているドキュメントの著作権は、いずれもCRI・ミドルウェア株式会社に
帰属します。本リポジトリはこれらの原文を再配布しておらず、参照先(URL・同梱パス)と
検索の手順のみを記載しています。ドキュメントから抽出した識別子の一覧
(`catalog.py` の型名・フィールド名等)についても、本サーバーのヒント生成に必要な範囲で
再構成したものであり、原文の転載ではありません。
