# Claude Code向け導入手順

共通の準備(Python導入・robot-path設定・Atom Craftのスクリプトサーバー起動)は
[../SETUP.md](../SETUP.md) を先に済ませてください。このページはClaude Code固有の
インストール・接続確認手順のみを扱います。

## 導入(2コマンド)

Claude Codeのプロンプトで以下を順に実行します。

```
/plugin marketplace add nakamura-kigeki/atomcraft-mcp
/plugin install atomcraft-mcp@atomcraft-mcp-marketplace
```

1行目でマーケットプレイス(このリポジトリ自体)を登録し、2行目でプラグイン
`atomcraft-mcp` をインストールします。プラグイン名とマーケットプレイス名は
`@` で連結して指定します(`.claude-plugin/marketplace.json` の最上位の
`name`(`atomcraft-mcp-marketplace`) / `plugins[].name` に対応)。

**CLIからの導入(AIエージェント・自動化向け)**: `/plugin` はチャットプロンプト専用の
組み込みコマンドですが、同等の操作は `claude` CLIのサブコマンドとしてターミナルから
実行できます。セットアップをAIエージェントに任せる場合や、スクリプトで自動化する場合は
こちらを使ってください(**AIエージェントはこの方式で導入できるため、リポジトリの
cloneや `claude mcp add` での手動登録・スキルの手動コピーに切り替える必要は
ありません**)。

```powershell
claude plugin marketplace add nakamura-kigeki/atomcraft-mcp
claude plugin install atomcraft-mcp@atomcraft-mcp-marketplace
# アンインストール・配布元削除
claude plugin uninstall atomcraft-mcp@atomcraft-mcp-marketplace
claude plugin marketplace remove atomcraft-mcp-marketplace
```

## 依存パッケージの自動管理(uv)

プラグイン既定の `.mcp.json` は `uv run --python 3.10 --with "fastmcp>=2.0.0,<4" ...` の形で
MCPサーバーを起動する設定になっています。**uvが導入されていれば、Python 3.10と依存パッケージ
(`fastmcp`)は初回起動時にuvが自動的に解決するため、pip installやvenvの構築は不要です。**

uvが未導入の場合は、以下のコマンドで導入してください。

```powershell
winget install --id=astral-sh.uv -e
```

導入後は、ターミナルとClaude Codeを一度閉じて開き直し、`uv` コマンドがPATH上で見つかる
状態にしてから、上記「導入(2コマンド)」でプラグインをインストールし、下記「インストール後の
反映」の手順で反映してください。

初回起動はuvによる環境構築(Python 3.10・依存パッケージの取得)を含むため約30秒程度かかり、
2回目以降は数秒に短縮されます。初回起動中は `/mcp` の表示が一時的に未接続に見えることが
ありますが、異常ではありません(詳細は [../SETUP.md](../SETUP.md) つまずき集を参照)。

**素のPython + pip方式(代替)を選ぶ場合**は [../SETUP.md](../SETUP.md) の「代替: 素の
Python+pip方式」を参照してください。ただしその場合、プラグイン既定の `.mcp.json` はuvを
呼び出す設定のままなので、そのままでは動きません。`claude mcp add` でpythonのフルパスを
直接指定する手動登録に切り替える必要があります(以降の接続確認・トラブルシュート手順は
uv方式=プラグイン既定の登録を前提にしています)。

## インストール後の反映

インストール直後はMCPサーバーがまだ読み込まれていないことがあります。以下のいずれかで
反映してください。

- `/reload-plugins` を実行する
- または Claude Code自体を再起動する

## 接続確認

```
/mcp
```

を実行し、`atomcraft` サーバーが一覧に表示され、接続状態と公開ツール数(21個)が
確認できることをチェックしてください。

## robot-path未設定時のエラーの読み方

**robot-pathの解決は、MCPサーバープロセスの起動時(モジュール読み込み時)に1回だけ行われます。**
`server/server.py` は起動直後に `robot.load()` を呼び出しており、`ATOMCRAFT_ROBOT_PATH` などの
robot-path設定([../SETUP.md](../SETUP.md) 手順2参照)が一つも見つからない場合、この時点で
`RobotPathError` が送出されてMCPサーバープロセスそのものが即終了します。つまり、robot-path
未設定は「ツールを呼び出したら失敗する」ではなく「**MCPサーバーが起動すらできない**」という
状態です(Atom Craft本体へのTCP接続が遅延接続なのとは別の話— robot-pathの解決自体はAtom Craft
未起動でも成功しうる、事前の準備段階です)。

