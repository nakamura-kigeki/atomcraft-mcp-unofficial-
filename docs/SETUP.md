# SETUP.md — 共通セットアップ手順

Claude Code・Codex CLIのどちらから使う場合でも共通の準備です。クライアント固有の手順は
[docs/clients/claude-code.md](clients/claude-code.md) / [docs/clients/codex.md](clients/codex.md) を参照してください。

## 前提

- Windows
- CRI Atom Craft本体(利用者ご自身のCRIライセンスで別途入手)
- uv(推奨。必要なPythonと依存パッケージを自動管理) または Python 3.10/3.11 + pip(代替)

## 手順

### 1. uvの導入(推奨・プラグイン既定)

プラグイン既定の `.mcp.json` は、以下の形でMCPサーバーを起動する設定になっています。

```
uv run --python 3.10 --with "fastmcp>=2.0.0,<4" server/server.py
```

**uvさえ導入されていれば、Python 3.10と依存パッケージ(`fastmcp`)は初回起動時にuvが自動的に
解決するため、pip installやvenvの構築・Pythonの実体確認は不要です。**

```
winget install --id=astral-sh.uv -e
```

導入後は、ターミナルおよびMCPクライアント(Claude Code / Codex CLI)を一度再起動し、
新しく入った `uv` コマンドがPATH上で見つかる状態にしてください。

**CRI公式マニュアルの「実行環境の準備」との関係**: Atom Craft公式マニュアルの
ロボット導入手順(実行環境の準備)には「Python3をインストールし、PYTHONPATHに
`robot\remote\Python` を追加する」とありますが、**本MCPサーバー経由で使う場合は
どちらも不要です**(Pythonはuvが用意し、パス解決は `ATOMCRAFT_ROBOT_PATH` が
PYTHONPATHの代わりを果たします)。同マニュアルの「ローカル実行のための環境設定」
(スクリプト設定のプラグイン選択等)もリモート実行しか使わない本サーバーでは不要です。
むしろ公式手順で設定した**グローバルなPYTHONPATHが残っていると、uvが起動する
Pythonと衝突して起動失敗の原因になり得る**ため、プラグイン既定の設定では
MCPサーバープロセス内でPYTHONPATH/PYTHONHOMEを無効化しています(ローカル実行や
他ツールでPYTHONPATHを使っている場合でも、システム設定を消す必要はありません)。

**実測値**: 初回起動(Python 3.10の取得・依存パッケージのダウンロードを含む環境構築)は
約30秒。2回目以降はuvのキャッシュが効くため数秒で起動します。初回起動中はクライアント側の
表示が一時的に未接続 / failedのように見えることがありますが、故障ではありません(詳細は
「つまずき集」参照)。

**なぜ `--python 3.10` を明示指定しているか**: uvの既定Pythonは3.14系ですが、CRIが提供する
Robot Python APIはこれに対応しておらず(Atom Craft Ver.3.55.00以降のRobot PythonはPython
3.10/3.11のみ対応。詳細は [VERSION-NOTES.md](VERSION-NOTES.md))、`.mcp.json` 側で
`--python 3.10` を固定しています。この固定構成での実機接続(`atomcraft_debug` の
`connect` / `ping` / `get_version`)は動作確認済みです。

また `.mcp.json` の `env` では `PYTHONPATH` / `PYTHONHOME` を空文字に設定しています。これは
システム側に別のPython関連の環境変数が残っていた場合に、uvが解決するPython実行環境へ
意図せず混入する(環境汚染)のを防ぐためです。

### 代替: 素のPython+pip方式

uvを使わず、Pythonとpipを自分で管理する方式です。この方式を選んだ場合、**プラグイン既定の
`.mcp.json` は `uv` を呼び出す設定のままなので、そのままでは動きません。** `claude mcp add` /
`codex mcp add` で、実際に依存パッケージを入れたPythonのフルパスを直接指定する手動登録に
切り替える必要があります(詳細は [clients/claude-code.md](clients/claude-code.md) /
[clients/codex.md](clients/codex.md) の代替手順を参照)。

#### Pythonの導入・確認

`python` コマンドがPATH上にあることを確認してください。

```
python --version
```

3.10または3.11であることを確認します(Atom Craft Ver.3.55.00以降のRobot PythonがPython
3.10/3.11のみに対応しているため。詳細は [VERSION-NOTES.md](VERSION-NOTES.md))。

**venvを使う場合の注意点**: `pip install` した Python と、MCPクライアントが実際に起動する
`python` コマンドの実体が食い違っていると、依存パッケージ(`fastmcp`)が見つからずMCPサーバーが
起動しません。以下のコマンドで、今使っている `python` の実体パスを確認する習慣をつけてください。

```
python -c "import sys; print(sys.executable)"
```

