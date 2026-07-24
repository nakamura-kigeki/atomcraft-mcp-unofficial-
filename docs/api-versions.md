# Robot API 7関数の初出バージョン調査結果と MIN_VER 採用値

調査日: 2026-07-24

対象7関数:
- preview モジュール: `get_playback_state` / `start_ingame_preview` / `stop_ingame_preview`
- project モジュール: `create_beatsync` / `create_beatsync_track` / `get_value_from_targets` / `set_value_to_targets`

この文書は Task 4〜6 が最初から使う `MIN_VER` 定数の根拠を確定するためのもの。
仮値運用はしない。未確定の項目は「確度: 推定」と明記した上で、安全側（低め）の値を採用する。

## 出典

- CRI ADX Tools SDK 同梱の変更履歴ドキュメント2種（`docs/jpn/history_criadx2toolssdk_win_j.txt`、
  `docs/jpn/history_criadx2tools_win_j.txt`）。それぞれ全文読了済み。
- Robot Python ソース（`robot/remote/Python/cri/atomcraft/{preview,project}.py`）の
  Ver.3.41.01 と Ver.3.57.02 の2バージョンでの存在有無突き合わせ。
  中間バージョンのアーカイブは手元になく、bisectによる絞り込みはできなかった。

## 採用 MIN_VER 一覧

| 関数 | MIN_VER | 確度 | 根拠 |
|---|---|---|---|
| `start_ingame_preview` | (3, 47, 0) | **確定**（履歴に関数名明記） | 変更履歴の `[2022-05-10 CRI Atom Craft Ver.3.47.00]` の項目に、previewモジュールへインゲーム接続用の関数(start_ingame_preview / stop_ingame_preview)を追加した旨の記載がある。Ver.3.41.01のソースには両関数とも存在せず、Ver.3.57.02には存在し、矛盾しない。 |
| `stop_ingame_preview` | (3, 47, 0) | **確定**（履歴に関数名明記） | 同上。 |
| `get_playback_state` | (3, 47, 0) | 推定（低め） | 履歴全文検索でも関数名の明記なし。Ver.3.57.02の`preview.py`では `start_ingame_preview` / `stop_ingame_preview` の直後に定義されており追加順の並びと見られる弱い傍証はあるが、履歴本文の裏付けはない。誤ブロックを避けるため、確定済みの `start_ingame_preview` と同じ Ver.3.47.0 を暫定下限として採用する（実際の初出はこれ以降 Ver.3.57.02 以前の可能性がある）。 |
| `create_beatsync` | (3, 45, 0) | 推定（低め） | 履歴全文検索で関数名の明記なし。ビート同期GUI自体はRobot API導入(Ver.3.44.18, 2020-11-25)より前から存在し、Ver.3.50.00でビート同期トラックの複数設定対応などGUI拡張があるが、ロボット関数追加を明記した記述は見つからなかった。Ver.3.41.01には存在せずVer.3.57.02には存在することのみ確認済み。安全側として、確定済み下限(3.47.0)よりもさらに低い Ver.3.45.0 を暫定下限として採用し、実際のブロックは主に関数存在チェックに委ねる。 |
| `create_beatsync_track` | (3, 45, 0) | 推定（低め） | 同上。 |
| `get_value_from_targets` | (3, 42, 0) | 推定（極めて低い） | 履歴全文検索で関数名・対応するGUI機能名（「複数オブジェクトへの一括値設定」等）とも該当なし。既存の単一target版 `get_value` / `set_value` に対する複数target版のバッチ関数と考えられるが、導入時期は履歴から裏付けられなかった。Ver.3.41.01には存在せずVer.3.57.02には存在する。最も根拠が薄いため、7関数中もっとも低い Ver.3.42.0 を暫定下限として採用する。 |
| `set_value_to_targets` | (3, 42, 0) | 推定（極めて低い） | 同上。 |

## 方針: バージョンゲートは「確実な下限」＋「関数存在チェック」の二段構え

上表のとおり、7関数のうち確度が高いのは `start_ingame_preview` / `stop_ingame_preview` の2つのみで、
残り5つは初出バージョンを履歴文書から確定できなかった。

そのため本実装（`versioning.require_feature`）では、MIN_VERによるバージョン比較だけに頼らず、
以下の二段構えでゲートする:

1. **関数存在チェック（`hasattr`）** — 接続先のAtom Craft本体ではなく、robot-pathが指す
   Robot Python側に対象関数が実際に存在するかを確認する。旧いRobot Pythonを指している場合、
   関数が存在しなければバージョン番号によらず確実にブロックできる。これが実質的な防波堤になる。
2. **バージョン下限チェック** — `get_tool_version` で取得した接続先バージョンが MIN_VER 未満であれば
   ブロックする。ただし取得に失敗した場合はブロックしない（fail-open）。接続断など他の理由で
   取得に失敗した場合、実API呼び出し自体が同じエラー封筒を返すため、ここで二重にブロックする必要はない。

確度が「推定」の関数について MIN_VER を実際の初出バージョンより低めに設定しているのは、
バージョン比較単体で確実に機能を止められない代わりに、関数存在チェックの方を実質的な防波堤として
機能させるための意図的な安全側設計である。MIN_VERを高く見積もって新しいAtom Craftを誤ってブロック
するより、低めに見積もって関数存在チェックに委ねる方が実害が小さいと判断した。

## get_tool_version の戻り値形状

- `debug.get_tool_version` はCRI ADX Tools SDK Ver.3.46.04で追加された関数（変更履歴に記載あり）。
- 戻り値の形状（型・フィールド構成）についての記載は変更履歴文書中に一切ない。
- 実運用で確認されている形状は2種類:
  - 文字列: `data="3.41.01"`
  - 辞書: `data={"version": "Ver.3.57.02"}`
- 本実装の `normalize_version_data` はこの両形状を受け付ける。
