---
name: cri-doc-search
description: CRIWARE/ADX(Atom Craft)/Sofdec/LipSync等のCRI社SDKについて、仕様・API・エラーメッセージ・マニュアルの記述を調べたいときに使用する。「CRIのドキュメントを調べて」「Atom CraftのAPI仕様を確認して」「このエラーメッセージの意味は」「game.criware.jpで検索して」のような依頼で使う。
---

# cri-doc-search

CRIWARE公式ドキュメント(game.criware.jp)を横断検索するための薄いラッパーです。
本体の地図は `../../../docs/dev/CRI-DOC-MAP.md` にあります。**まずそちらを読んでから**
検索してください。

## 手順

1. `../../../docs/dev/CRI-DOC-MAP.md` を読み、対象の製品(ADX/Atom Craft/Sofdec/LipSync等)の
   入口URLとURLパターンを確認する。
2. 調べたい内容の性質(API名/エラーメッセージ/概念名/バージョン固有の挙動)に応じて、
   同ドキュメントの「検索クエリの型」節にある `site:game.criware.jp` クエリの型を
   選んで検索する。
3. 検索結果がヒットしない場合は、日本語版・英語版を切り替えて再検索する
   (同ドキュメントの「日本語/英語マニュアルの使い分け」節を参照)。
4. Web版でも見つからない、またはオフライン環境の場合は、同ドキュメントの
   「ローカル同梱ドキュメント」節の手順でCRIツールインストールフォルダ内の
   同梱マニュアルを確認する。
5. 見つかった情報がAtom Craft自動化API(Robot API)に関するものであれば、
   本MCPサーバーの `../../../docs/dev/CAPABILITIES.md` / `../../../docs/dev/HANDBOOK.md` と
   突き合わせ、本サーバーの対応状況(実装済みか・実機検証済みか)も併せて確認する。
