# Petlibro API Reference

Base URL: `https://api.us.petlibro.com`

All endpoints require authentication via a `token` header obtained from `/member/auth/login`.

## Authentication

### POST /member/auth/login

Login and obtain an authentication token.

**Request:**
```json
{
  "appId": 1,
  "appSn": "c35772530d1041699c87fe62348507a8",
  "country": "US",
  "email": "user@example.com",
  "password": "<md5 hash of password>",
  "phoneBrand": "",
  "phoneSystemVersion": "",
  "timezone": "America/Chicago",
  "thirdId": null,
  "type": null
}
```

**Response:**
```json
{
  "code": 0,
  "msg": null,
  "data": {
    "token": "abc123..."
  }
}
```

**Error codes:**
- `1009`: NOT_YET_LOGIN (token expired, triggers auto re-login)

## Device Management

### POST /device/device/list

List all devices on the account.

**Request:** `{}`

**Response:** Array of device objects:
```json
[
  {
    "deviceSn": "WF0200319D4B3069K",
    "productName": "Dockstream Smart Fountain",
    "productIdentifier": "PLWF105",
    "name": "Kitchen Fountain",
    "mac": "AA:BB:CC:DD:EE:FF",
    "softwareVersion": "1.2.3",
    "hardwareVersion": "1.0",
    "online": true,
    "deviceShareState": 3,
    "shareId": null,
    "enableFeedingPlan": false
  }
]
```

**Known productName values:**
- `"Air Smart Feeder"` → `AirSmartFeeder`
- `"Granary Smart Feeder"` → `GranarySmartFeeder`
- `"Granary Smart Camera Feeder"` → `GranarySmartCameraFeeder`
- `"Granary 2 Vision"` → `Granary2VisionFeeder` (PLAF205)
- `"One RFID Smart Feeder"` → `OneRFIDSmartFeeder`
- `"Polar Wet Food Feeder"` → `PolarWetFoodFeeder`
- `"Dockstream Smart Fountain"` → `DockstreamSmartFountain`
- `"Dockstream Smart RFID Fountain"` → `DockstreamSmartRFIDFountain`
- `"Dockstream 2 Smart Cordless Fountain"` → `Dockstream2SmartCordlessFountain`
- `"Dockstream 2 Smart Fountain"` → `Dockstream2SmartFountain`
- `"Space Smart Feeder"` → `SpaceSmartFeeder`
- `"Luma Smart Litter Box"` → `LumaSmartLitterBox`

## Device Info Endpoints

All endpoints below take a JSON body with `"id": "<deviceSn>"` and `"deviceSn": "<deviceSn>"`.

### POST /device/device/baseInfo

Basic device information.

**Request:** `{"id": "<deviceSn>", "deviceSn": "<deviceSn>"}`

**Response fields:** device name, MAC, software/hardware version, online status, battery state, enableFeedingPlan, etc.

### POST /device/device/realInfo

Real-time device state.

