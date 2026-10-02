# Installation guide

Target environment: **Home Assistant OS / Supervised**, installed via **HACS
as a custom repository**. These steps assume you already have
[HACS](https://hacs.xyz) installed; if you don't, install HACS itself first
(Settings → Add-ons... no - HACS is a separate install, see hacs.xyz/docs/setup/download).

## 1. The repository

This project is published at
[github.com/pdelim73/ha-goe-charger](https://github.com/pdelim73/ha-goe-charger) -
nothing to do here, it's already there.

<details>
<summary>Reference: how it got there (for recreating this setup elsewhere)</summary>

```bash
cd claude-Go-e-charger
git remote add origin https://github.com/pdelim73/ha-goe-charger.git
git push -u origin main
```

If GitHub's "Add a README file" option was checked when the repo was
created, the remote already contains one throwaway commit and the first
`git push` is rejected ("fetch first") - rebase the real commits on top of
it rather than force-pushing:

```bash
git fetch origin
git rebase origin/main
# resolve the README.md conflict by keeping the real README, then:
git add README.md
git rebase --continue
git push -u origin main
```
</details>

## 2. Add it to HACS as a custom repository

1. In Home Assistant, open **HACS** in the sidebar.
2. Click the **⋮** (three-dot) menu in the top right → **Custom repositories**.
3. Paste the repo URL: `https://github.com/pdelim73/ha-goe-charger`
4. Set **Type** to **Integration**.
5. Click **Add**.
6. Find "**go-e Charger Gemini (Read-Only)**" in HACS (search for it, or
   look under the custom repository you just added) and click **Download**.
7. **Restart Home Assistant** (Settings → System → Restart) - required for a
   newly installed `custom_components` integration to be picked up.

## 3. Add the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for "**go-e Charger Gemini**".
3. Enter the charger's local IP address, e.g. `<charger IP address>` -
   and optionally a friendly name.
4. Submit. Home Assistant performs a single read-only status request to
   confirm the charger is reachable; if it succeeds, the integration and its
   device/entities are created immediately.

If you get a "**Could not reach the charger**" error:
- Confirm the IP address is still correct (check your router's DHCP leases
  or the charger's display) - consider giving the charger a DHCP reservation
  so this doesn't change later.
- Confirm the go-e app's **HTTP API** toggle is still enabled (it already is,
  since evcc depends on it - but worth a check under the charger's settings
  in the go-e app if this ever changes).
- Confirm Home Assistant and the charger are on the same local network/VLAN
  and nothing (e.g. client/AP isolation, a firewall rule) blocks port 80
  between them.

## 4. Optional: adjust the poll interval

Settings → Devices & Services → go-e Charger Gemini → **Configure**. Default
is 30 seconds; the field accepts 15-300 seconds. There is no reason to poll
faster than evcc's own default cadence (30s) - see
[`docs/technical-design.md`](technical-design.md) for why.

## 5. What you'll see

One device ("go-e Charger" or whatever name you gave it, model "Gemini
(11 kW / 16 A)") with ~26 sensor entities and 5 binary sensor entities, most
enabled by default. A handful of secondary/diagnostic ones (individual phase
voltages/currents/powers, serial number, lock-mode detail, RFID transaction,
grid frequency, energy data source) are created **disabled** to keep the
default entity list focused - enable any of them from the entity's settings
(gear icon → "Enabled") if you want them.

## Updating later

Whenever a fix or change is committed and pushed to the GitHub repo, get it
into your running Home Assistant like this - no reconfiguration needed,
existing entities and their history carry over unchanged:

1. **HACS → Integrations** (or search) → open **go-e Charger Gemini
   (Read-Only)**.
2. If HACS shows an **Update** badge, click it and update.
   - This repo has no GitHub Releases/version tags, so HACS tracks it by
     latest commit rather than a version number and may not always surface
     an automatic badge. If you don't see one: open the integration, click
     the **⋮** menu → **Redownload** - this pulls whatever is currently on
     `main` regardless of version detection.
3. **Restart Home Assistant** (Settings → System → Restart) - required,
   since Python files under `custom_components/` only reload on a full
   restart, not automatically.
4. Check the affected entities after restart - corrected values should
   appear on the next poll (within the configured scan interval). Past,
   already-recorded history isn't rewritten, only cosmetic.
5. Optionally confirm the installed version: **Settings → System → Repairs →
   ⋮ → System information**, under *Custom integrations*. It should match
   the `version` in `manifest.json` on GitHub. HACS itself shows a commit ID
   rather than this number, since the repo has no releases. Version scheme
   and history: [technical design §7](technical-design.md#7-versioning).

## Uninstalling

Settings → Devices & Services → go-e Charger Gemini → **⋮ → Delete**, then
remove it from HACS (HACS → the integration → **⋮ → Remove**) if you no
longer want it available at all. This never affects evcc or the charger
itself - deleting it just stops Home Assistant from polling it.
