# OdoDash for Home Assistant

Brings your [OdoDash](https://github.com/moshiur-hridoy/OdoDash) vehicles into
Home Assistant. Each vehicle becomes a device with sensors for its odometer,
consumption, costs and last fill-up, plus problem sensors for due maintenance,
expiring documents and reminders. A service logs fill-ups from Home Assistant.
Everything is set up from the UI; no YAML.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=moshiur-hridoy&repository=ododash-homeassistant&category=integration)

## Requirements

- An OdoDash version that serves `GET /api/ha/overview` (the first release
  after 0.50.0).
- Home Assistant 2024.12 or newer, with [HACS](https://hacs.xyz).
- Home Assistant must be able to reach OdoDash over the network.

## Install

1. Click the button above, or in HACS open the menu → **Custom repositories**,
   add `https://github.com/moshiur-hridoy/ododash-homeassistant` with type
   **Integration**, then download **OdoDash**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → OdoDash.**

## Set up

In OdoDash open **Settings → Integrations → Home Assistant** and create a Home
Assistant key. Then fill in the form in Home Assistant:

| Field | What to enter |
|---|---|
| Server address | The address Home Assistant can reach OdoDash on, for example `http://192.168.1.10:5050`. Behind a reverse proxy, use the proxy's address. |
| Home Assistant key | The key from OdoDash (starts with `odoha_`). An older account API key (`odo_`) also works, but the Home Assistant key can only read data and log fuel, so prefer it. |
| Verify SSL certificate | Leave on unless OdoDash uses a self-signed certificate. |

**Options:** update interval in minutes (default 15, minimum 5). OdoDash data
only changes when someone logs something, so polling faster gains nothing.

## Entities

One device per vehicle. A sensor is created only when OdoDash has a value for
it; the charging sensors only for electric and hybrid vehicles.

| Entity | Notes |
|---|---|
| Odometer | km or mi (converted to your Home Assistant unit system); engine hours for hour-metered vehicles |
| Average consumption | L/100km or mpg, as OdoDash calculates it |
| Total cost, Fuel cost, Expenses | all-time, in your OdoDash currency |
| Cost last 30 days | fuel + expenses |
| Last fill, Last fill volume | date and volume of the latest fill-up |
| Last charge energy, Last charge level | kWh added and end state of charge of the latest charging session |
| Alerts | number of alerts for this vehicle |
| Maintenance due, Document expiring, Reminder due | binary problem sensors; the matching alerts are in the `alerts` attribute |

An **OdoDash** device holds **Total alerts** and an **Online** connectivity sensor.

Imperial (UK) gallons have no Home Assistant unit, so a volume in `gal` is
shown as `imp gal` without a device class rather than relabelled as US gallons.

## Log a fill-up

```yaml
action: ododash.add_fuel
data:
  device_id: 0123456789abcdef0123456789abcdef  # pick the vehicle in the UI
  odometer: 45210
  volume: 38.5
  price_per_unit: 1.48
  # total_cost: 56.98   # optional, defaults to volume × price
  # date: "2026-11-20"  # optional, defaults to today
  is_full_tank: true
  notes: Logged from Home Assistant
```

The vehicle's sensors refresh right after the fill-up is saved.

## Troubleshooting

- **"OdoDash rejected the key" / a re-authentication notice:** the key was
  revoked or regenerated. Create a new Home Assistant key in OdoDash and paste
  it into the notice.
- **"Cannot reach OdoDash":** open the server address from a browser on the
  Home Assistant machine. Behind Caddy or another proxy, the address OdoDash
  shows in Settings may be its internal one; use the address Home Assistant
  can actually reach.
- **Permission denied when logging fuel:** the OdoDash account's role is
  viewer. Fill-ups need the editor or contributor role.
- **Diagnostics:** the integration's diagnostics download redacts the key,
  the server address, the username and registrations.

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

## Licence

MIT
