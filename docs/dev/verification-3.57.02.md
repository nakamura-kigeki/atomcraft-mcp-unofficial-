# 実機検証: CRI Atom Craft Ver.3.57.02(デモプロジェクト)

Ver.3.57.02 での実機検証記録。`scripts/live_smoke.py` を使い、MCP を介さず
`atomcraft_mcp` のツール関数を直接呼び出して、主要機能(robot-path解決、
preview系アクション、beatsync、bulk_property等)が実機で動くかを確認した。

検証環境: CRI Atom Craft Ver.3.57.02、デモプロジェクト、スクリプトサーバー
127.0.0.1:9000。生ログ・実UUID・個人パスはこの文書に含めていない。

## 発見した不具合と修正(robot.load）

実機接続で初めて、`robot.load()` が `ModuleNotFoundError: No module named
'criatomcraft_api_lib'` で失敗することが判明した。CRI提供の `project.py` 等が
内部で `import criatomcraft_api_lib`(パッケージ修飾なし)を行っており、
`robot\remote\Python` 直下だけでなく `cri\atomcraft` ディレクトリ自体も
`sys.path` に加えないと解決できない。fake_robot を使う既存ユニットテストでは
再現しない類の不具合で、実機接続で初めて顕在化した。

`server/atomcraft_mcp/robot.py` の `load()` を修正し、`cri/atomcraft` ディレクトリも
`sys.path` に追加するようにした。この修正がないと**実機ではサーバーが一切起動できない**
状態だったため、実機検証で見つかった最重要の修正点。

## 実行結果(1回目・完走)

| ツール | アクション | 結果 | 備考 |
|---|---|---|---|
| atomcraft_debug | ping | success | 接続確立(スクリプトサーバー到達確認) |
| atomcraft_debug | get_version | success | tool_version = Ver.3.57.02 |
| atomcraft_get_object | get_root | success | プロジェクトルート取得 |
| atomcraft_get_tree | get_tree(root, child_types=[WorkUnit], depth=1) | success | WorkUnit 0件(デモプロジェクトの構成による。API自体は正常応答) |
| atomcraft_get_object | find_all_by_type(Cue) | success | 既存Cueあり |
| atomcraft_get_object | find_all_by_type(Track) | success | 既存Trackあり |
| atomcraft_preview | get_playback_state(既存Cue) | error: NOT_FOUND | 対象Cueが再生中でないための想定内エラー |
| atomcraft_manage_beatsync | create_track(parent=既存Track) | error: API_ERROR | 「対象オブジェクトがキューでない」旨のメッセージ。ビート同期トラックの親はTrackではなくCueを期待している可能性が高い、と当時は推測にとどまった(2回目で実測確認、後述) |
| atomcraft_bulk_property | get | error: API_ERROR | 詳細メッセージは未記録。原因切り分けは未了だった(2回目で実測確認、後述) |
| atomcraft_preview | start_ingame_preview(target/ip はダミー値) | error: API_ERROR | 意図通りエラー封筒として返り、例外や無応答は発生しなかった(検証目的どおり) |

上記は接続成功後、1回のプロセス実行内で連続して完走した結果。

## 実行結果(2回目・保留2件の再検証、完走)

スクリプトサーバーを手動で再起動した後、1回の接続・1回のスクリプト実行内で
保留2件(beatsync親候補、bulk_property原因切り分け)を再検証した。

| ツール | アクション | 結果 | 備考 |
|---|---|---|---|
| atomcraft_manage_beatsync | create_track(parent=既存**Cue**、label=mcp_smoke_プレフィックス) | **success** | 1回目の推測どおり、親はTrackではなくCueで成功。作成物は同一接続内で削除に成功(atomcraft_modify_object action=delete) |
| atomcraft_bulk_property | get(targets=既存Cue2件, field_names=["Name"]) | error: API_ERROR | メッセージ要旨:「フィールド名が指定されていません」 |
| atomcraft_bulk_property | get(targets=既存Cue2件, field_names=["Name","Volume"]) | error: API_ERROR | 同上のメッセージ要旨。フィールド数(1件/2件)を変えても同一エラーで、フィールドの個数・綴りが原因ではないことを確認 |

