"""有効値カタログと近似候補サジェスト。

## 一次情報(CRI公式マニュアル)

- **オブジェクト型名・バスエフェクト名・グラフ種別**: オブジェクトリファレンス
  `criatom_tools_atomcraft_api_refobject.html`
  (型名のほかに「バスエフェクトの種類と名前」「AISACグラフ・オートメーション・
  再生パラメーター設定アクションの種類と名前」の節を含む)
- **プロパティフィールド名**: パラメーターリファレンス5ページ
  `..._api_refparam.html` / `_global` / `_workunittree` / `_aisac` / `_materialtree`

いずれも `https://game.criware.jp/manual/adx2_tool/latest/<ページ名>` で参照できる。
本モジュールのデータは、これらのページのローカル同梱版(CRIツール内 manual/jpn/contents)
から機械抽出したうえで実機に照合して確定させた。

## 検証状況(2026-07-25)

実機Atom Craft **Ver.3.57.02(製品版)** で照合。テスト環境からの Ver.3.56.01(LE版)
での検証結果も統合している。公式一覧と実機は完全には一致しないため、カタログは
**「公式 ∪ 実機」**で構成する:

- 公式に記載が無いが実機が受理する型が12件ある(OBJECT_TYPES 末尾の節)
- 公式記載の `Automation` は汎用検索から引けない(専用アクセサ経由でのみ取得可)
- 公式記載の graph_type `Spread` は実機で拒否され、実際の名前は `PanSpread`

網羅性は保証できない(公式・実機のどちらも完全な列挙手段を提供していない)。
詳細と限界は docs/dev/CAPABILITIES.md「オブジェクト型名の実機検証」を参照。
ヒント生成のロジック自体は単純に保つ(difflibによる近似マッチのみ)。
"""

from __future__ import annotations

import difflib

