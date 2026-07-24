"""cri.atomcraft 互換フェイク。実DLL・Atom Craftなしでtransport/toolsをテストする。

CRIの各API関数は {"succeed": bool, "message": str, "data": ...} 形式のdictを返す。
フェイクも同形式のcanned応答を返す。
"""


class _FakeConnectLib:
    def __init__(self):
        self.initialize_result = 0
        self.connect_result = 0
        self.status_value = 0  # 実測: 0=接続中, -1=未接続（2026-07-13スモークで確認）
        self.initialized = False
        self.connected = False

    def initialize(self):
        if self.initialize_result == 0:
            self.initialized = True
        return self.initialize_result

    def connect(self, host, port):
        if self.connect_result == 0:
            self.connected = True
        return self.connect_result

    def disconnect(self):
        self.connected = False
        return 0

    def finalize(self):
        self.initialized = False
        self.connected = False
        return 0

    def get_status(self):
        return self.status_value


class _FakeModule:
    def __init__(self, robot, name):
        self._robot = robot
        self._name = name

    def __getattr__(self, func_name):
        # capability-aware: 「旧robot Pythonには存在しない関数」を再現するため、
        # missing_functionsに登録された(module, func)はAttributeErrorを送出する
        # (hasattr/getattr(..., None)で「関数が無い」ことを検出できるようにする)
        if (self._name, func_name) in self._robot.missing_functions:
            raise AttributeError(func_name)

        def _call(*args):
            return self._robot._dispatch(self._name, func_name, args)
        _call.__name__ = func_name
        return _call


class FakeRobot:
    def __init__(self):
        self.connectlib = _FakeConnectLib()
        self.project = _FakeModule(self, "project")
        self.build = _FakeModule(self, "build")
        self.preview = _FakeModule(self, "preview")
        self.debug = _FakeModule(self, "debug")
        self.handlers = {}
        self.fail_queue = {}
        self.call_log = []
        self.missing_functions = set()  # capability-aware: (module, func)を持たないものとして扱う

    def set_handler(self, module, func, fn_or_dict):
        self.handlers[(module, func)] = fn_or_dict

    def set_missing(self, module, func):
        """(module, func)を「robot Python側に存在しない」ものとして扱う。

        __getattr__ が何でも生成する既定の挙動のままでは「関数が無い旧robot Python」を
        再現できないため、明示的にAttributeErrorを送出させるための登録口。
        """
        self.missing_functions.add((module, func))

    def fail_times(self, module, func, n, response):
        self.fail_queue[(module, func)] = [response] * n

    def _dispatch(self, module, func, args):
        self.call_log.append((module, func, args))
        queue = self.fail_queue.get((module, func))
        if queue:
            return queue.pop(0)
        handler = self.handlers.get((module, func))
        if handler is None:
            return {"succeed": False, "message": f"no handler for {module}.{func}", "data": None}
        if callable(handler):
            return handler(*args)
        return dict(handler)
