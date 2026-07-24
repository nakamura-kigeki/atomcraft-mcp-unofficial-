# Codex CLI向け導入手順

共通の準備(Python導入・robot-path設定・Atom Craftのスクリプトサーバー起動)は
[../SETUP.md](../SETUP.md) を先に済ませてください。このページはCodex CLI固有の
登録・接続確認手順のみを扱います。

Codex CLIはClaude Codeのプラグイン機構を使わないため、リポジトリをローカルに
`git clone` した上で、MCPサーバーとして直接登録します。

## 主手順: `codex mcp add`(uv版)

**uv方式を主手順とします。** uvが導入されていれば、Python 3.10と依存パッケージ
(`fastmcp`)は初回起動時にuvが自動的に解決するため、事前のpip installやPythonの実体確認は
不要です(uvの導入方法は [../SETUP.md](../SETUP.md) 手順1を参照)。

```powershell
codex mcp add atomcraft `
  --env ATOMCRAFT_HOST=127.0.0.1 `
  --env ATOMCRAFT_PORT=9000 `
  --env ATOMCRAFT_ROBOT_PATH="C:\path\to\...\robot\remote\Python" `
  --env PYTHONPATH= `
  --env PYTHONHOME= `
  -- uv run --python 3.10 --with "fastmcp>=2.0.0,<4" "C:\path\to\atomcraft-mcp\server\server.py"
```

- `atomcraft` はCodex側でのサーバー登録名です(任意の名前に変更可)。
- `--env` はstdioサーバーのみ有効なオプションで、指定した環境変数がサーバープロセスの
  起動時に渡されます。`ATOMCRAFT_HOST` / `ATOMCRAFT_PORT` は省略した場合の既定値
  (`127.0.0.1` / `9000`)と同じであれば省略可能です。
- `ATOMCRAFT_ROBOT_PATH` には、[../SETUP.md](../SETUP.md) 手順2で説明したRobot Python API
  (`robot\remote\Python`)までのフルパスを指定します。
- `--env PYTHONPATH=` / `--env PYTHONHOME=` は、それぞれの環境変数を空文字で渡す指定です。
  システム側に別のPython関連の環境変数が残っていた場合に、uvが解決するPython実行環境へ
  意図せず混入する(環境汚染)のを防ぐために設定しています。
- `--` 以降がサーバーの起動コマンドです。`uv run --python 3.10 --with "fastmcp>=2.0.0,<4"` で
  Python 3.10を固定し、`fastmcp` を実行時依存として指定した上で `server/server.py` を
  起動します。`--python 3.10` を明示しているのは、uvの既定Pythonが3.14系でありCRIのRobot
  Python APIが対応していないためです(Atom Craft Ver.3.55.00以降のRobot PythonはPython
  3.10/3.11のみ対応)。この固定構成での実機接続(`connect` / `ping` / `get_version`)は
  動作確認済みです。
- 初回起動はuvによる環境構築(Python 3.10・依存パッケージの取得)を含むため約30秒程度かかり、
  2回目以降は数秒に短縮されます。

登録内容の確認:

```
codex mcp list
```

`atomcraft` がコマンド・環境変数付きで一覧に表示されることを確認してください。

登録を削除したい場合:

```
codex mcp remove atomcraft
```

## 代替: python.exeフルパス直接指定方式(uvを使わない場合)

uvを使わず、[../SETUP.md](../SETUP.md) の「代替: 素のPython+pip方式」でPython 3.10/3.11に
`fastmcp` をpip installした環境をそのまま使いたい場合の方式です。この場合は `--` 以降に
`uv run ...` ではなく、確認済みのPythonのフルパスを直接指定してください。

```powershell
codex mcp add atomcraft `
  --env ATOMCRAFT_HOST=127.0.0.1 `
  --env ATOMCRAFT_PORT=9000 `
  --env ATOMCRAFT_ROBOT_PATH="C:\path\to\cri_adx_tools_ver_X_XX_XX\cri\tools\ADX2\ver.3\robot\remote\Python" `
  -- "C:\path\to\Python310\python.exe" "C:\path\to\atomcraft-mcp\server\server.py"
```

**`python -c "import sys; print(sys.executable)"` で確認したフルパスを、上記のように直接
指定してください。裸の `python` というコマンド名だけを指定する構成は避けてください。理由は
単なる念のための注意ではなく、実機検証で実際に踏んだ事故です。** Codex CLI自身のプロセス
起動は、普段使っているシェルとは別に独自のロジックでPATHを解決するため、シェル上で
`python` が指す実体と、Codexが実際に起動する実体が食い違うことがあります。この検証では、
シェル上は正しいPython 3.10を指しているにもかかわらず、Codexは別のラッパー経由でPython 2.7を
起動してしまい、MCPサーバーが起動直後に `SyntaxError`(非ASCII文字のエンコーディング未宣言)で
クラッシュし、ツールが1つも公開されない事象を確認しています。**裸の `python` は非推奨** —
必ずフルパス指定にしてください(詳細は「このリポジトリでの実機検証結果」を参照)。