venvを有効化した状態でこのコマンドを実行し、表示されたパスが `pip install` 先と一致しているか、
そして手動登録に書く `python` コマンド(またはそのフルパス)が同じ実体を指しているかを確認して
ください。venvを使わずシステムのPythonに直接インストールする場合は、この食い違いは起きません。

**Microsoft Store版Pythonのaliasの罠**: Windows環境では `python` と入力すると、実際には
Python本体ではなく `WindowsApps\python.exe` という、Microsoft Storeを開くためのエイリアスが
実行されてしまうことがあります(実体のPythonが別途インストールされていても、PATHの並び順次第で
このaliasが先に解決されることがあります)。これが起きていると `pip install` や `python
server/server.py` の実行が期待通りに動きません。`where python`(PowerShellなら `Get-Command
python`)で複数の候補が出てくる場合、上から順に解決されることに注意し、`python -c "import sys;
print(sys.executable)"` で実際に使われている実体を必ず確認してください。想定外の実体が
解決されている場合は、手動登録(`claude mcp add` やCodexの `codex mcp add`)でPythonのフルパスを
直接指定することを検討してください。

#### 依存パッケージのインストール

依存は `fastmcp` の1個だけです。Claude Codeのプラグインマーケットプレイス経由で導入した
場合はリポジトリをcloneしていないため `server/requirements.txt` 自体が手元にありません。
そのため、次のコマンドを主手順として直接実行してください。

```
pip install "fastmcp>=2.0.0,<4"
```

**別解(リポジトリをclone済みの場合)**: `server/requirements.txt` にも同じ範囲指定が
書かれているため、以下でも同じ結果になります。

```
pip install -r server/requirements.txt
```

CRI提供のRobot Python API(`cri.atomcraft` 配下のモジュール)はpip配布ではなく、Atom Craftの
インストール物に含まれるファイルを直接参照する方式のため、別途pipインストールする必要は
ありません(次項のrobot-path設定で参照先を指定します)。

### 2. ATOMCRAFT_ROBOT_PATH の設定(推奨)

サーバーは、CRIが提供するRobot Python API(`robot\remote\Python`)の場所を実行時に解決する
必要があります。解決順は次の3段階です(上ほど優先)。

1. 環境変数 `ATOMCRAFT_ROBOT_PATH`
2. `server/server.py` と同じディレクトリの `robot-path.txt`(1行に絶対パスを記述)
3. `%USERPROFILE%\.atomcraft-mcp\robot-path.txt`(1行に絶対パスを記述)

**推奨は環境変数 `ATOMCRAFT_ROBOT_PATH` です。** Claude Codeのプラグインはユーザーのplugin
cacheにコピーされて動くため、リポジトリ同梱の `robot-path.txt` はインストール後には参照できません。
また、環境変数はクライアント設定(`.mcp.json` や `codex mcp add --env`)から明示的に渡せるため、
「どのバージョンのAtom Craftに接続しているか」がクライアント設定を見るだけで分かるという利点も
あります(**バージョン一致の原則**: MCPサーバーが読み込むRobot Python APIのバージョンと、実際に
起動しているAtom Craft本体のバージョンは一致させてください。ズレていると、新しいツールが
`UNSUPPORTED_VERSION` で弾かれたり、逆に古い挙動に依存した処理が想定外の結果を返したりします)。

値には、CRIツールのインストール先の `robot\remote\Python` までのフルパスを指定します。例:

```
C:\path\to\cri_adx_tools_ver_X_XX_XX\cri\tools\ADX2\ver.3\robot\remote\Python
```

Atom Craft本体をバージョンアップした場合は、このパスを新しいバージョンのものに差し替えるだけで
接続先が切り替わります(MCPサーバー自体の再インストールは不要)。

**注意**: robot-pathには、CRIツール配布物に含まれる `robot\remote\Python` ディレクトリのみを
指定してください。このディレクトリ配下のPythonコードはMCPサーバープロセス上でそのまま
importされて実行されるため、出所の分からないパスや信頼できないパスを指定しないでください。

環境変数を使わない場合は、`%USERPROFILE%\.atomcraft-mcp\robot-path.txt` に同じ内容を1行で
書いてください(フォーマットは `server/robot-path.txt.example` を参照)。

**robot-pathの解決は、MCPサーバープロセスの起動時(モジュール読み込み時)に1回だけ行われます。**
`server/server.py` は起動直後に robot-pathの解決を行っており、3段階のいずれでも解決できない
場合はその場でMCPサーバープロセスが終了します。つまり、robot-path未設定は「個々のツール呼び出しが
失敗する」のではなく「**MCPサーバーがそもそも起動できず、クライアント側にはツールが1つも
見えない**」という形で現れます(次項で述べるAtom Craft本体へのTCP接続の遅延接続とは別の話です。
robot-pathの解決自体はAtom Craft未起動でも成功します)。クライアントごとの実際の見え方・
エラーメッセージの確認場所は [clients/claude-code.md](clients/claude-code.md) /
[clients/codex.md](clients/codex.md) を参照してください。