bulk_propertyの原因切り分け: ロボットAPI側の `get_value_from_targets(targets, field_names)` は
引数を `field_name`(単数キー)としてAtom Craft側に渡す実装になっている。フィールド数を
変えても同一メッセージで失敗したことから、実際に渡す値の形式(リスト)自体が
想定と異なっている可能性が高いという仮説を得た(単一文字列としての呼び出しは
今回の接続チャンス内では未検証。原因確定にはさらなる実機検証が必要)。

## 懸念(解消済み): 1回目実行後のスクリプトサーバー再接続不可

1回目の実行完了後、スクリプトサーバーへの再接続を試みたところ、2回にわたり
(各3回のping試行、計6回)すべて失敗した。OSのTCP接続状態を確認したところ、
ポート9000がLISTEN状態から消えていることも確認した。

- ライブスモークスクリプト終了時に明示的な切断(`transport.finalize()`)を
  追加した後の再実行でも症状は変わらず、自スクリプト側の後始末漏れが原因とは
  考えにくい
- Atom Craft側のスクリプトサーバーが1クライアントの接続を受けた後、
  クライアントが正常切断しない限り(または何らかの理由で)再listenしていない
  可能性がある
- 接続失敗時のリトライは3回までとし、それ以上は試行していない

Atom Craft側でスクリプトサーバーを手動で再起動したところ、2回目の接続は
初回pingから成功した。これにより「1接続を受けた後は明示切断してもスクリプト
サーバー側が再listenしない/要再起動」という運用上の制約がある可能性が高いことが
裏付けられた。接続断自体は例外・クラッシュを伴うものではなく、封筒(envelope)は
いずれも正常なJSON形式で返っており、transport層のエラー分類自体は機能している。

## プロジェクトへの影響

- プロジェクト保存API(`atomcraft_project_io` の save系)は2回の実行を通じて
  一度も呼んでいない
- 2回目の実行でbeatsync create_trackが成功したが、同一接続内で
  `atomcraft_modify_object(action=delete)` により削除済み
- そのため、Atom Craft側に未保存の変更が残っていたとしても、保存せず終了すれば
  破棄できる状態

## 実行結果(3回目・未検証項目の一括検証)

スクリプトサーバーを再度手動で再起動した後、1回の接続・1回のスクリプト実行に
残りの未検証項目(bulk_property原因調査の深掘り、get_playback_state正常系、
beatsync完全ライフサイクル、set_value_to_targets往復、project_io save)を
詰め込んで実行した。事前調査としてCRIローカルマニュアルと公式Webリファレンスを
確認し、`get_value_from_targets` / `set_value_to_targets` の `field_name` は
いずれも単一文字列であることを突き止めた(現行実装は `get` 側だけリストのまま
渡している)。

接続断リスクを考慮し、危険度の低い項目から先に実行する順序に組み替えた
(ping/get_version → 発見 → bulk_property安全実験(a) → get_playback_state正常系
→ beatsync完全系 → set_value_to_targets往復 → start_ingame_preview →
bulk_property危険実験(b)(c) → project_io save)。