**Response fields (varies by device type):**
| Field | Type | Description |
|---|---|---|
| `online` | bool | Device connectivity |
| `wifiSsid` | string | Connected Wi-Fi network |
| `wifiRssi` | int | Wi-Fi signal strength (dBm) |
| `batteryState` | string | `"low"`, `"normal"`, etc. |
| `batteryDisplayType` | int/string | Battery percentage |
| `electricQuantity` | float | Battery level % |
| `unitType` | int | Measurement unit (1=cup, 2=oz, 3=g, 4=mL) |
| `runningState` | string | `"IDLE"` or `"RUNNING"` |
| `enableFeedingPlan` | bool | Feeding plan enabled |
| `surplusGrain` | bool | Food available |
| `grainOutletState` | bool | Outlet open |
| `barnDoorError` | bool | Door obstruction |
| `barnDoorState` | bool | Door position |
| `childLockSwitch` | bool | Child lock |
| `lightSwitch` | bool | Indicator light |
| `soundSwitch` | bool | Sound on/off |
| `vacuumState` | bool | Air pump active |
| `pumpAirState` | bool | Pump state |
| `temperature` | float | Temperature (Celsius) |
| `weight` | float | Water/litter weight (g) |
| `weightPercent` | int | Water level % |
| `useWaterType` | int | Water mode (0=constant, 1=intermittent) |
| `useWaterInterval` | int | Water interval (minutes) |
| `useWaterDuration` | int | Water duration (minutes) |
| `remainingReplacementDays` | int | Filter remaining days |
| `remainingCleaningDays` | int | Cleaning remaining days |
| `changeDesiccantFrequency` | int | Desiccant cycle (days) |
| `closeDoorTimeSec` | int | Auto-close delay |
| `coverCloseSpeed` | string | Lid speed |
| `screenDisplaySwitch` | bool | Display on/off |
| `enableLowBatteryNotice` | bool | Low battery alerts |
| `enablePowerChangeNotice` | bool | Power change alerts |
| `enableReGrainNotice` | bool | Refill alerts |
| `enableSleepMode` | bool | Sleep mode |
| `resolution` | string | Camera resolution |
| `nightVision` | string | Night vision mode |
| `enableVideoRecord` | bool | Video recording |
| `videoRecordSwitch` | bool | Recording toggle |
| `videoRecordMode` | string | Recording mode |
| `powerMode` | int | Power source (1=AC) |
| `powerType` | int | Power type (2=battery, 3=AC) |
| `powerState` | string | `"USING"`, `"CHARGING"`, `"CHARGED"` |

**Additional fields seen on Granary 2 Vision (PLAF205):**
| Field | Type | Description |
|---|---|---|
| `bowlMode` | string | `"SINGLE_BOWL"` or dual-tray mode |
| `leftWarehouseSurplusGrain` | bool | Left grain warehouse has food (dual-tray) |
| `rightWarehouseSurplusGrain` | bool | Right grain warehouse has food (dual-tray) |
| `warehouseSurplusGrain` | string | Combined warehouse status, e.g. `"GOOD"` |
| `cameraAuthInfo` | string | Kalay/TUTK per-device camera auth string |
| `enableHumanDetection` | bool | AI human detection enabled |
| `radarSensingLevel` | string | Radar sensing/trigger level, e.g. `"NearTrigger"` |
| `talkChannelState` | bool | Whether a 2-way talk session is active |
| `detThreshold` / `reidThreshold` | float | AI detection / re-identification confidence thresholds |

Note: `nightVisionMode` and `petDetectionSwitch` are **not** present on `realInfo` for this
model - they only appear in `getAttributeSetting`'s response (see below), unlike
`nightVision`/`enableVideoRecord` on the older Granary Smart Camera Feeder.

### POST /data/data/realInfo

Extended real-time info (fountains, litter boxes).

**Response includes all realInfo fields plus:**
| Field | Type | Description |
|---|---|---|
| `exceptionMessage` | string | Error message (e.g. `"Rotor stuck"`, `"Calibration error"`) |
| `waterStopSwitch` | bool | Fountain water mode |
| `lowWater` | int | Low water threshold (mL) |
| `radarSensingLevel` | string | Radar sensitivity |
| `filterState` | string | Filter condition |
| `cleanState` | string | Cleaning state |
| `matState` | string | Mat condition |
| `doorState` | string | Door state |
| `remainingMatDays` | int | Mat remaining days |
| `deodorizationMode` | string | Deodorization mode |
| `deodorizationModeSwitch` | bool | Deodorization toggle |
| `motionSensitivityLevel` | string | Motion sensitivity |
| `batterySupply8Hours` | bool | Battery capacity |

### POST /device/setting/getAttributeSetting

Device attribute settings.