この状態でClaude Codeから見えるのは次のような症状です。

1. `/mcp` を実行すると、`atomcraft` サーバーが **failed / 接続不可** の状態で表示され、
   公開ツール数が0件になっている(個々のツール呼び出しの失敗としては出てきません。
   そもそもツールが1つも登録されていないため、呼び出す対象自体が存在しません)
2. `/mcp` のエラー詳細表示、またはClaude CodeのMCP関連ログに、`RobotPathError` が起動時に
   出力した生のメッセージが残っています。このメッセージには、設定可能な3つの手段
   (環境変数 `ATOMCRAFT_ROBOT_PATH` / `server/server.py` 隣接の `robot-path.txt` /
   `%USERPROFILE%\.atomcraft-mcp\robot-path.txt`)が列挙されています
3. 上記いずれか1つを設定してから、Claude Codeを再起動する(または該当のMCPサーバー接続を
   再読み込みする)と、次回起動時にrobot-pathが解決され、21個のツールが登録された状態で
   `/mcp` に表示されるようになります

Claude Codeのプラグインはユーザーのplugin cacheにコピーされて動作するため、リポジトリ同梱の
`robot-path.txt` は使えません。**環境変数 `ATOMCRAFT_ROBOT_PATH` での設定を推奨します。**

Claude Codeでプラグイン経由のMCPサーバーに環境変数を渡したい場合は、プラグイン同梱の
`.mcp.json` が読む `env` に設定を追加するか、システム環境変数として `ATOMCRAFT_ROBOT_PATH` を
設定してからClaude Codeを起動してください。設定変更後は `/reload-plugins` または再起動で
反映させてください。

## pythonの実体解決が原因でMCPサーバーが起動失敗した場合の対処(素のPython方式(代替)を選んだ場合のみ関係)

この節は、uv方式(プラグイン既定)ではなく「素のPython + pip方式(代替)」を選び、`claude mcp add`
で `python` を手動登録した場合にのみ関係します。uv方式では `.mcp.json` が `uv` コマンド経由で
起動するため、この問題自体が発生しません。

素のPython方式で `claude mcp add` に裸の `python` というコマンド名を指定すると、PATH上で
最初に解決される `python` が想定と違うものだった場合、MCPサーバーがそもそも起動できません。

- PATH上の `python` が実際にどの実体を指しているかは、`python -c "import sys;
  print(sys.executable)"` で確認できます。表示されたパスが Python 3.10以上の実体であることを
  確認してください([../SETUP.md](../SETUP.md) の「代替: 素のPython+pip方式」内
  「Microsoft Store版Pythonのaliasの罠」も参照)。venvを使っている場合は、venvを有効化した
  状態でこのコマンドを実行してください
- plugin cache配下の `.mcp.json` を直接書き換えてpythonのフルパスを指定する応急処置も可能ですが、
  プラグイン更新のたびにplugin cacheが再配置され、直接編集した内容は消えます。**恒久対処にはならない
  ため非推奨**です。恒久的に解決したい場合は、PATH上で最初に解決される `python` の実体そのものを
  正しいバージョンに揃えるか(PATHの並び順を調整する、Microsoft Store版のaliasを無効化する等)、
  システム環境変数として正しい `python` を指すよう設定してください

## 参考: `/mcp` に出ない・エラーのまま変わらない場合

- **`atomcraft` が failed / 接続不可で、ツール数が0件のまま変わらない場合は、まずrobot-path
  未設定を疑ってください**(上記「robot-path未設定時のエラーの読み方」)。これが最も多い原因です
- 次に疑うべきは上記の「pythonの実体解決」問題です
- Atom Craft本体でスクリプトサーバーが起動しているか([../SETUP.md](../SETUP.md) 手順3)
- 一度接続が成立した後に再接続できない場合は、スクリプトサーバーが停止して
  新規接続を受け付けなくなる既知の挙動(異常切断・プロトコルエラーの後に
  起きやすいが条件は完全には特定できていない。[../SETUP.md](../SETUP.md)
  つまずき集、[../HANDBOOK.md](../HANDBOOK.md))を疑ってください。Atom Craft側で
  スクリプトサーバーを再起動すれば直ります