# CRI公式オブジェクトリファレンス記載の全型名(モジュールdocstringの出典参照)。
# 実機Ver.3.56.01(LE)の find_all_by_type で全件照合済み(Automationのみ拒否)。
# なお "Waveform" は未文書だが受理される "Material" の別名(返却type_nameはMaterial)
# のため、このリストには載せない。
OBJECT_TYPES: list[str] = [
    # --- プロジェクト設定・ユーザー設定・全体設定 ---
    "Project",
    "UserSettings",
    "GlobalFolder",
    "TargetConfigFolder",
    "TargetConfigPc",
    "TargetConfigPs4",
    "TargetConfigXboxOne",
    "TargetConfigSwitch",
    "TargetConfigiPhone",  # 小文字の i が正
    "TargetConfigAndroid",
    "TargetConfigWebGl",  # WebGL ではなく WebGl が正
    "TargetConfigPublic",
    "LanguageSettingsFolder",
    "LanguageSettings",
    "OutputPortFolder",
    "OutputPort",
    "VoicePoolFolder",
    "VoicePool",
    "MixerFolder",
    "Mixer",
    "MixerSnapshot",
    "Bus",
    "BusMaster",
    "BusMap",
    "CategoryFolder",
    "CategoryGroup",
    "Category",
    "GameVariableFolder",
    "GameVariable",
    "SelectorFolder",
    "Selector",
    "SelectorLabel",
    "ReactFolder",
    "React",
    "VoiceLimitGroupFolder",
    "VoiceLimitGroup",
    "AisacControlFolder",
    "AisacControl",
    "GlobalAisacFolder",
    # --- AISAC ---
    "Aisac",
    "AisacGraph",
    "AisacPoint",
    # --- ワークユニットツリー ---
    "WorkUnitFolder",
    "WorkUnitSubFolder",
    "WorkUnit",
    "ReferenceAisacFolder",
    "CueSheetRootFolder",  # atomcraft_get_tree が返す type 値
    "CueSheetFolder",
    "CueSheet",
    "CueFolder",
    "PrivateCueFolder",
    "Cue",
    "LoopMarker",
    "StartMarker",
    "EndMarker",
    "CallbackMarker",
    "ReactEndMarker",
    # "Automation" は find_objects / get_children からは引けない(実機Ver.3.57.02・
    # Ver.3.56.01(LE)の双方で INVALID_TYPE)。ただし専用アクセサ
    # project.get_automation(parent, graph_type) 経由では取得できる
    # (MCPでは atomcraft_setup_automation(action='get', parent=..., graph_type=...)。
    # 実機3.57.02で Track を親に graph_type='Volume' の取得成功を確認済み)。
    # ルートフォルダ系が専用methodを要するのと同じ「汎用検索から引けない型」であり、
    # 存在しない型ではない。
    "Automation",
    "AutomationPoint",
    "Track",
    "WaveformRegion",
    "SubSequence",
    "CueLink",
    "ExternalCueLink",
    "ActionTrack",
    "ActionStart",
    "ActionStop",
    "ActionPause",
    "ActionResume",
    "ActionMute",
    "ActionSetPlaybackParameter",
    "ActionSetSelectorLabel",
    "PlayerActionTrack",
    "ActionPlayerFader",
    "AisacLink",
    "Block",
    "BeatSync",
    "TrimmingInfo",
    "FadeInfo",
    "StopAction",
    # --- マテリアルツリー ---
    "MaterialInfo",
    "MaterialRootFolder",
    "MaterialSubFolder",
    "Material",
    # --- 公式オブジェクトリファレンス未記載。実機Ver.3.57.02(製品版)・Ver.3.56.01(LE)の
    #     双方で find_all_by_type が受理することを確認済み。公式一覧が不完全であるため、
    #     カタログは「公式 ∪ 実機」で構成する必要がある。未発見の型がまだある前提で扱うこと。
    "ParameterAction",  # パラメーター監視アクション本体
    "ParameterActionCondition",  # その条件(トリガー/リセット)
    "SpeakerSetting",
    "SpeakerSettingFolder",
    "DspSetting",
    "DspSettingFolder",
    "DspBusMaster",  # 実機ではBusMasterと同一UUIDを返す
    "BusMapRootFolder",
    "BusMapFolder",
    "BusMapAisacGraph",
    "BeatSyncLabelFolder",
    "CueSheetSubFolder",
]

# 左辺の型名も実機に受理されるが、右辺と同一のオブジェクトを返すエイリアス
# (get_property が返す type_name は右辺)。実機でUUID集合の一致を確認済み。
#
# エイリアスを OBJECT_TYPES に載せると同じ実体が二重に見えるため、原則として
# 正規名(右辺)のみを載せる。ただし以下2件は例外的に OBJECT_TYPES にも含まれる:
#   - AutomationPoint: 公式オブジェクトリファレンスに正式な型として記載があるため
#   - CueSheetSubFolder: 公式未記載だが実機が受理する型として0.2.4で追加したため
# どちらも「OBJECT_TYPESに残すか」は未解決の論点として保留している。
#
# なお child_types にエイリアス同士を併記しても、atomcraft_get_tree 側が
# 子UUIDで重複排除するため実害は出ない(0.2.6以降)。この辞書は将来
# find_all_by_type 等で必要になったときのためのデータとして保持する。
OBJECT_TYPE_ALIASES: dict[str, str] = {
    "Waveform": "Material",  # 実機3.57.02で152件、3.56.01(LE)で5件が一致
    "LanguageSettingFolder": "LanguageSettingsFolder",  # 単数形/複数形
    "AutomationPoint": "AisacPoint",  # 3.57.02で454件、3.56.01(LE)で14件が一致
    "CueSheetSubFolder": "CueSheetFolder",  # 3.56.01(LE)で同一UUIDを確認
}

# INVALID_TYPE時のヒントで、近似候補が1件も出なかった場合に示す代表例。
_REPRESENTATIVE_TYPES: list[str] = [
    "Project", "WorkUnit", "CueSheet", "CueSheetRootFolder", "Cue", "Track",
    "WaveformRegion", "Material", "MaterialRootFolder", "Bus", "Mixer",
    "Aisac", "AisacControl", "Category", "Selector",
]