登録内容の確認・削除は、上記「主手順」と同じく `codex mcp list` / `codex mcp remove atomcraft`
を使用してください。

## 代替手順: TOML直接編集

`codex mcp add` を使わず、`~/.codex/config.toml`(Windowsでは `%USERPROFILE%\.codex\config.toml`)
に直接追記することもできます。`codex mcp add` が内部的に生成するのも同じ形の設定です。

```toml
[mcp_servers.atomcraft]
command = "uv"
args = [
  "run",
  "--python", "3.10",
  "--with", "fastmcp>=2.0.0,<4",
  "C:\\path\\to\\atomcraft-mcp\\server\\server.py",
]

[mcp_servers.atomcraft.env]
ATOMCRAFT_HOST = "127.0.0.1"
ATOMCRAFT_PORT = "9000"
ATOMCRAFT_ROBOT_PATH = "C:\\path\\to\\cri_adx_tools_ver_X_XX_XX\\cri\\tools\\ADX2\\ver.3\\robot\\remote\\Python"
PYTHONPATH = ""
PYTHONHOME = ""
```

Windowsパスは `\\` によるエスケープが必要な点、`env` は `mcp_servers.atomcraft` とは別の
独立したテーブル `[mcp_servers.atomcraft.env]` として書く点(`env = { ... }` のインライン
テーブルではなく)に注意してください。手編集の場合はこの2点の書き間違いが事故の主因になるため、
特別な事情がなければ上記の `codex mcp add` を使うことを推奨します。

uvを使わない「代替: python.exeフルパス直接指定方式」を選ぶ場合は、`command` /
`args` を次のように置き換えてください(`env` の `PYTHONPATH` / `PYTHONHOME` の空文字指定は
uvの環境汚染対策のためのものなので不要です)。

```toml
[mcp_servers.atomcraft]
command = "C:\\path\\to\\Python310\\python.exe"
args = ["C:\\path\\to\\atomcraft-mcp\\server\\server.py"]
```

## tool_timeout_sec の案内

Codex CLIはMCPツール呼び出しに既定のタイムアウトがあり、これを超えると呼び出し中の処理を
打ち切ります。本サーバーの `atomcraft_build`(キューシートビルド)のように、Atom Craft側の
処理が数十秒〜それ以上かかりうるツールを呼ぶ場合、Codexの既定タイムアウト(既定60秒)より
先に打ち切られ、Atom Craft側では処理が継続しているのにCodex側だけ失敗として扱われることが
あります。長時間かかるツールを使う予定がある場合は、サーバー登録に `tool_timeout_sec` を
明示的に長めに設定してください。

```toml
[mcp_servers.atomcraft]
command = "uv"
args = [
  "run",
  "--python", "3.10",
  "--with", "fastmcp>=2.0.0,<4",
  "C:\\path\\to\\atomcraft-mcp\\server\\server.py",
]
tool_timeout_sec = 300

[mcp_servers.atomcraft.env]
...
```

`codex mcp add` に `tool_timeout_sec` を直接指定するオプションはないため、この設定だけは
TOMLへの追記(または `-c` オプションでの上書き)で行ってください。なお、本サーバー自身の
`atomcraft_build` ツールにも呼び出し単位で上書きできる `timeout_sec` 引数があります
([../HANDBOOK.md](../HANDBOOK.md) のタイムアウト設計を参照)。クライアント側とサーバー側の
両方のタイムアウトを、実際にかかる時間より長く揃える必要があります。

## 接続確認

`codex exec` などでプロンプトを実行し、登録した `atomcraft` サーバーのツール一覧が
見えることを確認してください。ツール一覧の取得自体はAtom Craft未起動でも可能です
(遅延接続。[README.md](../../../README.md) 構成図を参照)。uv方式の場合、初回接続確認時に
uvによる環境構築で数十秒待たされることがある点は事前に把握しておいてください。実際の操作
(`atomcraft_debug` の `ping` 等)を試す場合は、事前に[../SETUP.md](../SETUP.md) の手順3・4を
済ませてください。

確認する際は、単に「ツール一覧を教えて」とだけ頼むと、モデルがMCP経由でツールを実際に
検出する代わりに、リポジトリ内のソースコード(`server/atomcraft_mcp/tools/*.py` や
`AGENTS.md` — 本リポジトリのAGENTS.mdには21ツール名がすべて列挙されています)を読んで
それらしい回答を返してしまうことがあります。これは正しい名前が返っていても
「MCP経由で実際にツールが見えている」ことの確認にはならないため、次のように
**ファイル・シェルコマンドを使わないことを明示し、ツール検索の仕組みを使うよう指示する**
と、実際のMCP接続状況を切り分けやすくなります。

```
ファイルの読み取りやシェルコマンドは使わず、ツール検索の仕組みを使って、
atomcraft MCPサーバーが公開しているツール名を一覧で教えてください。
```

## このリポジトリでの実機検証結果

