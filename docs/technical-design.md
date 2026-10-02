# Technical design

## 1. Why local HTTP polling on API v2, not WebSocket, MQTT, or the cloud

go-e's Gemini-generation chargers (hardware "V4"/"V5") speak the **API v2**
local HTTP interface (`goecharger/go-eCharger-API-v2`). Four transports were
considered:

| Transport | Verdict | Why |
|---|---|---|
| **Local HTTP GET `/api/status?filter=...`** | **Chosen** | Stateless, no auth beyond the HTTP API toggle already enabled (evcc depends on it), no config change on the charger, no persistent connection to manage or leak. |
| Local WebSocket (`ws://<host>/ws`) | Rejected | Requires **setting a device password** via the go-e app first - a device configuration change, which conflicts with "no adverse effect on the existing setup". The `marq24/ha-goecharger-api2` README also documents a real race condition between the go-e mobile app and a WebSocket integration client during firmware updates - exactly the kind of interference this project must avoid. |
| MQTT (`mqtt-en.md`, used by `syssi/homeassistant-goecharger-mqtt`) | Rejected | Requires configuring the charger to connect to an MQTT broker (`mcu` config key) - again a device configuration change, plus a broker dependency this integration shouldn't require. |
| Cloud API (`api.go-e.co`) | Rejected | Needs a go-e cloud account/token, adds internet dependency and cloud-side rate limits (documented ~25,000 req/month fair-use limit) for something that's one hop away on the LAN. Local-only is more reliable and more private. |

Local filtered HTTP GET is also exactly what **evcc itself uses** (see §2),
which is the strongest possible evidence that it's a safe, low-risk choice
for a second, independent reader.

## 2. Why this cannot interfere with evcc

evcc's own go-e driver (`charger/go-e/api.go` in `evcc-io/evcc`) was read
directly to answer this, rather than assuming:

- evcc detects API v2 once at startup with `GET /api/status?filter=alw` and,
  from then on, polls with `GET /api/status?filter=alw,car,eto,nrg,wh,trx,cards,modelStatus`
  - the same endpoint, same query style, this integration uses.
- evcc's **only** write calls are `GET /api/set?frc=<0|1|2>` (enable/disable),
  `GET /api/set?amp=<n>` (max current), and `GET /api/set?psm=<n>` (phase
  switching). This integration never calls `/api/set` at all, for any key -
  reads and writes are different endpoints on the charger's HTTP server, so
  there is no shared state or read-modify-write cycle to race.
- There is **no session, cookie, token, or lock** anywhere in evcc's client -
  every call is an independent, short-lived HTTP GET over a standard
  `net/http` client. evcc's own 1-second result cache is local to evcc's
  process and has no effect on the device or any other client.
- evcc's default control-loop interval is **30 seconds**
  (`evcc.dist.yaml`: *"Interval <30s can lead to unexpected behavior"*), so
  this integration defaults to the same 30-second cadence rather than
  polling more aggressively.