# AISACグラフ・オートメーション・再生パラメーター設定アクションのグラフ種別。
# atomcraft_setup_aisac(action='create_graph'/'get_graph') と
# atomcraft_setup_automation(action='create'/'get') の graph_type 引数に渡す値。
# 公式リスト43件を実機Ver.3.57.02の project.get_automation(読み取り)で全件照合し、
# 42件が有効。公式記載の "Spread" のみ拒否され、実際の名前は "PanSpread" だった
# (無効な値には「指定したグラフタイプはサポートしていません」が返るため判定可能)。
GRAPH_TYPES: list[str] = [
    "Volume", "Pitch", "Priority", "PreDelayTime", "PlaybackRate",
    "BandPassHigh", "BandPassLow", "BiquadFreq", "BiquadQ", "BiquadGain",
    "PanAngle", "PanVolume", "PanInteriorDistance", "PanCenter", "PanLFE",
    "PanWideness", "PanSpread",  # 公式表記の "Spread" は実機で拒否される
    "EgAttackTimeMs", "EgReleaseTimeMs",
    "BusSendLevel1", "BusSendLevel2", "BusSendLevel3", "BusSendLevel4",
    "BusSendLevel5", "BusSendLevel6", "BusSendLevel7", "BusSendLevel8",
    "AisacControl0", "AisacControl1", "AisacControl2", "AisacControl3",
    "AisacControl4", "AisacControl5", "AisacControl6", "AisacControl7",
    "AisacControl8", "AisacControl9", "AisacControl10", "AisacControl11",
    "AisacControl12", "AisacControl13", "AisacControl14", "AisacControl15",
]

# バスエフェクトの種類名(atomcraft_setup_mixer のエフェクト操作で使う)。
# 公式リスト21件。実機Ver.3.57.02では、読み取りAPI(get_bus_effect /
# get_dsp_bus_effect)が「名前が無効」と「そのバスに未装着」を同一メッセージで
# 返すため、名前の有効性を網羅判定できない。うち15件はマスターバス上に実在を
# 確認済み(下記コメントの★)。残り6件は未装着だった可能性が高く、無効と確定した
# わけではないので公式記載どおり保持する。
BUS_EFFECT_TYPES: list[str] = [
    "BandpassFilter",  # ★
    "BiquadFilter",  # ★
    "Limiter",
    "Compressor",
    "Delay",  # ★
    "Echo",  # ★
    "PitchShifter",  # ★
    "Reverb",  # ★
    "3BandEQ",  # ★
    "32BandEQ",
    "Chorus",  # ★
    "Flanger",  # ★
    "Distortion",  # ★
    "AmplitudeAnalyzer",  # ★
    "Surrounder",
    "I3DL2Reverb",
    "MultiTapDelay",  # ★
    "Matrix",
    "Phaser",  # ★
    "BitCrusher",  # ★
    "HeadphoneVirtualSurround",  # ★
]

# タイプ別の既知有効プロパティフィールド一覧(出典はモジュールdocstring)。
# KNOWN_FIELDS_LIVE_VERIFIED に載る型は実機Ver.3.57.02で全フィールドの取得成功を
# 確認済み。それ以外は公式パラメーターリファレンス記載値(検証プロジェクトに対象
# オブジェクトが無く未検証)。"*" はどのタイプにも該当しない場合のフォールバック。
KNOWN_FIELDS_LIVE_VERIFIED = frozenset({
    "ActionSetPlaybackParameter", "ActionSetSelectorLabel", "ActionStart", "ActionStop",
    "ActionTrack", "Aisac", "AisacControl", "AisacGraph", "Block", "Bus", "BusMap",
    "BusMaster", "CallbackMarker", "Category", "Cue", "CueLink", "CueSheet",
    "CueSheetRootFolder", "EndMarker", "ExternalCueLink", "GameVariable", "LoopMarker",
    "Material", "MaterialRootFolder", "MaterialSubFolder", "Mixer", "Project", "React",
    "ReactEndMarker", "Selector", "SelectorLabel", "StartMarker", "SubSequence", "Track",
    "UserSettings", "VoiceLimitGroup", "WaveformRegion", "WorkUnit"
})