**Response fields:**
| Field | Type | Description |
|---|---|---|
| `enableSleepMode` | bool | Sleep mode |
| `volume` | int | Sound level (1-100) |
| `enableCamera` | bool | Camera enabled |
| `cameraSwitch` | bool | Camera toggle |
| `cloudVideoRecordSwitch` | bool | Cloud recording |
| `nightVisionMode` | string | Night vision |
| `petDetectionSwitch` | bool | Pet detection |
| `enableHumanDetection` | bool | Human detection |
| `disableHardwareButton` | bool | Button lock |
| `cleanMode` | string | `"AUTO"` or `"MANUAL"` |
| `autoDelaySec` | int | Auto-clean delay |
| `enableSleepMode` | bool | Sleep mode config |

**Additional fields seen on Granary 2 Vision (PLAF205):**
| Field | Type | Description |
|---|---|---|
| `nightVisionMode` | string | Active night vision mode, e.g. `"AUTO_BLACK_WHITE"` (authoritative source - `realInfo.nightVision` is always null on this model) |
| `autoStopFeedSwitch` | bool | Unconfirmed - looked like a Smart Feed toggle but did not change when Smart Feed was toggled in the app. Real Smart Feed state lives in the feeding mode (see below), not here. |
| `autoFeedMaxWeight` | int | Unconfirmed - unrelated to Free Feeding's `freeDailyMaxNum` (see below); meaning not yet verified. |

### POST /device/ota/getUpgrade

Firmware update information.

**Response:**
```json
{
  "jobItemId": 12345,
  "targetVersion": "1.2.4",
  "jobName": "Firmware v1.2.4",
  "upgradeDesc": "Bug fixes and improvements",
  "progress": 0.5
}
```

### POST /device/data/grainStatus

Dry feeder grain/feeding status.

**Response fields:**
| Field | Type | Description |
|---|---|---|
| `todayFeedingTimes` | int | Feedings today |
| `todayFeedingQuantity` | float | Total food dispensed today |
| `todayFeedingQuantities` | array | Per-feeding quantities |
| `todayEatingTimes` | int | Eating sessions (RFID) |
| `petEatingTime` | int | Total eating time (seconds) |
| `surplusGrain` | bool | Food remaining |

### POST /device/device/getDefaultMatrix

Device default configuration matrix.

**Response:** Device-specific configuration values (feed portion sizes, etc.)

## Feeding Plan Endpoints

### POST /device/feedingPlan/todayNew

Today's feeding plan summary.

**Response:**
```json
{
  "allSkipped": false
}
```

### POST /device/feedingPlan/list

List all feeding plans.

**Response:** Array of plan objects:
```json
[
  {
    "id": 1,
    "enable": true,
    "executionTime": "08:00",
    "grainNum": 4,
    "repeatDay": "[1,2,3,4,5,6,7]",
    "timezone": "America/Chicago",
    "label": "Breakfast",
    "enableAudio": false
  }
]
```

### POST /device/feedingPlan/todayNew

Today's feeding plan data...

### POST /device/wetFeedingPlan/wetListV3

Wet food (Polar) feeding plan.

**Response:**
```json
{
  "templateName": "My Schedule",
  "manualFeedId": null,
  "plan": [
    {
      "id": 123,
      "plate": 1,
      "label": "Breakfast",
      "executionStartTime": "08:00",
      "executionEndTime": "08:30"
    }
  ]
}
```

### POST /device/wetFeedingPlan/manualFeedNow

Start manual feeding on a specific plate. Opens the lid.

**Request:** `{"deviceSn": "<sn>", "plate": 1}`

### POST /device/wetFeedingPlan/stopFeedNow

Stop manual feeding. Closes the lid.

**Request:** `{"deviceSn": "<sn>", "feedId": <id>}`

### POST /device/wetFeedingPlan/platePositionChange

Rotate food bowl to next plate.

**Request:** `{"deviceSn": "<sn>"}`

### POST /device/device/getFreeFeedingSetting (Granary 2 Vision)

Free Feeding ("Smart Feed" in the app) settings.

**Request:** `{"id": "<deviceSn>", "deviceSn": "<deviceSn>"}`

**Response:**
```json
{
  "freePerGrainNum": 1,
  "freeDailyMaxNum": 13,
  "freeLeftoverWeight": 3,
  "freeWaitSeconds": 3
}
```