- The one documented real-world risk (from evcc's own FAQ) is **some
  wallboxes' embedded web servers limiting concurrent TCP connections** -
  not a go-e-specific issue, and mitigated here by keeping every request
  short-lived (HA's default `aiohttp` client session, no long-poll/keep-open
  connections) and always using `filter=` to keep each request small, per
  go-e's own guidance that unfiltered `/api/status` calls cause "higher
  system load".

**Net effect:** this integration is architecturally incapable of writing to
the charger (no code path calls `/api/set`), and its read traffic is a
smaller, less frequent version of exactly what evcc already does safely
today.

## 3. Architecture

```
config_flow.py  --(one-time validation GET)-->  api.py --> charger
     |
     v
__init__.py creates GoeDataUpdateCoordinator (coordinator.py)
     |
     v  (single filtered GET every scan_interval seconds)
   api.py --> charger  /api/status?filter=<STATUS_KEYS>
     |
     v
 coordinator.data (dict)
     |
     +--> sensor.py       (entity.py: shared device_info)
     +--> binary_sensor.py
```

- **`api.py`** - the only module that ever opens a socket to the charger.
  One method, `async_get_status(filter_keys)`, one HTTP verb (GET), a 10s
  timeout, defensive error handling (`GoeApiError`).
- **`coordinator.py`** - a standard HA `DataUpdateCoordinator`. All entities
  read from `coordinator.data`; nothing polls independently, so however many
  entities exist, exactly one HTTP request happens per cycle.
- **`sensor.py` / `binary_sensor.py`** - data-driven: each entity is a
  `(key, translation_key, device_class, ..., value_fn)` description, where
  `value_fn` extracts and transforms one field out of `coordinator.data`.
  Adding a new read-only field later is a one-line addition, not a new class.
- **No `switch.py`, `number.py`, `select.py`, or `button.py`** exist in this
  integration at all - not "present but disabled", genuinely absent. That's
  a stronger read-only guarantee than "an entity you could accidentally
  re-enable".
- **Defensive parsing everywhere**: every `value_fn` uses `.get()` and
  tolerates `None`; unmapped enum codes render as `unknown_code_<n>` instead
  of raising (see `const.py: lookup()`). Firmware 60.x is under active
  development (the 60.5 changelog itself adds new keys), so the parser is
  built to degrade gracefully rather than assume a fixed schema.
- **`null` doesn't always mean "unavailable" - it's checked per field**:
  most optional fields (`pgrid`/`ppv`/`pakku`, `dsrc`, `car`) genuinely mean
  "no data" when null, so they correctly surface as HA's `unknown` state.
  But `err` is documented as null meaning **"no error"** - a defined,
  common, healthy state - not "unavailable". An earlier version of this
  integration treated `err: null` as unknown, which made the `error` sensor
  and `problem` binary sensor show "unknown" during all normal, error-free
  operation (i.e. almost all the time) instead of "none"/off. Caught by
  running every `value_fn` against a synthetic status payload before
  shipping (see the last bullet below) - fixed in `sensor.py`/
  `binary_sensor.py` by treating `err: null` as code 0 explicitly.

## 4. Entity reference

All values come from a single `GET /api/status?filter=...` call. Key
scaling notes: the legacy `nrg` array packs U (V, direct) and, per the
`goecharger/go-eCharger-API-v1` spec, I (0.1 A) and P (0.1 kW per phase,
0.01 kW total). **None of that scaling holds on a real Gemini V4 (firmware
60.5)** - two separate user reports showed charging/phase power reading
10x-100x too high and phase current reading 10x too low; reverse-engineering
both confirmed every value in this array already arrives in plain native
units (W, A) on this hardware/firmware, not the v1-era scaled integers.
Fixed by using a scale factor of 1 throughout. Voltage was always documented
as direct volts, so it was correct from the start.

| Entity | Source key(s) | Notes |
|---|---|---|
| Charging state | `car` | enum: unknown/idle/charging/wait_car/complete/error/initializing |
| Charging status reason | `modelStatus` | ~40-value enum, e.g. `charging_because_pv_surplus` |
| Error | `err` | enum, `none` when no error |
| Session energy | `wh` | Wh → kWh |
| Total energy | `eto` | Wh → kWh, lifetime |
| Charging power | `nrg[11]` | already in W (see scaling note above) |
| Power/Voltage/Current L1-L3 | `nrg[...]` | disabled by default (diagnostic detail) |
| Active phases | `pnp` | 1 or 3 |
| Allowed charging current | `acu` | what the car is currently allowed to draw - informational |
| Max current limit | `ama` | charger's configured ceiling - informational, diagnostic |
| Energy logic mode | `lmo` | default / awattar / next_trip |
| Grid/PV/battery power | `pgrid`/`ppv`/`pakku` | only populated if an energy-management source is configured; otherwise `unknown` |
| Energy data source | `dsrc` | diagnostic, disabled by default |
| Cable lock status | `cus` | enum |
| Lock mode / Lock feedback | `lck` / `ffb` | diagnostic, disabled by default |
| RFID transaction | `trx` | `no_transaction` / `no_card` / `card_<n>`, disabled by default |
| Grid frequency | `fhz` | diagnostic, disabled by default |
| Wi-Fi signal | `rssi` | diagnostic |
| Firmware version, Serial number, Device variant | `fwv`, `sse`, `var` | diagnostic |
| **Binary:** Car connected | derived from `car` | best-effort - see caveat below |
| **Binary:** Charging | `car == charging` | |
| **Binary:** Charging allowed | `alw` | |
| **Binary:** PV surplus mode | `fup` | disabled by default |
| **Binary:** Problem | `err not in (null, 0)` | `device_class: problem`; null/0 both mean "no error" (off), not unknown |

**Caveat on "Car connected":** go-e's local API has no dedicated "cable/car
plugged in" boolean. This binary sensor infers it from the `car` state
machine (`charging`/`wait_car`/`complete` → connected, `idle` → not
connected, everything else → unknown) - a reasonable best-effort reading
based on the documented state names, but not an officially documented
field. If it doesn't match your observed behavior, it's worth flagging so
the mapping can be corrected against your unit's actual behavior.

## 5. Comparison with existing community integrations

Three existing projects were read in detail before designing this one:

| | `cathiele/homeassistant-goecharger` | `marq24/ha-goecharger-api2` | `syssi/homeassistant-goecharger-mqtt` | **This integration** |
|---|---|---|---|---|
| Protocol | API v1 (legacy) | API v2 local HTTP + optional WebSocket | API v2 over MQTT | API v2 local HTTP only |
| Maintenance | Stale (~15 months, open "is this maintained?" issue, 36 open issues) | Active | Active | N/A (new) |
| Gemini support | Unverified, V1-only design | Used in the wild against Gemini, undocumented | Explicitly documented and tested | Explicitly targets Gemini V4 |
| Write capability | Switches + services (start/stop, limits) | Switches, numbers, selects, buttons, custom services | Switches, numbers, selects, buttons, custom services | **None - no write platforms exist in the codebase at all** |
| Extra infra required | None | None (WS needs a device password) | MQTT broker | None |
| Known evcc friction | Not documented | Yes - open issues about evcc/OCPP mutual exclusion and out-of-sync writes when both control the charger | Not documented | N/A - read-only, cannot conflict with a controller by construction |

**What this design deliberately does differently:** the three existing
projects are general-purpose integrations meant to let Home Assistant *also
control* the charger - which is exactly the failure mode (`marq24`'s issues
#78/#143) to avoid when evcc is already the controller. This integration
narrows scope on purpose: no control platforms, no MQTT/broker dependency,
no WebSocket/password requirement, defensive parsing for a firmware that's
still actively gaining new keys. `cathiele`'s project is the clearest
cautionary example for the *documentation and maintenance* side - its
README still describes API v1 while the shipped code has since added a
config flow, i.e. docs and code drifted apart; this project's docs
(`docs/`) describe the exact behavior of the shipped code as of this
version, not an aspirational or historical version of it.

## 6. Known limitations / things to watch

- The `modelStatus` and `err` enum tables were sourced from go-e's published
  firmware-60.4 reference (closest to this device's 60.5 beta) - if a future
  firmware update introduces new codes, they'll surface as
  `unknown_code_<n>` rather than breaking the sensor; worth reporting so the
  lookup table can be extended.
- `pgrid`/`ppv`/`pakku` depend on the charger having an energy-management/PV
  data source configured; if none is set up, these sensors will simply read
  `unknown` rather than `0`, which is the more accurate representation of
  "no data available" versus "measured zero".
- **Fixed:** `charging_power`, `power_l1`/`l2`/`l3` and `current_l1`/`l2`/`l3`
  originally applied the go-e API v1 spec's legacy scaling (0.01 kW / 0.1 kW
  / 0.1 A steps) to the `nrg` array's fields, which was correct for older
  HOME/HOME+ hardware but not for this Gemini V4 on firmware 60.5 - real
  readings showed power values 10x-100x too high and a current reading 10x
  too low, confirming every `nrg` sub-field already arrives in plain native
  units (W, A) on this firmware. All now use a scale factor of 1.
- No local HA instance was available to run this integration live during
  development, so verification stopped one level short of an actual running
  Home Assistant: Python syntax checks, every module successfully imported
  against a real installed `homeassistant` package (2025.1.4, in a scratch
  venv) to catch API/import mistakes, every `sensor.py`/`binary_sensor.py`
  `value_fn` run against a synthetic status payload (normal operation, an
  active error, and a "no chargectrl connection" case) to check actual
  output values/states rather than just "it doesn't crash" - this is what
  caught the `err`/null bug described above - and the `hassfest` GitHub
  Actions check (validates the integration against Home Assistant's own
  manifest/structure schema). The separate HACS-store-submission checklist
  (`hacs/action`) was tried too, but dropped from CI - it only matters for
  listing in HACS's default store, which isn't the goal here; installing via
  a HACS *custom repository* never runs it. End-to-end confirmation that
  entities populate correctly happens
  on your own Home Assistant instance after installation - see
  [`installation.md`](installation.md).

## 7. Versioning

The integration's version is the `version` field in
[`custom_components/goe_gemini/manifest.json`](../custom_components/goe_gemini/manifest.json),
following semantic versioning (`MAJOR.MINOR.PATCH`):

| Bump | When | Example |
|---|---|---|
| PATCH | Bug fix, no change to entities or setup | `nrg` scaling fix (1.0.0 → 1.0.1) |
| MINOR | New read-only entity, option or diagnostic, nothing existing changes | Adding a new sensor |
| MAJOR | Breaking change: entity/unique IDs renamed or removed, or setup must be redone | Changing the unique_id scheme |

- Bump the version in the same commit as the code change, before pushing.
  Changes that only touch docs or CI don't bump it - the version describes
  the integration code under `custom_components/`.
- Every version is published as a **GitHub Release** tagged `vX.Y.Z`,
  matching the manifest. HACS installs the latest release (not the latest
  commit on `main`), shows its version number, and offers an **Update**
  when a newer release is published. A code change therefore only reaches
  HACS once it's released; docs-only commits don't need a release.
- Home Assistant shows the installed version under **Settings → System →
  Repairs → ⋮ → System information**, in the *Custom integrations* list.

### Release process

1. Change the code, bump `version` in `manifest.json`, add a row to the
   version history below, commit and push to `main`.
2. Publish the release from the pushed commit:
   ```bash
   gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes "<the version history row>"
   ```
   (or on GitHub: **Releases → Draft a new release**, new tag `vX.Y.Z` on `main`).
3. In Home Assistant, HACS shows the update; install it and restart.

### Version history

| Version | Changes |
|---|---|
| 1.0.1 | Fixed `charging_power`, `power_l1`-`l3` (10x-100x too high) and `current_l1`-`l3` (10x too low): the `nrg` array arrives in native W/A on Gemini V4 firmware 60.5, not the v1-spec scaled units. |
| 1.0.0 | Initial release: read-only local API v2 polling, ~26 sensors + 5 binary sensors, UI config flow and options flow (poll interval), diagnostics with the serial redacted. |