KNOWN_FIELDS: dict[str, list[str]] = {
    "*": [
        "Name", "Comment"
    ],
    "ActionMute": [
        "Name", "Comment", "DelayTimeMS"
    ],
    "ActionPause": [
        "Name", "Comment", "DelayTimeMS"
    ],
    "ActionResume": [
        "Name", "Comment", "DelayTimeMS"
    ],
    "ActionSetPlaybackParameter": [
        "Name", "Comment", "DelayTimeMS", "ParameterType", "Parameter", "Ratio", "CurveType",
        "CurveStrength"
    ],
    "ActionSetSelectorLabel": [
        "Name", "Comment", "DelayTimeMS"
    ],
    "ActionStart": [
        "Name", "Comment", "DelayTimeMS", "FadeTime"
    ],
    "ActionStop": [
        "Name", "Comment", "DelayTimeMS", "FadeTime"
    ],
    "ActionTrack": [
        "Name", "Comment", "Omit", "ScopeType", "TargetObject"
    ],
    "Aisac": [
        "Name", "Comment", "AisacControlType", "AisacControl", "DefaultControlValueFlag",
        "DefaultControlValue", "RandomRange", "ModulationType", "ModulationStepTimeMS",
        "ModulationTriggerType", "ModulationTriggerKey"
    ],
    "AisacControl": [
        "Name", "Comment", "ControlId"
    ],
    "AisacGraph": [
        "GraphType"
    ],
    "Block": [
        "Name", "Comment", "BlockDuration", "BlockTransitionDestinationType",
        "BlockPlaybackLoopNum", "BlockDivisionNum", "BlockTransitionMode",
        "BlockTransitionTiming", "BlockTransitionBehavior"
    ],
    "Bus": [
        "Name", "Comment", "Volume", "PanAngle", "PanDistance", "PanVolume"
    ],
    "BusMap": [
        "Name", "Comment", "BusName1", "BusName2", "BusName3", "BusName4", "BusName5",
        "BusName6", "BusName7", "BusName8"
    ],
    "BusMaster": [
        "Name", "Comment", "Volume", "PanAngle", "PanDistance", "PanVolume"
    ],
    "CallbackMarker": [
        "Comment", "MarkerStartTime", "MarkerEndTime", "CallbackId", "CallbackTag"
    ],
    "Category": [
        "Name", "Comment", "CategoryId", "MultiplePlaybackProhibitionTime", "Volume",
        "CategoryCueLimitEnableFlag", "CategoryCueLimitNum"
    ],
    "Cue": [
        "Name", "Comment", "Omit", "CueID", "SequenceType", "PlaybackMode",
        "IgnoreAtomExPlayer", "UserData", "VoiceBehaviorMode", "PlaybackRatio",
        "MultiplePlaybackProhibitionTime", "MuteFlag", "Volume", "VolumeRnd", "Pitch",
        "PitchRnd", "PanType", "PanAngle", "PanAngleRnd", "PanDistance", "PanDistanceRnd",
        "Pos3dInsideAngle", "Pos3dOutsideAngle", "Pos3dDistanceMin", "Pos3dDistanceMax",
        "Pos3dDopplerCoefficient", "Pos3dDistanceAisacControl",
        "Pos3dListenerBasedAzimuthAngleAisacControl",
        "Pos3dSoundSourceBasedAzimuthAngleAisacControl",
        "Pos3dListenerBasedElevationAngleAisacControl",
        "Pos3dSoundSourceBasedElevationAngleAisacControl", "PlaybackPositionBehavior",
        "CueLimitEnableFlag", "CueLimitNum", "CuePriorityType", "CategoryCuePriorityLevel",
        "CategoryCuePriorityType", "BusMap", "UseBusSend1", "UseBusSend2", "UseBusSend3",
        "UseBusSend4", "UseBusSend5", "UseBusSend6", "UseBusSend7", "UseBusSend8",
        "BusSendLevel1", "BusSendLevel2", "BusSendLevel3", "BusSendLevel4", "BusSendLevel5",
        "BusSendLevel6", "BusSendLevel7", "BusSendLevel8", "PanVolume", "CenterVolume",
        "LFEVolume", "Pos3dVolume", "DefaultSelectorLabel", "SwitchVariable", "ComboInterval",
        "ComboLoopBack", "PlaybackProbability", "RandomNoRepeatingCount", "CuePriority"
    ],
    "CueLink": [
        "Name", "Comment", "Omit", "Volume", "VolumeRnd", "Pitch", "PitchRnd", "PanAngle",
        "PanAngleRnd", "PanDistance", "PanDistanceRnd", "PanVolume", "CenterVolume",
        "LFEVolume", "Pos3dVolume", "UseBusSend1", "UseBusSend2", "UseBusSend3", "UseBusSend4",
        "UseBusSend5", "UseBusSend6", "UseBusSend7", "UseBusSend8", "BusSendLevel1",
        "BusSendLevel2", "BusSendLevel3", "BusSendLevel4", "BusSendLevel5", "BusSendLevel6",
        "BusSendLevel7", "BusSendLevel8", "DelayTimeMS", "PlaybackTimingRnd",
        "AutoRepeatInterval", "AutoRepeatNum", "PreDelayTime", "PreDelayTimeRnd",
        "PlaybackProbability"
    ],
    "CueSheet": [
        "Name", "Comment", "Volume", "DefaultPlaybackPositionBehavior", "IncludeCueNameToAcb",
        "EmbedLinkCue", "StartCueId", "CueLimitEnableFlag", "CueLimitNum", "CuePriorityType",
        "BusMap", "AcbOutputFilePath", "AwbOutputFilePath"
    ],
    "CueSheetFolder": [
        "Name", "Comment", "BusMap"
    ],
    "CueSheetRootFolder": [
        "Name", "Comment", "BusMap"
    ],
    "EndMarker": [
        "Comment", "MarkerStartTime", "MarkerEndTime"
    ],
    "ExternalCueLink": [
        "Name", "Comment", "Omit", "Volume", "VolumeRnd", "Pitch", "PitchRnd", "PanAngle",
        "PanAngleRnd", "PanDistance", "PanDistanceRnd", "PanVolume", "CenterVolume",
        "LFEVolume", "Pos3dVolume", "UseBusSend1", "UseBusSend2", "UseBusSend3", "UseBusSend4",
        "UseBusSend5", "UseBusSend6", "UseBusSend7", "UseBusSend8", "BusSendLevel1",
        "BusSendLevel2", "BusSendLevel3", "BusSendLevel4", "BusSendLevel5", "BusSendLevel6",
        "BusSendLevel7", "BusSendLevel8", "DelayTimeMS", "PlaybackTimingRnd",
        "AutoRepeatInterval", "AutoRepeatNum", "PreDelayTime", "PreDelayTimeRnd",
        "PlaybackProbability", "ExternalLinkCueName", "ExternalLinkCueId", "LinkCueSheet",
        "ExternalLinkCueLengthMS"
    ],
    "FadeInfo": [
        "Name", "Comment", "FadeInTime", "FadeInCurveType", "FadeInCurveStrength",
        "FadeOutTime", "FadeOutCurveType", "FadeOutCurveStrength"
    ],
    "GameVariable": [
        "Name", "Comment", "VariableId", "InitValue"
    ],
    "LoopMarker": [
        "Comment", "MarkerStartTime", "MarkerEndTime", "LoopCount", "InfinityLoopFlag",
        "EnableRegionPlaybackSync"
    ],
    "Material": [
        "Name", "Comment", "OutputPort", "SrcFileAbsolutePath", "Channels", "SamplingRate",
        "BitsPerSamples", "SampleFrames", "LocalFileLastWriteTime", "DisplayLoopType",
        "StreamType", "EncodeType", "EncodeQuality", "UsePrefetchTime", "PrefetchTime",
        "UseHcaCutoffFrequency", "HcaCutoffFrequency", "ResamplingRate", "EncodeVolume"
    ],
    "MaterialRootFolder": [
        "Name", "Comment", "OutputPort", "StreamType", "EncodeType", "EncodeQuality"
    ],
    "MaterialSubFolder": [
        "Name", "Comment", "OutputPort", "StreamType", "EncodeType", "EncodeQuality"
    ],
    "Mixer": [
        "Name", "Comment"
    ],
    "OutputPort": [
        "Name", "Comment", "OutputPortType", "EnableMonauralMix", "UseDedicatedMixer",
        "FallbackBehavior"
    ],
    "ParameterAction": [
        "Name", "Comment", "ParameterActionTarget", "ResetOutOfRange"
    ],
    "ParameterActionCondition": [
        "Name", "Comment", "CondType", "Logic", "ObserveValueType", "Operator", "Value"
    ],
    "PlayerActionTrack": [
        "Name", "Comment", "Omit", "ScopeType"
    ],
    "Project": [
        "Name", "Comment", "ProjectFilePath"
    ],
    "React": [
        "Name", "Comment", "ChangeCategory", "TriggerCategory", "ReactType",
        "IncludeCueInPause", "ChangeTime", "ChangeCurveType", "ChangeCurveStrength",
        "HoldType", "HoldTime", "ReturnTime", "ReturnCurveType", "ReturnCurveStrength",
        "ChangeParameter", "Level", "ChangeAisacModKeyFlag", "ChangeAisacModKey",
        "ReturnAisacModKeyFlag", "ReturnAisacModKey"
    ],
    "ReactEndMarker": [
        "Comment", "MarkerStartTime", "MarkerEndTime"
    ],
    "Selector": [
        "Name", "Comment", "GlobalLabel"
    ],
    "SelectorLabel": [
        "Name", "Comment"
    ],
    "StartMarker": [
        "Comment", "MarkerStartTime", "MarkerEndTime"
    ],
    "StopAction": [
        "Name", "Comment", "TargetObject", "ActionType", "ScopeType", "Enable"
    ],
    "SubSequence": [
        "Name", "Comment", "Omit", "SequenceType", "Volume", "VolumeRnd", "Pitch", "PitchRnd",
        "PanAngle", "PanAngleRnd", "PanDistance", "PanDistanceRnd", "PanVolume",
        "CenterVolume", "LFEVolume", "Pos3dVolume", "UseBusSend1", "UseBusSend2",
        "UseBusSend3", "UseBusSend4", "UseBusSend5", "UseBusSend6", "UseBusSend7",
        "UseBusSend8", "BusSendLevel1", "BusSendLevel2", "BusSendLevel3", "BusSendLevel4",
        "BusSendLevel5", "BusSendLevel6", "BusSendLevel7", "BusSendLevel8", "SwitchRange",
        "DelayTimeMS", "PlaybackTimingRnd", "AutoRepeatInterval", "AutoRepeatNum",
        "PreDelayTime", "PreDelayTimeRnd", "SwitchVariable", "ComboInterval", "ComboLoopBack",
        "PlaybackProbability"
    ],
    "Track": [
        "Name", "Comment", "Omit", "OutputPort", "TrackMonoFlag", "MuteFlag", "Volume",
        "VolumeRnd", "Pitch", "PitchRnd", "PanAngle", "PanAngleRnd", "PanDistance",
        "PanDistanceRnd", "BiquadType", "BiquadCof", "BiquadCofRnd", "BiquadQ", "BiquadQRnd",
        "BiquadGain", "BandPassLow", "BandPassHigh", "UseBusSend1", "UseBusSend2",
        "UseBusSend3", "UseBusSend4", "UseBusSend5", "UseBusSend6", "UseBusSend7",
        "UseBusSend8", "BusSendLevel1", "BusSendLevel2", "BusSendLevel3", "BusSendLevel4",
        "BusSendLevel5", "BusSendLevel6", "BusSendLevel7", "BusSendLevel8", "PanVolume",
        "CenterVolume", "LFEVolume", "Pos3dVolume", "SwitchRange", "SelectorLabel",
        "RandomWeight", "PlaybackProbability", "PlaybackPositionBehavior"
    ],
    "TrimmingInfo": [
        "Name", "Comment", "TrimmingStartTime", "TrimmingEndTime"
    ],
    "UserSettings": [
        "Name", "Comment", "AcfOutputFlag", "BuildForUnityFlag", "CueSheetHierarchyOutputFlag",
        "CsHeaderOutputFlag", "HeaderOutputFlag", "JsonOutputFlag", "AcbInfoFileOutputFlag"
    ],
    "VoiceLimitGroup": [
        "Name", "Comment", "VoiceLimitNum"
    ],
    "VoicePool": [
        "Name", "Comment", "CodecType", "StreamType", "NumVoices", "MinChannels",
        "MaxChannels", "MaxSamplingRate"
    ],
    "WaveformRegion": [
        "Name", "Comment", "LinkMaterial", "Omit", "IgnoreLoop", "StopAtLoopEnd", "Volume",
        "VolumeRnd", "EgAttackTimeMs", "EgAttackCurveType", "EgAttackCurveStrength",
        "EgHoldTimeMs", "EgDecayTimeMs", "EgDecayCurveType", "EgDecayCurveStrength",
        "EgSustainLevel", "EgReleaseTimeMs", "EgReleaseCurveType", "EgReleaseCurveStrength",
        "Pitch", "PitchRnd", "PanType", "PanAngle", "PanAngleRnd", "PanDistance",
        "PanDistanceRnd", "PlaybackPositionBehavior", "FixedAngleZeroWithinMinDistance",
        "UseTrackFilterSettings", "BiquadType", "BiquadCof", "BiquadCofRnd", "BiquadQ",
        "BiquadQRnd", "BiquadGain", "BandPassLow", "BandPassHigh", "VoicePriority",
        "VoicePriorityType", "VoiceLimitGroup", "UseBusSend1", "UseBusSend2", "UseBusSend3",
        "UseBusSend4", "UseBusSend5", "UseBusSend6", "UseBusSend7", "UseBusSend8",
        "BusSendLevel1", "BusSendLevel2", "BusSendLevel3", "BusSendLevel4", "BusSendLevel5",
        "BusSendLevel6", "BusSendLevel7", "BusSendLevel8", "PanVolume", "CenterVolume",
        "LFEVolume", "Pos3dVolume", "DelayTimeMS", "PlaybackTimingRnd", "AutoRepeatInterval",
        "AutoRepeatNum", "PreDelayTime", "PreDelayTimeRnd", "PlaybackProbability"
    ],
    "WorkUnit": [
        "Name", "Comment", "UseWorkUnitManagedMaterials", "MaterialAbsolutePath",
        "WorkUnitAbsolutePath"
    ],
}