`codex mcp add` による登録 → `codex mcp list` での確認 → `codex exec` でのツール可視性確認 →
`codex mcp remove` での後始末、という一連の流れをこのリポジトリの開発環境で実機検証しました。

**1回目の登録(`-- python "...\server.py"` とコマンド名のみ指定)は、ツールが1つも
見えないという結果になりました。** `codex mcp add` / `codex mcp list` / `codex doctor`
はいずれも登録成功・サーバー1件・stdio有効と表示していたにもかかわらず、`codex exec`
のプロンプト応答は「このセッションには `atomcraft_debug` ツールが公開されていない」
「ツール検索でも `atomcraft` 名前空間を検出できなかった」という内容でした。
`RUST_LOG=trace` でCodex CLI自体のログを確認したところ、原因は次の通りでした。

- Codex CLIのプロセス起動は、`codex_rmcp_client::program_resolver` が独自に
  `python` というコマンド名を解決している(シェルの `PATH` 解決結果とは別)
- この環境では `python` が、Python 2.7 (`C:\Python27\python.exe`) を呼び出す
  独自のラッパー用batファイルに解決されていた(シェル上で
  `python -c "import sys; print(sys.executable)"` を実行すると正しくPython 3.10.11の
  実体が返るにもかかわらず、Codexの内部解決では別の実体が選ばれた)
- 結果、MCPサーバー(`server/server.py`)がPython 2.7で起動され、起動直後に
  `SyntaxError: Non-ASCII character '\xe8' ... but no encoding declared` で
  クラッシュしていた(ソースファイルの日本語コメントがPython 2の暗黙ASCII前提で
  弾かれたもの。Python 3であれば問題にならない)
- MCPサーバープロセスがクラッシュしているため、Codex側にはツールが1つも登録されず、
  かつ `codex mcp list` / `codex doctor` の表示上はこのクラッシュが一切見えない
  (どちらも設定内容の確認であって、実際のサーバー起動・ハンドシェイクの成否は
  別の手段でしか分からない)

**`--` 以降のコマンドを `python` から、実際に確認したフルパス
(`...\Python310\python.exe`)に変更して再登録したところ、症状は解消しました。**
`codex exec` から「ツール検索の仕組みを使い、ファイル・シェルは使わずにツール名を
列挙して」と指示したところ、実際のMCP経由のツール検索で21個すべてのツール名
(`atomcraft_debug` / `atomcraft_get_object` / `atomcraft_get_property` /
`atomcraft_get_tree` / `atomcraft_bulk_property` / `atomcraft_create_object` /
`atomcraft_modify_object` / `atomcraft_set_property` / `atomcraft_create_cue` /
`atomcraft_manage_material` / `atomcraft_manage_category` / `atomcraft_setup_aisac` /
`atomcraft_setup_automation` / `atomcraft_setup_mixer` / `atomcraft_manage_busmap` /
`atomcraft_manage_beatsync` / `atomcraft_manage_workunit` / `atomcraft_project_io` /
`atomcraft_manage_bookmark` / `atomcraft_build` / `atomcraft_preview`)が正しく返り、
所要時間は1ターンあたり体感12〜25秒程度でした(モデルの推論・ツール検索のオーバーヘッドが
主。Atom Craft本体は未起動のまま、遅延接続の設計通りツール一覧だけは取得できています)。

さらに `atomcraft_debug(action='status')` の実呼び出しも試みたところ、モデルは
`mcp_tool_call` としてツールを正しく認識・呼び出そうとしましたが、`codex exec`
の非対話実行では呼び出し確認(承認)をその場で与える手段がなく、
`"user cancelled MCP tool call"` として自動キャンセルされました。**非対話の
`codex exec` から実際にツールを実行(承認が必要な呼び出し)させたい場合は、
承認方針の設定([../SETUP.md](../SETUP.md) や Codex CLI本体のドキュメントを参照)を
別途検討してください。** 対話セッション(`codex` を通常起動して使う場合)であれば、
その場で呼び出しを承認できます。

検証後は `codex mcp remove atomcraft` で登録を削除し、環境を汚さずに後始末しています。

### この検証から得られる教訓

- **`codex mcp list` / `codex mcp get` / `codex doctor` の表示が正常でも、実際に
  MCPサーバーが起動・接続できているとは限りません。** これらは設定の登録状態を
  表示しているだけで、サーバープロセスの起動成否やハンドシェイクの結果までは
  検証していません
- `--` 以降のコマンドは、`python` のような裸のコマンド名ではなく、
  `python -c "import sys; print(sys.executable)"` で確認したフルパスを渡すことを
  強く推奨します(uv方式であればこの問題自体を回避できます。シェル上の `python` と
  Codex CLI自身が解決する `python` が食い違うことがあり、食い違った場合の失敗は
  Codex側の通常の確認コマンドには一切現れません)
- ツール一覧の確認プロンプトは、モデルが安易にソースコードを読んで回答しないよう、
  「ファイル・シェルコマンドを使わない」ことを明示すると、実際にMCP接続できているかの
  切り分けに有効です
