"""バスマップ・AISAC・オートメーション・ミキサー設定ツール:
atomcraft_manage_busmap / atomcraft_setup_aisac / atomcraft_setup_automation /
atomcraft_setup_mixer

send_levelは0.0〜1.0の範囲外をAPI呼び出し前にINVALID_PARAMSで弾く。
"""
from typing import Literal, Optional

from ..envelope import from_result, make_error
from ..transport import READ, NON_IDEMPOTENT
from .. import catalog


def _with_graph_type_hint(payload: str, graph_type: str) -> str:
    """graph_type起因の失敗に、カタログ由来の近似候補ヒントを付け直す。"""
    return _rehint(payload, catalog.graph_type_hint(graph_type),
                   "グラフタイプ")


def _with_bus_effect_hint(payload: str, effect_name: str) -> str:
    """バスエフェクト名起因の失敗に、カタログ由来の近似候補ヒントを付け直す。"""
    return _rehint(payload, catalog.bus_effect_hint(effect_name),
                   "バスエフェクト")


def _rehint(payload: str, hint: str, marker: str) -> str:
    """失敗封筒のうち、messageにmarkerを含むものだけhintを差し替える。"""
    import json
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return payload
    if data.get("success") is not False:
        return payload
    if marker not in (data.get("error") or ""):
        return payload
    data["hint"] = hint
    return json.dumps(data, ensure_ascii=False)

BusmapAction = Literal[
    "create_for_cue", "get_for_cue", "create_custom", "get_custom", "get_for_aisac",
]
AisacAction = Literal["create", "create_graph", "add_point", "create_link", "get_graph"]
AutomationAction = Literal["create", "add_point", "get"]
MixerAction = Literal[
    "create_mixer", "add_bus_send", "remove_bus_send", "get_bus_effect",
    "copy_bus_effect", "move_bus", "sync_snapshot",
]