# タイプ別の「取得できないフィールド」→代替経路のヒント。
UNAVAILABLE_FIELDS: dict[str, dict[str, str]] = {
    "Cue": {
        "Category": "atomcraft_manage_category(action='get') を使用してください",
        "Categories": "atomcraft_manage_category(action='get') を使用してください",
        "Pan": "利用不可",
        "DSPBusSetting": "atomcraft_manage_busmap(action='get_for_cue') を使用してください",
    },
}


def suggest(value: str, candidates: list[str], n: int = 3) -> list[str]:
    """value に近い候補を candidates から最大 n 件返す。"""
    return difflib.get_close_matches(value, candidates, n=n, cutoff=0.5)


def type_hint(bad_type: str) -> str:
    """無効なオブジェクトタイプ名向けのヒント文字列を生成する。

    84件の全リストをダンプするとエラーのたびに約1,300文字がhintに載って
    LLMの文脈を浪費するため、近似候補のみを返し、候補が1件も無いときだけ
    代表例と公式リファレンスへの誘導を示す。
    """
    candidates = suggest(bad_type, OBJECT_TYPES)
    if candidates:
        return (
            f"'{bad_type}' は利用できません。"
            f"近い候補: {', '.join(candidates)}"
        )
    return (
        f"'{bad_type}' は利用できません。近い候補も見つかりませんでした。"
        f"代表的なタイプ例: {', '.join(_REPRESENTATIVE_TYPES)}。"
        "全一覧はCRI公式のオブジェクトリファレンス"
        "(criatom_tools_atomcraft_api_refobject.html)を参照してください。"
    )