| ツール | アクション | 結果 | 備考 |
|---|---|---|---|
| atomcraft_bulk_property | get(現行ラッパー、field_names=リスト) | error: API_ERROR | 「フィールド名が指定されていません」。3回目の実行でも同一エラーを再確認 |
| atomcraft_preview | play(既存Cue) | **success** | |
| atomcraft_preview | get_playback_state(直後) | error: NOT_FOUND | play成功直後の呼び出しでもNOT_FOUND。短いSEで既に再生終了していた可能性が高いが、「再生中」の状態そのものは観測できなかった |
| atomcraft_preview | stop_all | **success** | |
| atomcraft_manage_beatsync | create_track(parent=既存Cue) | **success** | |
| atomcraft_manage_beatsync | create(time_ms=0, bpm=120, parent=作成したトラック) | **success** | ビート同期点の作成もCueの子トラックに対して成功することを確認 |
| atomcraft_modify_object | delete(ビート同期点) | **success** | |
| atomcraft_modify_object | delete(ビート同期トラック) | **success** | 作成物はすべて同一接続内で削除済み |
| atomcraft_get_property | backup(既存CueのComment) | **success** | 復元用に元の値を退避 |
| atomcraft_bulk_property | set(Comment=probe値) | **success** | |
| atomcraft_get_property | verify(Comment==probe値) | **success** | 設定値が正しく反映されていることを確認 |
| atomcraft_bulk_property | restore(Comment=元の値) | **success** | 実験前の状態に復元済み |
| atomcraft_preview | start_ingame_preview(target/ipはダミー値) | error: API_ERROR | 引き続きエラー封筒として正常に返る |
| (robot API直接) | get_value_from_targets(targets, "Name")(単一文字列) | error: PARSE_ERROR | ドキュメント通りの単一文字列形式に直しても失敗。**この呼び出し直後から接続がSERVER_UNREACHABLEになり、以降のすべての呼び出しが失敗した**(2回連続で再現) |
| atomcraft_project_io | create(一時プロジェクト) | error: SERVER_UNREACHABLE | 直前のPARSE_ERRORで接続が失われたため未検証のまま終了 |

### bulk_property get の原因調査(結論: 未解決、意図的に現状維持)

CRIローカルマニュアル(`manual/jpn/contents/
criatom_tools_atomcraft_api_refmodule_project.html`)と公式Webリファレンス
(`game.criware.jp`)の両方で、`get_value_from_targets(targets, field_name)` の
`field_name` は単一文字列と明記されている。しかし実機では、(a) 現行のリスト渡し
はAPI_ERRORで安全に失敗する一方、(b) ドキュメント通り単一文字列に直すと
PARSE_ERRORとなり、その場で接続そのものが壊れることを2回の接続(それぞれ1回ずつ、
計2回)で再現した。すなわち「ドキュメント通りの正しい呼び方」が実際には
グレースフルな失敗より悪い結果(接続断)を招くため、`properties.py` の実装は
リスト渡しのまま意図的に維持することにした(詳細はコード内コメント・
CAPABILITIES.md参照)。原因がAtom Craft側のこの関数自体の不具合なのか、
他の引数形式(common.call_apiの生キー等)に解があるのかは、接続断により
切り分けが完了しておらず未解決。

### project_io save検証: 4回目(単独接続)で成功

1〜3回目の接続では、直前に実行したbulk_property危険実験(単一文字列形式の
get_value_from_targets)による接続断が原因で `atomcraft_project_io` のsave系
検証に到達できなかった。4回目は他の実験を挟まず、project_io検証のみを
単独で実行した。

- `create_project`(%TEMP%配下の一時ディレクトリ、`mcp_smoke_` プレフィックス付き
  プロジェクト名、overwrite=True)→ **success**
- `save_project_all` → **success**
- 保存先ディレクトリを実際に走査し、プロジェクトファイル(.atmcproject)・
  グローバル設定(.atmcglobal)・ユーザー設定・バックアップフォルダ一式・
  プリセット・セッション・タグ・ワークユニット関連など、計15ファイルが
  実際にディスクへ書き出されていることを確認した(ファイル名にはPC名・
  ユーザー名が自動的に含まれる仕様のため、本書には具体的なファイル名は
  記載しない)
- 確認後、検証用ディレクトリは削除済み
- デモプロジェクトそのものを保存するAPIは呼んでいない。ただし `create_project`
  の実行によりAtom Craft側で開いているプロジェクトが切り替わった可能性がある
- この実行の前後で接続は生きたままだった(project_io系のcreate/save_all自体は
  接続を壊さない)ことも確認できた

### 接続の回復力に関する追加の観察(未確定)

