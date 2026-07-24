# CAPABILITIES.md — 機能マトリクスとできないこと

本ドキュメントは、本MCPサーバーが公開する21ツールについて「何ができるか」「どのくらい危険か」
「実機でどこまで確認できているか」を一覧化したものです。誇張はせず、未検証・未解決の項目は
正直に「未検証」「既知の問題」と書いています。実装の詳細な設計意図は `server/atomcraft_mcp/`
配下の各モジュールdocstringを、実機での確認手順・生ログの要旨は `verification-3.57.02.md`
を、バージョン別の機能差分は `VERSION-NOTES.md` を参照してください。

## 危険度の定義

各ツールの危険度は、実装が `transport.call()` に渡している `idempotency` 引数に基づきます。

| 区分 | 意味 |
|---|---|
| **読み取り** | 状態を変更しない照会系。失敗時は自動で1回だけ再試行される |
| **冪等書き込み** | 同じ入力を何度実行しても結果が変わらない書き込み(再接続、ログ送信、プロパティの一括設定、選択状態の変更、保存など)。再実行しても安全 |
| **非冪等作成** | 実行のたびに新規オブジェクトが作られたり、削除・移動など状態が不可逆に変化する操作。接続断などで結果不明になった場合は `UNKNOWN_OUTCOME` が返り、再実行前に対象の存在確認が必要 |
| **ビルド/保存** | キューシートビルドやプロジェクト全保存など、ディスク上の成果物(ACB・プロジェクトファイル)を生成・上書きする操作。他の非冪等操作より影響範囲が広い |

1つのツールが複数のactionを持ち、actionごとに危険度が異なる場合はセル内に併記しています。

## 機能マトリクス(21ツール)