_FIELD_LIST_CAP = 12


def field_hint(type_name: str, bad_fields: list[str]) -> str:
    """無効なプロパティフィールド向けのヒント文字列を生成する。

    型によっては有効フィールドが60件を超える(Cue/WaveformRegion等)ため、
    まず typo に対する近似候補を示し、一覧は先頭 _FIELD_LIST_CAP 件までに
    切り詰める(残数は件数で伝える)。UNAVAILABLE_FIELDS に登録された
    代替経路の案内があればそれも連結する。
    """
    known = KNOWN_FIELDS.get(type_name, KNOWN_FIELDS["*"])
    parts = []

    candidates = []
    for field in bad_fields:
        for c in suggest(field, known):
            if c not in candidates:
                candidates.append(c)
    if candidates:
        parts.append(f"近い候補: {', '.join(candidates)}")

    shown = known[:_FIELD_LIST_CAP]
    listing = f"'{type_name}' の既知の有効フィールド: {', '.join(shown)}"
    if len(known) > _FIELD_LIST_CAP:
        listing += f" ほか{len(known) - _FIELD_LIST_CAP}件"
    parts.append(listing)

    unavailable = UNAVAILABLE_FIELDS.get(type_name, {})
    for field in bad_fields:
        if field in unavailable:
            parts.append(f"'{field}' は取得できません。{unavailable[field]}")

    return "。".join(parts)


