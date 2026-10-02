# go-e Charger Gemini (Read-Only) for Home Assistant

A read-only Home Assistant custom integration for the **go-e Charger Gemini V4**
(and other V4/V5 "Gemini" generation go-e chargers speaking local API v2).

It exposes charging state, energy, power/voltage/current per phase, PV-surplus
info, cable lock status and diagnostics as sensors and binary sensors - and
**nothing else**. There are no switches, number inputs, selects or buttons,
and the integration never calls the charger's write endpoint (`/api/set`).
That makes it safe to install alongside an existing controller such as
[evcc](https://github.com/evcc-io/evcc), which keeps full control of
charging - see [`docs/technical-design.md`](docs/technical-design.md) for the
detailed reasoning and the evidence behind that claim.

## Documentation

- [Installation guide](docs/installation.md) - HACS custom-repository setup
  and first-time configuration on Home Assistant OS/Supervised.
- [Technical design](docs/technical-design.md) - API choice, architecture,
  full entity reference, and a comparison against existing community go-e
  integrations.

## At a glance

| | |
|---|---|
| Protocol | go-e local API v2, `GET /api/status?filter=...` only |
| Auth | None (uses the same local HTTP API evcc already talks to) |
| Polling | Every 30s by default (configurable, 15-300s) |
| Writes | None, ever |
| Entities | ~26 sensors + 5 binary sensors, all read-only |
| Distribution | HACS custom repository |
| Versioning | Semantic versioning in `manifest.json`, published as GitHub Releases (`vX.Y.Z`) - see the [version history](docs/technical-design.md#7-versioning) |

## License

MIT - see [LICENSE](LICENSE).