Values are per-device config (e.g. `freeDailyMaxNum` differed between two units on the same
account: 13 vs 10). This endpoint returns settings regardless of which feeding mode is
currently active - it is not itself a signal of whether Free Feeding is enabled.

### POST /device/device/updateFeedingMode (Granary 2 Vision)

Switch the device's active feeding mode. Confirmed via a live network capture of the app.

**Request:**
```json
{
  "deviceSn": "<sn>",
  "mode": "FREE"
}
```

**Known `mode` values:**
| Value | Meaning |
|---|---|
| `FREE` | Free Feeding / Smart Feed - device dispenses automatically based on the Free Feeding settings above |
| `PLAN` | Schedule-based feeding - the device follows `/device/feedingPlan/list` entries |

There is currently no known GET endpoint that reads back the *current* mode; it must be
tracked from the last value written, or inferred (e.g. an empty `feedingPlan/list` combined
with automatic `GRAIN_OUTPUT_SUCCESS` work records tagged `"mode":"{AUTO_MODE}"` suggests `FREE`).

## Water / Fountain Endpoints

### POST /data/deviceDrinkWater/todayDrinkData

Today's drinking data.

**Response:**
```json
{
  "todayTotalMl": 250.0,
  "todayTotalTimes": 12,
  "petEatingTime": 180,
  "avgDrinkDuration": 15,
  "yesterdayTotalMl": 200.0,
  "yesterdayTotalTimes": 10
}
```

### POST /device/device/waterModeSetting

Configure fountain water mode.

**Request:**
```json
{
  "deviceSn": "<sn>",
  "requestId": "<uuid>",
  "useWaterType": 0,
  "useWaterInterval": 60,
  "useWaterDuration": 10,
  "waterStopSwitch": false,
  "sensingWaterDuration": null
}
```

`useWaterType`: 0=constant, 1=intermittent, 2=sensed

### POST /device/setting/updateRadarSetting

Configure radar sensing level.

**Request:** `{"deviceSn": "<sn>", "radarSensingLevel": "NearTrigger"}`

### POST /device/setting/updateLowWaterSetting

Set low water threshold.

**Request:** `{"deviceSn": "<sn>", "lowWater": 650}`

## Litter Box Endpoints

### POST /device/device/execCmdService

Execute a device command.

**Request:** `{"deviceSn": "<sn>", "action": "<action>", "requestId": "<uuid>"}`

**Supported actions:**
| Action | Description |
|---|---|
| `CLEAN` | Start cleaning cycle |
| `STOP_CLEAN` | Stop cleaning |
| `SUSPEND_CLEAN` | Pause cleaning |
| `RESTART_CLEAN` | Resume cleaning |
| `EMPTY` | Empty waste bin |
| `STOP_EMPTY` | Stop emptying |
| `RESTART_EMPTY` | Resume emptying |
| `LEVELING` | Level litter |
| `RESTART_LEVELING` | Resume leveling |
| `VACUUM` | Air purifier on |
| `OPEN_DOOR` | Open door |
| `CLOSE_DOOR` | Close door |
| `STOP` | Stop current action |
| `CANCEL` | Cancel current action |

### POST /device/setting/updateCleanModeSetting

Set clean mode.

**Request:** `{"deviceSn": "<sn>", "cleanMode": "AUTO", "autoDelaySec": 60}`

### POST /device/setting/updateDeodorizationSetting

Set deodorization.

**Request:** `{"deviceSn": "<sn>", "deodorizationMode": "auto", "deodorizationModeSwitch": true}`

## Event Endpoints

### POST /data/event/deviceEventsV2

Recent device events.

**Request:** `{"id": "<deviceSn>"}`

**Response:**
```json
{
  "data": {
    "eventInfos": [
      {
        "eventKey": "MOTION_DETECTED",
        "eventTime": 1689000000000,
        "eventValue": ""
      }
    ]
  }
}
```