def graph_type_hint(bad_value: str) -> str:
    """無効な graph_type 向けのヒント文字列を生成する(全件ダンプはしない)。"""
    candidates = suggest(bad_value, GRAPH_TYPES)
    if candidates:
        return f"'{bad_value}' は利用できません。近い候補: {', '.join(candidates)}"
    return (
        f"'{bad_value}' は利用できません。代表的な値: Volume, Pitch, Priority, "
        "PanAngle, PanVolume, BusSendLevel1〜8, AisacControl0〜15。"
        "全43種はCRI公式のオブジェクトリファレンス"
        "(criatom_tools_atomcraft_api_refobject.html)の"
        "「AISACグラフ・オートメーション…の種類と名前」節を参照してください。"
    )


def bus_effect_hint(bad_value: str) -> str:
    """無効なバスエフェクト名向けのヒント文字列を生成する(全件ダンプはしない)。"""
    candidates = suggest(bad_value, BUS_EFFECT_TYPES)
    if candidates:
        return f"'{bad_value}' は見つかりません。近い候補: {', '.join(candidates)}"
    return (
        f"'{bad_value}' は見つかりません。代表的な値: Reverb, Delay, Echo, Chorus, "
        "Flanger, Distortion, BiquadFilter, BandpassFilter, 3BandEQ。"
        "全21種はCRI公式のオブジェクトリファレンスの「バスエフェクトの種類と名前」節を"
        "参照してください(なお対象バスに未装着の場合も同じエラーになります)。"
    )