3回目の実行は、実際には同一のスクリプトサーバー起動中に**2回のプロセス実行**を
行っている。1回目のプロセス実行(旧い項目順)でも同じPARSE_ERROR経由の接続断が
発生したが、その後(体感で数分程度の間隔を空けて)確認したところ接続が復旧しており、
2回目のプロセス実行(項目順を安全な順に組み替えたもの)は最初から接続に成功した。
これは、1・2回目の検証時に観察した「手動再起動が必要」という理解と矛盾するように
見える。検証中に気づかないうちに再度手動再起動していた可能性と、一定時間の
クールダウンで自動的に再listenする可能性の両方が考えられ、今回の観察だけでは
切り分けられない。運用上は「再接続に失敗したら、スクリプトサーバーの再起動を
試す」を第一の対処として案内しつつ、この自動回復の可能性も付記しておく。

なお4回目(project_io単独検証)の接続も、明示的に再起動せずに生きている
状態から開始できており、この観察と整合する。また4回目の実行中は接続が最後まで
落ちなかった(project_io系のcreate/save_all自体は接続を壊さない)ことも
合わせて確認できた。

## ユニットテスト

`python -m pytest server/tests -q` → **228 passed**(本検証を実施した2026-07-24時点)

## 追記(2026-07-25): 「スクリプトサーバーは1接続限り」という解釈の訂正

上記の1・2回目の検証(「懸念(解消済み): 1回目実行後のスクリプトサーバー
再接続不可」の節)をもとに、これまでのドキュメントでは「スクリプトサーバーは
1接続限りで、1回の接続が終わると手動再起動なしには再接続できない」という
仕様として説明していた。しかし、根拠が十分か再確認するために切り分け実験を
追加で実施した結果、この解釈は不正確だったことが判明した。

追加実験(2026-07-25、Ver.3.57.02)で確認した内容:

- クリーン切断(disconnect+finalize)であれば、サーバーは再listenし、**連続2回の
  接続→ping→切断がすべて成功**した。手動再起動は不要だった
- 接続保持中(ESTABLISHED)の間も、サーバー側のLISTENは**継続していた**
  (netstatで LISTENING と ESTABLISHED が同時に存在することを確認)

一方で、過去の検証(本文書の1・2回目)でLISTENが消えて接続不能になった現象は
複数回実在しており、これ自体は否定されない。発生タイミングを振り返ると
「不正な引数の実験でPARSE_ERROR→接続断が起きた直後」「スクリプトのクラッシュ・
強制終了などの異常切断後」に集中しており、異常系の後にリスナーが止まることが
ある、という理解が実測と整合する。

**ただし、実運用者からは「(異常系がなくても)確かに勝手に停止することもある」
という証言もあり、「異常切断・プロトコルエラーの後にだけ起きる」と因果関係を
断定できるほどの根拠はない。** 現時点で言えるのは次の2点にとどまる。

1. 通常のクリーン切断後は再接続できる(毎回の手動再起動は不要)
2. スクリプトサーバーが停止して新規接続を受け付けなくなることがある
   (異常切断・プロトコルエラーの後に起きやすい傾向はあるが、それが唯一の
   条件かどうかは特定できていない)

この訂正を受け、`HANDBOOK.md` / `AGENTS.md` / `SETUP.md` /
`../guide/FAQ.md` 等の「1接続限り」「再listenしない」という断定的な記述を、
上記の2点に基づく記述に修正した。並列接続の可否(同時2接続が可能かどうか)は
今回も検証しておらず、引き続き未検証のまま逐次実行を推奨している。

## 実行結果(4回目・bulk_property get のクリーン単独再現、2026-07-25)

「単一文字列渡しでの接続断は、直前の異常系実験の後遺症だった可能性はないか」という
疑義を晴らすため、他の操作を一切挟まないクリーンな接続で単独再現を行った。

手順: 新規接続 → find_objects(Cue) → `get_value_from_targets(cues, "Name")`
(公式リファレンスどおりの単一文字列)を1回だけ実行。

結果: `Failed to parse response`(PARSE_ERROR)が返り、直後のpingは
SERVER_UNREACHABLE、スクリプトサーバーのLISTENも消失(要手動再起動)。
バッチ実験2回+本再現1回の計3回、同一の失敗モードを確認した。

この結果を受け、`atomcraft_bulk_property` の `action=get` はツール側で
意図的に無効化した(サーバーを呼ばずローカルでエラー封筒を返す)。
根拠と将来の再有効化条件は `CAPABILITIES.md` の該当節を参照。
