"""接続状態マシンと安全な呼び出しラッパー。

- 自動リトライは read のみ・1回のみ。エラー分類は envelope.classify に一本化
- タイムアウト時はDLLをfull_reset（finalize→initialize）し、世代カウンタで
  旧スレッドの遅延書き込みを破棄する（非スレッドセーフDLLの並行アクセス防止）
- 非冪等操作の結果不明は UNKNOWN_OUTCOME として呼び出し側に確認を促す
"""
import logging
import threading
import time

from .envelope import classify

logger = logging.getLogger(__name__)

READ = "read"
IDEMPOTENT_WRITE = "idempotent_write"
NON_IDEMPOTENT = "non_idempotent"

_RETRYABLE_INFRA = {"PARSE_ERROR", "CONNECTION_LOST", "TIMEOUT"}

_UNSET = object()  # tool_versionキャッシュ未取得の番人。Noneは「取得失敗」を意味するため区別する


class AtomCraftTransport:
    def __init__(self, robot, settings):
        self._robot = robot
        self.host = settings.host
        self.port = settings.port
        self._default_timeout = settings.api_timeout
        self._initialized = False
        self._connected = False
        self._generation = 0
        self._lock = threading.Lock()
        self._tool_version_cache = _UNSET
        self._UNSET = _UNSET  # インスタンス経由でも番人にアクセスできるようにする(テスト用)

    # --- ライフサイクル ---

    def _initialize(self) -> bool:
        if self._initialized:
            return True
        if self._robot.connectlib.initialize() != 0:
            logger.error("CriAcApiClient initialize failed")
            return False
        self._initialized = True
        return True

    def connect(self) -> bool:
        if not self._initialize():
            return False
        if self._robot.connectlib.connect(self.host, self.port) != 0:
            logger.error("connect to %s:%d failed", self.host, self.port)
            return False
        self._connected = True
        self._tool_version_cache = _UNSET  # 再接続・別バージョン接続でのキャッシュ残留防止
        return True

    def disconnect(self):
        if self._connected:
            self._robot.connectlib.disconnect()
            self._connected = False

    def reset(self):
        """公開リセット（旧 conn._connected=False ハックの置き換え）"""
        try:
            self.disconnect()
        except Exception:
            self._connected = False

    def full_reset(self):
        """DLLレベルの完全リセット。タイムアウト後の健全化に使う"""
        with self._lock:
            self._generation += 1
        try:
            self.disconnect()
            if self._initialized:
                self._robot.connectlib.finalize()
        except Exception:
            pass
        self._initialized = False
        self._connected = False
        self._tool_version_cache = _UNSET  # 再起動・別バージョン接続でのキャッシュ残留防止

    def finalize(self):
        self.full_reset()

    def tool_version(self):
        """接続先ツールのバージョンtuple。取得失敗はNoneをキャッシュ(接続リセットで無効化)"""
        if self._tool_version_cache is _UNSET:
            from .versioning import normalize_version_data
            # get_tool_version自体はCRI ADX Tools SDK Ver.3.46.04で追加された関数のため、
            # それより古いrobot Pythonでは属性自体が存在しない。直接属性参照(self._robot.debug.
            # get_tool_version)だとAttributeErrorが生で漏れるため、getattr(..., None)でガードし、
            # 無ければ取得失敗(None)としてfail-openにする。
            fn = getattr(self._robot.debug, "get_tool_version", None)
            if fn is None:
                self._tool_version_cache = None
            else:
                result = self.call(fn, idempotency=READ)
                self._tool_version_cache = (
                    normalize_version_data(result.get("data")) if result.get("succeed") else None)
        return self._tool_version_cache

    @property
    def is_connected(self) -> bool:
        return self._connected

    def status(self) -> dict:
        dll_status = None
        try:
            dll_status = self._robot.connectlib.get_status()
        except Exception:
            pass
        return {"host": self.host, "port": self.port,
                "initialized": self._initialized, "connected": self._connected,
                "dll_status": dll_status}

    # --- 呼び出し ---

    def _attempt(self, func, args, timeout: float) -> dict:
        """1回の呼び出し試行。TIMEOUT時はfull_reset済みで返る"""
        with self._lock:
            gen = self._generation
        holder = {}

        def _worker():
            try:
                r = func(*args)
            except Exception as e:
                r = {"succeed": False, "message": str(e), "_exception": True}
            # holderは_attempt呼び出しごとにローカルなので、遅延ワーカーの結果が
            # 別の呼び出しに混入することは構造的にない。世代チェックは防御の二重化
            # （full_reset後の遅延書き込みを明示的に破棄する）であり、
            # 停止できないDLL呼び出し自体は止められない点は設計上の既知の限界。
            with self._lock:
                if self._generation == gen:
                    holder["result"] = r

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        if "result" not in holder:
            logger.error("API call timed out (%.1fs), full-resetting DLL", timeout)
            self.full_reset()
            return {"succeed": False, "_code": "TIMEOUT",
                    "message": f"API call timed out after {timeout}s. Connection was reset."}
        result = holder["result"]
        if not isinstance(result, dict):
            return {"succeed": False, "message": "API returned non-dict result",
                    "_code": "PARSE_ERROR"}
        return result

    def _infra_code(self, result: dict) -> str:
        """試行結果からインフラ系コードを判定（なければ空文字）"""
        preset = result.get("_code")
        if preset in _RETRYABLE_INFRA:
            return preset
        if result.get("succeed"):
            return ""
        if result.get("_exception"):
            return "CONNECTION_LOST"
        code = classify(result.get("message", "")).code
        return code if code in _RETRYABLE_INFRA else ""

    def call(self, func, *args, idempotency: str = READ, timeout: float = None) -> dict:
        if timeout is None:
            timeout = self._default_timeout
        if not self._connected:
            if not self.connect():
                return {"succeed": False, "_code": "SERVER_UNREACHABLE",
                        "message": "Not connected to Atom Craft. "
                                   "Please ensure CRI Atom Craft is running "
                                   "with the script server enabled."}

        result = self._attempt(func, args, timeout)
        infra = self._infra_code(result)

        if infra and idempotency == READ:
            # 読み取り系のみ: リセット→再接続→1回だけ再試行
            logger.warning("read call failed with %s, retrying once", infra)
            if infra != "TIMEOUT":  # TIMEOUTはfull_reset済み
                self.reset()
            time.sleep(0.5)
            if self.connect():
                result = self._attempt(func, args, timeout)
                infra = self._infra_code(result)

        if infra and idempotency == NON_IDEMPOTENT:
            result["_code"] = "UNKNOWN_OUTCOME"
        elif infra:
            result["_code"] = infra
        return result