def make_tools(t):
    p = t._robot.project

    def atomcraft_manage_busmap(
        action: BusmapAction,
        busmap_name: Optional[str] = None,
        cue: Optional[str] = None,
    ) -> str:
        """バスマップの作成・取得を行う。

        action: create_for_cue, get_for_cue, create_custom, get_custom, get_for_aisac
        busmap_name: バスマップ名 (action=create_for_cue, get_for_cueで必須)
        cue: キューUUID (action=create_custom, get_customで必須)
        """
        if action == "create_for_cue":
            if not busmap_name:
                return make_error(
                    "busmap_name is required", "INVALID_PARAMS",
                    hint="action=create_for_cueにはbusmap_nameが必要です")
            result = t.call(p.create_busmap_for_cue, busmap_name, idempotency=NON_IDEMPOTENT)

        elif action == "get_for_cue":
            if not busmap_name:
                return make_error(
                    "busmap_name is required", "INVALID_PARAMS",
                    hint="action=get_for_cueにはbusmap_nameが必要です")
            result = t.call(p.get_busmap_for_cue, busmap_name, idempotency=READ)

        elif action == "create_custom":
            if not cue:
                return make_error(
                    "cue is required", "INVALID_PARAMS",
                    hint="action=create_customにはcue（UUID）が必要です")
            result = t.call(p.create_custom_busmap, cue, idempotency=NON_IDEMPOTENT)

        elif action == "get_custom":
            if not cue:
                return make_error(
                    "cue is required", "INVALID_PARAMS",
                    hint="action=get_customにはcue（UUID）が必要です")
            result = t.call(p.get_custom_busmap, cue, idempotency=READ)

        elif action == "get_for_aisac":
            result = t.call(p.get_busmap_for_aisac, idempotency=READ)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(BusmapAction.__args__)}",
                "INVALID_PARAMS")

        return from_result(result)

    def atomcraft_setup_aisac(
        action: AisacAction,
        parent: Optional[str] = None,
        object_name: Optional[str] = None,
        aisac_control: Optional[str] = None,
        aisac: Optional[str] = None,
        graph_type: Optional[str] = None,
        aisac_graph: Optional[str] = None,
        control_value: Optional[float] = None,
        destination_value: Optional[float] = None,
    ) -> str:
        """AISAC(Adaptive Interactive Sound AIsac Control)の作成とグラフ・ポイント設定。

        action:
          - create: AISAC作成 (parent, object_name, aisac_control必須)
          - create_graph: グラフ追加 (aisac, graph_type必須)
          - add_point: ポイント追加 (aisac_graph, control_value, destination_value必須)
          - create_link: AISACリンク作成 (parent, aisac必須)
          - get_graph: グラフ取得 (aisac, graph_type必須)

        graph_type: グラフ種別名。代表値は Volume, Pitch, Priority, PlaybackRate,
          PanAngle, PanVolume, PanWideness, PanSpread, BiquadFreq, BiquadQ,
          BusSendLevel1〜8, AisacControl0〜15(全43種)。誤った値には近似候補を
          添えたエラーが返る。全一覧はCRI公式オブジェクトリファレンスの
          「AISACグラフ・オートメーション…の種類と名前」節を参照。
        """
        if action == "create":
            if not parent or not object_name or not aisac_control:
                return make_error(
                    "parent, object_name, and aisac_control are required", "INVALID_PARAMS",
                    hint="action=createにはparent、object_name、aisac_controlが必要です")
            result = t.call(p.create_aisac, parent, object_name, aisac_control,
                            idempotency=NON_IDEMPOTENT)

        elif action == "create_graph":
            if not aisac or not graph_type:
                return make_error(
                    "aisac and graph_type are required", "INVALID_PARAMS",
                    hint="action=create_graphにはaisacとgraph_typeが必要です")
            result = t.call(p.create_aisac_graph, aisac, graph_type, idempotency=NON_IDEMPOTENT)

        elif action == "add_point":
            if not aisac_graph or control_value is None or destination_value is None:
                return make_error(
                    "aisac_graph, control_value, and destination_value are required",
                    "INVALID_PARAMS",
                    hint="action=add_pointにはaisac_graph、control_value、destination_valueが必要です")
            result = t.call(p.create_aisac_point, aisac_graph, control_value, destination_value,
                            idempotency=NON_IDEMPOTENT)

        elif action == "create_link":
            if not parent or not aisac:
                return make_error(
                    "parent and aisac are required", "INVALID_PARAMS",
                    hint="action=create_linkにはparentとaisacが必要です")
            result = t.call(p.create_aisaclink, parent, aisac, idempotency=NON_IDEMPOTENT)

        elif action == "get_graph":
            if not aisac or not graph_type:
                return make_error(
                    "aisac and graph_type are required", "INVALID_PARAMS",
                    hint="action=get_graphにはaisacとgraph_typeが必要です")
            result = t.call(p.get_aisac_graph, aisac, graph_type, idempotency=READ)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(AisacAction.__args__)}",
                "INVALID_PARAMS")

        payload = from_result(result)
        if graph_type and action in ("create_graph", "get_graph"):
            payload = _with_graph_type_hint(payload, graph_type)
        return payload

    def atomcraft_setup_automation(
        action: AutomationAction,
        parent: Optional[str] = None,
        graph_type: Optional[str] = None,
        automation: Optional[str] = None,
        time_ms: Optional[float] = None,
        destination_value: Optional[float] = None,
    ) -> str:
        """オートメーション(時間ベースのパラメータ変化)の作成とポイント追加。

        action:
          - create: オートメーション作成 (parent, graph_type必須)
          - add_point: ポイント追加 (automation, time_ms, destination_value必須)
          - get: 既存オートメーション取得 (parent, graph_type必須)

        parent: TrackやCue等、オートメーションを持たせる対象のUUID。
        graph_type: グラフ種別名。代表値は Volume, Pitch, Priority, PlaybackRate,
          PanAngle, PanVolume, PanWideness, PanSpread, BiquadFreq, BiquadQ,
          BusSendLevel1〜8, AisacControl0〜15(全43種)。誤った値には近似候補を
          添えたエラーが返る。全一覧はCRI公式オブジェクトリファレンス参照。

        なお `Automation` 型は汎用検索(atomcraft_get_object)では引けず、
        このツールの action='get' が唯一の取得経路。
        """
        if action == "create":
            if not parent or not graph_type:
                return make_error(
                    "parent and graph_type are required", "INVALID_PARAMS",
                    hint="action=createにはparentとgraph_typeが必要です")
            result = t.call(p.create_automation, parent, graph_type, idempotency=NON_IDEMPOTENT)

        elif action == "add_point":
            if not automation or time_ms is None or destination_value is None:
                return make_error(
                    "automation, time_ms, and destination_value are required", "INVALID_PARAMS",
                    hint="action=add_pointにはautomation、time_ms、destination_valueが必要です")
            result = t.call(p.create_automation_point, automation, time_ms, destination_value,
                            idempotency=NON_IDEMPOTENT)

        elif action == "get":
            if not parent or not graph_type:
                return make_error(
                    "parent and graph_type are required", "INVALID_PARAMS",
                    hint="action=getにはparentとgraph_typeが必要です")
            result = t.call(p.get_automation, parent, graph_type, idempotency=READ)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(AutomationAction.__args__)}",
                "INVALID_PARAMS")

        payload = from_result(result)
        if graph_type and action in ("create", "get"):
            payload = _with_graph_type_hint(payload, graph_type)
        return payload

    def atomcraft_setup_mixer(
        action: MixerAction,
        object_name: Optional[str] = None,
        bus_from: Optional[str] = None,
        bus_to: Optional[str] = None,
        send_level: float = 1.0,
        bus: Optional[str] = None,
        bus_effect_name: Optional[str] = None,
        bus_effect: Optional[str] = None,
        destination_bus: Optional[str] = None,
        destination_bus_effect: Optional[str] = None,
        mixer_snapshot: Optional[str] = None,
    ) -> str:
        """ミキサーの作成、バスセンド管理、バスエフェクト操作を行う。

        action:
          - create_mixer: ミキサー作成 (object_name必須)
          - add_bus_send: バスセンド追加 (bus_from, bus_to必須, send_level任意)
          - remove_bus_send: バスセンド削除 (bus_from, bus_to必須)
          - get_bus_effect: バスエフェクト取得 (bus, bus_effect_name必須)
          - copy_bus_effect: バスエフェクトコピー (bus_effect必須, destination_bus/destination_bus_effect任意)
          - move_bus: バス移動 (bus必須, destination_bus任意)
          - sync_snapshot: スナップショットのエフェクトパラメータ同期 (bus_effect, mixer_snapshot必須)

        send_level: バスセンドレベル (0.0〜1.0、action=add_bus_sendで使用)
        """
        if send_level is not None and not (0.0 <= send_level <= 1.0):
            return make_error(
                "send_level must be between 0.0 and 1.0", "INVALID_PARAMS",
                hint="send_levelは0.0〜1.0")

        if action == "create_mixer":
            if not object_name:
                return make_error(
                    "object_name is required", "INVALID_PARAMS",
                    hint="action=create_mixerにはobject_nameが必要です")
            result = t.call(p.create_mixer, object_name, idempotency=NON_IDEMPOTENT)

        elif action == "add_bus_send":
            if not bus_from or not bus_to:
                return make_error(
                    "bus_from and bus_to are required", "INVALID_PARAMS",
                    hint="action=add_bus_sendにはbus_fromとbus_toが必要です")
            result = t.call(p.add_mixer_bus_send, bus_from, bus_to, send_level,
                            idempotency=NON_IDEMPOTENT)

        elif action == "remove_bus_send":
            if not bus_from or not bus_to:
                return make_error(
                    "bus_from and bus_to are required", "INVALID_PARAMS",
                    hint="action=remove_bus_sendにはbus_fromとbus_toが必要です")
            result = t.call(p.remove_mixer_bus_send, bus_from, bus_to, idempotency=NON_IDEMPOTENT)

        elif action == "get_bus_effect":
            if not bus or not bus_effect_name:
                return make_error(
                    "bus and bus_effect_name are required", "INVALID_PARAMS",
                    hint="action=get_bus_effectにはbusとbus_effect_nameが必要です")
            result = t.call(p.get_bus_effect, bus, bus_effect_name, idempotency=READ)

        elif action == "copy_bus_effect":
            if not bus_effect:
                return make_error(
                    "bus_effect is required", "INVALID_PARAMS",
                    hint="action=copy_bus_effectにはbus_effectが必要です")
            result = t.call(p.copy_bus_effect, bus_effect, destination_bus, destination_bus_effect,
                            idempotency=NON_IDEMPOTENT)

        elif action == "move_bus":
            if not bus:
                return make_error(
                    "bus is required", "INVALID_PARAMS",
                    hint="action=move_busにはbusが必要です")
            result = t.call(p.move_bus, bus, destination_bus, idempotency=NON_IDEMPOTENT)

        elif action == "sync_snapshot":
            if not bus_effect or not mixer_snapshot:
                return make_error(
                    "bus_effect and mixer_snapshot are required", "INVALID_PARAMS",
                    hint="action=sync_snapshotにはbus_effectとmixer_snapshotが必要です")
            result = t.call(p.sync_snapshot_effect_parameters, bus_effect, mixer_snapshot,
                            idempotency=NON_IDEMPOTENT)

        else:
            return make_error(
                f"Unknown action: {action}. Valid actions: {', '.join(MixerAction.__args__)}",
                "INVALID_PARAMS")

        payload = from_result(result)
        if bus_effect_name and action in ("get_bus_effect", "copy_bus_effect"):
            payload = _with_bus_effect_hint(payload, bus_effect_name)
        return payload

    return [
        atomcraft_manage_busmap,
        atomcraft_setup_aisac,
        atomcraft_setup_automation,
        atomcraft_setup_mixer,
    ]