| ツール名 | できること | 危険度 | 必要バージョン | 検証状態 |
|---|---|---|---|---|
| `atomcraft_debug` | ping/reconnect/status/log/warning/clear_log/get_version | ping・status・get_version=読み取り、reconnect・log・warning・clear_log=冪等書き込み | Ver.3.44.18(基本)。`get_version`が内部で使う`get_tool_version`自体はVer.3.46.04追加(それ未満は取得失敗として扱われるだけでエラーにはならない) | ping・get_versionは3.57.02実機で確認済み。他actionはユニットテストのみ |
| `atomcraft_get_object` | find_by_name/find_all_by_type/get_by_path/get_children/get_child_by_name/get_parent/get_selected/get_root/get_global_folder/get_workunit/get_cuesheet_rootfolder/get_material_rootfolder/get_project_material_rootfolder | 読み取り | Ver.3.44.18 | get_root・find_all_by_type(Cue/Track)は3.57.02実機で確認済み。他methodはユニットテストのみ |
| `atomcraft_create_object` | 汎用オブジェクト作成(CueSheet/Cue/Track/Bus/SelectorLabel/Category等) | 非冪等作成 | Ver.3.44.18 | ユニットテストのみ(実機未検証) |
| `atomcraft_modify_object` | copy/duplicate/move/delete/select | copy・duplicate・move・delete=非冪等作成、select=冪等書き込み | Ver.3.44.18。ただしcopyでAISAC/オートメーションのポイント・グラフをコピーする場合、Ver.3.47.00〜Ver.3.55.02(グラフはVer.3.54.02まで)の接続先では欠落する既知不具合がツール側にある(詳細はVERSION-NOTES.md) | deleteは3.57.02実機で確認済み(beatsync検証で作成したトラックの後片付けに使用)。他actionは未検証 |
| `atomcraft_get_property` | 単一/複数フィールドの取得、継承解決後の実効値取得(use_actual_value)、色情報の取得。無効フィールドは自動除外して部分成功を返す | 読み取り | Ver.3.44.18(use_actual_valueが呼ぶget_actual_valueはVer.3.45.00で追加) | 単一フィールド(Comment)の取得は3.57.02実機で確認済み(bulk_property set往復確認の退避・検証に使用)。use_actual_value等は未実機検証 |
| `atomcraft_set_property` | 複数フィールドの一括設定、色の設定/解除 | 冪等書き込み | Ver.3.44.18 | ユニットテストのみ(実機ではatomcraft_bulk_propertyのset経由でset_value_to_targetsを確認。本ツール自体のset_valuesは未実機検証) |
| `atomcraft_manage_category` | get(カテゴリ一覧取得)/set(完全置換)/add(複数キューへ追加) | get=読み取り、set=冪等書き込み、add=非冪等作成 | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_bulk_property` | set(複数対象へ同一値を一括設定)。**getはツール側で意図的に無効化**(呼ぶと接続を切断するため。下記「既知の未解決問題」節) | set=冪等書き込み、get=無効(ローカルで即エラー返却・サーバー未呼び出し) | 新API、根拠は確度「推定・極めて低い」のVer.3.42.0(関数存在チェックが実質的な防波堤。詳細はapi-versions.md) | **setは3.57.02実機でCommentフィールドの退避→設定→検証→復元の往復が成功**(問題なし)。getの無効化根拠は計3回の実機再現(詳細は下記) |
| `atomcraft_manage_material` | register(1件登録)/register_unregistered(未登録一括登録)/get_info/get_project_info/get_root_folder/get_project_root_folder | register系=非冪等作成、get系=読み取り | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_manage_workunit` | create/delete/get/save/exclude/include/get_cuesheet_rootfolder | create・delete=非冪等作成、get・get_cuesheet_rootfolder=読み取り、save・exclude・include=冪等書き込み | Ver.3.44.18(ワークユニットサブフォルダーへの作成はVer.3.55.10以降が前提) | ユニットテストのみ |
| `atomcraft_project_io` | create(新規プロジェクト)/open(開く)/save_all(全保存) | create=非冪等作成、open・save_all=**冪等書き込み(ビルド/保存に相当)** | Ver.3.44.18 | **create→save_allを3.57.02実機で確認済み**(単独の接続で実施)。%TEMP%配下の新規プロジェクトに対し、createが成功し、save_allでプロジェクトファイル一式(.atmcproject/.atmcglobal/バックアップフォルダ等、計15ファイル)が実際にディスクへ書き出されることを確認。検証用ディレクトリは確認後に削除済み。デモプロジェクト自体を保存するAPIは呼んでいない(create実行によりAtom Craft側の開いているプロジェクトが切り替わった可能性はある)。openは未実機検証 |
| `atomcraft_create_cue` | simple(マテリアルからキュー作成)/cuelink(既存キューへのリンク)/external_cuelink(外部キューリンク)/waveform_region(トラックへのウェーブフォームリージョン追加) | 非冪等作成 | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_manage_bookmark` | add/remove/list | add・remove=非冪等作成、list=読み取り | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_manage_busmap` | create_for_cue/get_for_cue/create_custom/get_custom/get_for_aisac | create系=非冪等作成、get系=読み取り | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_setup_aisac` | create/create_graph/add_point/create_link/get_graph | create系=非冪等作成、get_graph=読み取り | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_setup_automation` | create/add_point/get | create・add_point=非冪等作成、get=読み取り | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_setup_mixer` | create_mixer/add_bus_send/remove_bus_send/get_bus_effect/copy_bus_effect/move_bus/sync_snapshot | get_bus_effect=読み取り、他は非冪等作成 | Ver.3.44.18 | ユニットテストのみ |
| `atomcraft_build` | build(キューシートビルド)/clean_all(ビルドキャッシュ全クリーン) | **非冪等作成(ビルド/保存に相当)** | Ver.3.44.18。timeout_secで呼び出し単位のタイムアウトを上書き可能 | ユニットテストのみ。実機検証では未実行(実プロジェクトへの副作用を避けるため) |
| `atomcraft_preview` | play/stop_all/get_playback_state/start_ingame_preview/stop_ingame_preview | play・stop_all・start/stop_ingame_preview=冪等書き込み、get_playback_state=読み取り | play・stop_allはVer.3.44.18。get_playback_state/start_ingame_preview/stop_ingame_previewはVer.3.47.0以降が必要(start/stop_ingame_previewは変更履歴に関数名明記で確定、get_playback_stateは推定・安全側で同じ下限を採用) | 3.57.02実機で play→get_playback_state→stop_all を通しで確認済み: play・stop_allは成功。**get_playback_stateはplay直後の呼び出しでもNOT_FOUNDを返した**(短いSEで既に再生終了していた可能性が高いが、「再生中」状態を実際に観測できたわけではない点は留意)。start_ingame_preview(ダミー値でのAPI_ERROR異常系)も確認済み |
| `atomcraft_get_tree` | フォルダ階層を再帰走査し、全ノードのプロパティを一括取得。output_format=jsonは構造ツリーをそのまま返す、csvはCSV+構造JSONの2ファイル出力 | 読み取り(csv出力時はローカルディスクへのファイル書き込みを伴う) | Ver.3.44.18 | root=プロジェクトルート、child_types=["WorkUnit"]で3.57.02実機確認済み(該当0件だがAPI応答は正常)。csv出力モード・大規模ツリーでのJSON→CSV自動フォールバックは未実機検証 |
| `atomcraft_manage_beatsync` | create_track(ビート同期トラック作成)/create(ビート同期情報作成) | 非冪等作成 | 新API、根拠は確度「推定・低め」のVer.3.45.0(関数存在チェックが実質的な防波堤) | **create_track→create→delete(点・トラック)の完全なライフサイクルを3.57.02実機で確認済み**(親オブジェクトはCueである必要がある。親がTrackだとAPI_ERROR。作成物は同一接続内ですべて削除済み) |

補足: ユニットテストは `python -m pytest server/tests -q` で228件パス(2026-07-24時点)。
「ユニットテストのみ」の行はfake_robotによるモック検証であり、実際のAtom Craft
本体との通信は確認できていません。

## まだできないこと

### Robot APIが束ねていないモジュール

`server/atomcraft_mcp/robot.py` が読み込んでいるのは、CRIが提供するRobot Python
(`robot\remote\Python\cri\atomcraft\`)配下の `connectlib` / `project` / `build` /
`preview` / `debug` の5モジュールのみです。同ディレクトリには他に以下のモジュールが
あり、本MCPサーバーからは一切呼び出せません。

| モジュール | 内容 | 影響 |
|---|---|---|
| `profiler.py` | プロファイラーログの開始/停止、全ログのCSV書き出し | **パフォーマンス計測・プロファイリング機能がまるごと利用不可**。負荷計測が必要な場合はAtom Craft GUIのプロファイラーを手動操作する |
| `view.py` | ファイル選択ダイアログ表示、メッセージダイアログ表示 | GUIモーダルダイアログを要する操作のため、そもそも自動化に向かない(手動操作が前提) |
| `dsp.py` | バス関連操作の互換レイヤー。内部のほとんどの関数は`project`モジュールの同等関数に処理を委譲しているだけ(廃止予定の別名) | 実質的な機能ギャップではない(`atomcraft_setup_mixer`等で同等の操作が可能)。ただし`delete_dsp_bus`(バス削除)だけは`project`側にも対応するMCPツールのactionがなく、**バスの削除はMCP経由でできない** |
| `common.py` / `error.py` | 内部通信ヘルパーとエラーコード定義 | 機能ではなく内部実装。ユーザー向けの操作対象ではない |

### project モジュール内の未提供関数

`atomcraft_mcp` の各ツールが呼んでいない `project.py` の関数(=対応するactionが
どのツールにも存在しない)は以下の通りです。

- `create_language_settings` — 言語設定の作成
- `create_lipsync_file` — LipSyncファイルの作成
- `create_target_config` — ターゲットコンフィグの作成
- `create_selector_label` — セレクターラベルの作成
- `get_user_settings` / `get_usersettings` — ユーザー設定の取得
- `sync_local_files` — ローカルファイルの同期
- `delete_dsp_bus` — バスの削除(上記dsp.pyの節を参照)

これらが必要な場合はAtom Craft GUIで手動操作してください。

### タイムライン上の波形編集(トリミング・フェード)

CRI公式の変更履歴には「Ver.3.52.03でロボットがウェーブフォームリージョンの
トリミング・フェード操作に対応した」と記載がありますが、`project.py` に
`trim` / `fade` を名前に含む専用関数は見つかっていません。`atomcraft_set_property`
経由で特定のフィールド名を渡せば理論上到達できる可能性はありますが、有効な
フィールド名が `catalog.py` の `KNOWN_FIELDS` に未登録・未検証のため、
**本MCPサーバーでは現時点でサポート対象外**として扱っています。波形の分割・
トリミング・フェードイン/フェードアウトはAtom Craft GUIのタイムライン上で
手動操作してください。

### atomcraft_bulk_property の get(既知の未解決問題)

上の機能マトリクスに記載の通り、`action=get` は3.57.02実機で動作しません。
2026-07-24の実機検証で、CRIローカルマニュアル(`manual/jpn/contents/
criatom_tools_atomcraft_api_refmodule_project.html`)と公式Webリファレンスの
両方を確認したところ、ロボットAPI `get_value_from_targets(targets, field_name)`
の `field_name` は**単一の文字列**と定義されていることが判明しました(本ツールが
現在渡している `field_names` はリスト)。この情報をもとに以下2パターンを
実機で検証しましたが、いずれも成功しませんでした:

1. **リストを渡す(旧実装)**: `フィールド名が指定されていません` という
   API_ERRORで失敗します(フィールド数を1件/2件と変えても同一エラー)。
   仕様(単一文字列)に反する呼び方をサーバーが拒否しているだけで、接続には無害です。
2. **ドキュメント通り単一文字列を渡す**: `PARSE_ERROR`(応答の解析失敗)となり、
   直後から接続そのものが再接続不能(`SERVER_UNREACHABLE`)になり、スクリプト
   サーバー自体も停止します。2026-07-24のバッチ実験2回に加え、2026-07-25に
   **他の操作を一切挟まないクリーンな単独接続でも再現**(計3回)しており、
   偶発的な通信エラーや直前の実験の後遺症ではないと判断しています。

原因としては、公式リファレンスがこの関数の戻り値を「**オブジェクトをキーと
する連想配列**」と定義している点が疑わしく、このオブジェクトキーがリモート
プロトコルの応答直列化で壊れている可能性が高いとみています(ツール内ローカル
スクリプトでの動作可否は未検証)。

この状況を踏まえ、`server/atomcraft_mcp/tools/properties.py` では `action=get` を
**ツール側で意図的に無効化**しています(サーバーを呼ばずにローカルでエラー封筒を
返す)。「正しい」呼び方が接続とスクリプトサーバーを巻き添えにする以上、
呼ばせないことが最も安全なためです。一括取得が必要な場合は、
`atomcraft_get_property` を対象ごとに個別に呼んでください。
`atomcraft_bulk_property` の `action=set`(`set_value_to_targets`、単一文字列
引数)は既存Cueへの往復確認(退避→設定→検証→復元)込みで実機動作確認済みで、
問題ありません。将来のAtom Craftバージョンでリモート応答の問題が解消された
場合は、単一文字列引数での再有効化を検討してください。

## 将来課題: tool annotations

MCPプロトコルは各ツールに `readOnlyHint` / `destructiveHint` / `idempotentHint`
等のannotationsを付与する仕組みを提供していますが、本サーバーの `server/server.py`
での `mcp.tool()` 登録では現時点でannotationsを付けていません。上記マトリクスの
「危険度」列は実装内部の `idempotency` 引数(READ / IDEMPOTENT_WRITE /
NON_IDEMPOTENT)に基づく手作業の整理であり、MCPクライアント側から機械的に
参照できる形にはなっていません。クライアント側での安全性チェックを強化したい
場合、annotationsの付与は今後の課題です。