### 3. Atom Craftのスクリプトサーバーを起動

CRI Atom Craft本体を起動し、**スクリプトメニュー > サーバー > スクリプトサーバーを起動** を
実行してください。既定のリッスン先は `127.0.0.1:9000` です(`ATOMCRAFT_HOST` /
`ATOMCRAFT_PORT` で変更可能。詳細はクライアント別ドキュメント参照)。

MCPサーバー自体は起動時にAtom Craftへ接続しません(遅延接続)。ツール一覧の表示はAtom Craft未起動でも
可能ですが、実際にツールを呼び出した時点で接続を試み、スクリプトサーバーが起動していなければ
`SERVER_UNREACHABLE` エラーになります。

### 4. 疎通確認

MCPクライアント経由で `atomcraft_debug` ツールを `action='ping'` で呼び出し、応答が
`{"success": true, ...}` になることを確認してください。これがすべての作業の起点になります。

## つまずき集

| 症状 | 原因 | 対処 |
|---|---|---|
| `uv` が見つからない・コマンドとして認識されない | uvがインストールされていない、またはインストール直後でPATHの再読み込みが済んでいない | `winget install --id=astral-sh.uv -e` を実行後、ターミナルとMCPクライアントを再起動する。`uv --version` で実体を確認する |
| 初回起動が遅く、クライアント側でMCPサーバーが未接続/failedのように見える | uv方式では初回起動時にPython 3.10と依存パッケージ(`fastmcp`)をuvが自動解決・ダウンロードするため、実測で約30秒程度かかることがある(2回目以降はキャッシュが効き数秒) | すぐに失敗と判断せず、しばらく待ってから `/mcp` 等で再確認する。2回目以降は数秒で起動することも合わせて確認するとよい |
| `SERVER_UNREACHABLE` | ポート9000にAtom Craftが応答していない | Atom Craft側でスクリプトサーバーが起動しているか確認。`ATOMCRAFT_HOST`/`ATOMCRAFT_PORT` をクライアント設定側で変えている場合は、Atom Craft側の待受設定と一致しているか確認 |
| 一度接続できたのに、その後接続できなくなる | 通常のクリーン切断後は再接続でき、毎回の手動再起動は不要。ただしスクリプトサーバーが停止して新規接続を受け付けなくなることがある(異常切断・プロトコルエラーの後に起きやすい傾向はあるが、条件は完全には特定できていない) | Atom Craft側で**スクリプトメニュー > サーバー > スクリプトサーバーを起動** を再実行(手動再起動)する。MCPサーバー側の `atomcraft_debug(action='reconnect')` はサーバー側状態のリセットのみで、Atom Craft側の停止には効かない |
| MCPサーバーが起動しない・クライアント側でツールが1つも見えない(接続不可/failed表示) | `ATOMCRAFT_ROBOT_PATH` 未設定、かつ `robot-path.txt` もどちらの場所にもなく、robot-path解決がMCPサーバー起動時点で失敗している | クライアントのエラー表示・ログに残る `RobotPathError` のメッセージに、設定可能な3つの手段(環境変数/server隣接ポインタ/ホームポインタ)が列挙されるので、いずれかを設定してクライアントを再起動する。パスは `robot\remote\Python` までの絶対パスで、末尾に余計なサブディレクトリを含めない。見え方の詳細は [clients/claude-code.md](clients/claude-code.md) / [clients/codex.md](clients/codex.md) 参照 |
| `cri\atomcraft` が robot-path の下に見つからない旨のエラー | `ATOMCRAFT_ROBOT_PATH` の指す先が `robot\remote\Python` を正しく指していない(バージョン違い・パスの取り違え等) | 実際にCRIツールをインストールしたフォルダを辿り、`cri\atomcraft\criatomcraft_api_lib` 等が存在する `robot\remote\Python` のフルパスを指定し直す |
| `pip install` はできたのにMCPサーバー起動時に `ModuleNotFoundError: fastmcp` 等(**代替の素のPython+pip方式を選んだ場合のみ関係**) | `pip install` した Python と、MCPクライアントが実際に起動している `python` の実体が別物(venvの取り違え・Store版python aliasなど) | `python -c "import sys; print(sys.executable)"` で両者の実体パスを突き合わせる。必要なら手動登録で `python` をフルパス指定に変更する。uv方式(推奨)ではこの問題は発生しない |
| ツールが `UNSUPPORTED_VERSION` を返す | `ATOMCRAFT_ROBOT_PATH` が指すAtom Craftのバージョンが古く、呼び出したツールが要求する下限バージョンに満たない | 接続先のAtom Craftをアップデートするか、そのバージョンでは未対応の機能として諦める。必要な下限バージョンは [CAPABILITIES.md](CAPABILITIES.md) の機能マトリクスを参照 |