**Known event keys:**
| Event Key | Source |
|---|---|
| `VACUUM_FAILED` | SpaceSmartFeeder |
| `GRAIN_OUTLET_BLOCKED_OVERTIME` | SpaceSmartFeeder |
| `FOOD_OUTLET_DOOR_FAILED_CLOSE` | SpaceSmartFeeder |
| `MOTION_DETECTED` | GranarySmartCameraFeeder |
| `SOUND_DETECTED` | GranarySmartCameraFeeder |

### POST /device/workRecord/list

Work/feeding records (past 30 days).

**Request:**
```json
{
  "deviceSn": "<sn>",
  "startTime": 1689000000000,
  "endTime": 1691680000000,
  "size": 25,
  "type": ["GRAIN_OUTPUT_SUCCESS"]
}
```

**Response:** Array of daily records:
```json
[
  {
    "workRecords": [
      {
        "type": "GRAIN_OUTPUT_SUCCESS",
        "recordTime": 1689000000000,
        "actualGrainNum": 4
      }
    ]
  }
]
```

## Pet Endpoints

### POST /device/devicePetRelation/getBoundPets

Get pets bound to a device.

**Request:** `{"deviceSn": "<sn>"}`

**Response:** Array of pet objects with `id`, `name`, `memberId`, etc.

### POST /device/device/wear/wearListV2

Get RFID collar data for pets.

**Request:** `{"deviceSn": "<sn>", "type": 1}`

**Response:**
```json
[
  {
    "id": 45919,
    "petId": 325457,
    "petName": "Marble",
    "rfid": "130033179230917",
    "enable": true,
    "todayDrinkTimes": 5,
    "todayDrinkAmount": 120.0,
    "todayDrinkDuration": 60,
    "petBindDeviceTime": 1748952241855,
    "collarBindDeviceTime": 1748952241855
  }
]
```

## Control / Setting Endpoints

All endpoints below take a JSON body with `"deviceSn": "<serial>"` plus parameters.

### POST /device/setting/updateFeedingPlanSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateChildLockSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateLightEnableSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateLightSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateSoundEnableSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateSoundSwitch
**Body:** `{"deviceSn": "<sn>", "enable": true}`

### POST /device/setting/updateVolumeSetting
**Body:** `{"deviceSn": "<sn>", "volume": 50}`

### POST /device/setting/updateCoverSetting
**Body:** `{"deviceSn": "<sn>", "coverOpenMode": null, "coverCloseSpeed": "fast", "closeDoorTimeSec": 5}`

### POST /device/device/maintenanceFrequencySetting
**Body:** `{"deviceSn": "<sn>", "key": "DESICCANT", "frequency": 30, "requestId": "<uuid>", "timeout": 5000}`

**Keys:** `DESICCANT`, `MACHINE_CLEANING`, `FILTER_ELEMENT`

### POST /device/setting/baseInfo
**Body:** `{"id": "<sn>"}` - Get base info

### POST /device/device/vacuum
**Body:** `{"deviceSn": "<sn>", "vacuumMode": "auto", "requestId": "<uuid>"}`

## Camera Credential Endpoints

### POST /member/third/tutk/info

Kalay/TUTK P2P camera credentials, account-scoped (not per-device despite taking a serial
in the request). This is a credential layer only - it does not provide a video stream by
itself. An external Kalay/TUTK-compatible client would need these plus the per-device
`cameraAuthInfo` from `realInfo` to establish its own P2P session. See PetLibro/petlibro#269
(upstream, unmerged as of this writing) for prior art exposing these attributes without
attempting to build a full camera platform.

**Request:** `{"id": "<deviceSn>", "deviceSn": "<deviceSn>"}`

**Response:**
```json
{
  "userToken": "RsOpmYHrliyPvA6p2BOa",
  "appTutkUrl": "https://us-vsaasapi-tutk.kalayservice.com/vsaas/api/v1/be/"
}
```

## Member / Account Endpoints

### POST /member/auth/logout

End the session.

### POST /member/info (not explicitly listed but used)

Get member/account information. Response includes email, username, nickname, gender, region, feedUnitType, waterUnitType, weightUnitType, subscription status, etc.
