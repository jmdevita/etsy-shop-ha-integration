# Etsy Shop Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.8.3%2B-blue.svg)](https://www.home-assistant.io/)
[![GH-downloads](https://img.shields.io/github/downloads/jmdevita/etsy-shop-ha-integration/total)](https://github.com/jmdevita/etsy-shop-ha-integration/releases)
[![HACS Compatible](https://img.shields.io/badge/HACS-Compatible-green.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration that pulls data from your Etsy shop — listings, orders, and shop stats — and exposes them as sensors you can use in dashboards and automations.

You can connect either with your own Etsy developer credentials (Direct mode) or through a hosted proxy that handles OAuth for you (Proxy mode).

[![Get started in 2 minutes](https://img.shields.io/badge/No_Etsy_developer_account%3F-Get_started_in_2_minutes_%E2%86%92-orange?style=for-the-badge&logo=etsy&logoColor=white)](https://bridge.ctrlprinthome.com/)

Don't want to register an Etsy app or manage OAuth credentials? Sign up at [bridge.ctrlprinthome.com](https://bridge.ctrlprinthome.com/), grab an API key, and jump to *Proxy Service* setup below.

## Installation

### HACS

1. In HACS, open the three-dots menu and choose *Custom repositories*.
2. Add `https://github.com/jmdevita/etsy-shop-ha-integration` as an *Integration*.
3. Install "Etsy Shop" and restart Home Assistant.

### Manual

Copy `custom_components/etsyapp` into your Home Assistant `custom_components` directory and restart.

## Setup

### Direct Etsy API

If you have (or are willing to register for) an Etsy developer account, this is the most straightforward option.

1. Create an app at the [Etsy Developer Dashboard](https://www.etsy.com/developers/your-apps) and note the App Keystring and Shared Secret.
2. In Home Assistant, go to *Settings → Devices & Services → Add Integration* and search for "Etsy Shop".
3. Pick *Direct Etsy API* and paste in the keystring and secret.
4. Authorize the app on Etsy and pick which shop to monitor (if you have more than one).

### Proxy Service

For users who don't want to manage their own Etsy developer credentials. The proxy holds the OAuth client and refreshes tokens on your behalf; your Home Assistant instance authenticates to it with an API key and HMAC secret.

1. Sign up at [bridge.ctrlprinthome.com](https://bridge.ctrlprinthome.com/). Approval is manual but usually quick.
2. Once you receive your credentials, add the integration as above and select *Proxy Service*.
3. Enter the API key and HMAC secret, authorize with Etsy, and pick a shop.

## Naming

Each integration entry is named `ShopName (ShopID) - Direct` or `ShopName (ShopID) - Proxy` (for example, `TestEtsyShop (56636211) - Direct`). The device itself uses just the shop name. This keeps things readable when you're running multiple shops or both connection modes side by side.

## Sensors

| Sensor | State | Attributes |
| --- | --- | --- |
| Etsy Shop Info | Shop name | Shop ID, currency, creation date, announcement, sale message |
| Etsy Active Listings | Active listing count | Recent listings, total views, total favorites |
| Etsy Recent Orders | Recent transaction count | Transaction details, recent revenue, buyer info |
| Etsy Last Order | Last order quantity | Item title, price, variations, buyer info |
| Etsy Shop Statistics | Total sales count | Active listings, views, favorites, revenue, ratings |

## Sample dashboard cards

The five sensors render as plain tiles by default, but the rich attribute data can be pulled into a polished overview using only built-in Lovelace cards — no HACS, no custom-card dependencies.

Two ready-to-use examples live in [`examples/`](./examples):

- **[`examples/dashboard-card.yaml`](./examples/dashboard-card.yaml)** — full overview: shop name, recent revenue, average rating, and a recent-sales feed with compact relative timestamps. Built as a `vertical-stack` of markdown cards.
- **[`examples/glance-card.yaml`](./examples/glance-card.yaml)** — compact alternative showing just the three headline numbers as a glance row.

To use either: open the file, copy its contents, then in Home Assistant go to **Edit Dashboard → Add Card → Manual** and paste.

## Services

- `etsyapp.refresh_data` — force a poll of the Etsy API.
- `etsyapp.get_shop_stats` — return detailed shop statistics, with optional filtering for listings and transactions.

## Options

After setup you can adjust:

- Listings display limit (1–25)
- Transactions display limit (1–25)
- Stock threshold for the low-stock trigger (1–100)
- Update interval (60–3600 seconds, Direct mode only)

## Device Triggers

The integration registers three device triggers for use in automations:

- `new_order` — fires when a new order is detected
- `new_review` — fires on a new review
- `low_stock` — fires when a listing drops below the configured stock threshold

Example:

```yaml
automation:
  - alias: Notify on new Etsy order
    trigger:
      - platform: device
        device_id: YOUR_DEVICE_ID
        domain: etsyapp
        type: new_order
    action:
      - service: notify.mobile_app
        data:
          message: You have a new Etsy order!
```

## Requirements

- Home Assistant 2025.8.3 or newer (needed for PKCE OAuth2 support)
- An Etsy seller account with an active shop
- Either an Etsy developer account (Direct mode) or proxy credentials (Proxy mode)

## Acknowledgements

PKCE support in Home Assistant's OAuth2 framework comes from [@svrooij's work in core#139509](https://github.com/home-assistant/core/pull/139509), which this integration relies on.

## Support

Bug reports and feature requests go in the [issue tracker](https://github.com/jmdevita/etsy-shop-ha-integration/issues).

## License

MIT. See [LICENSE](LICENSE).

---

This integration is not affiliated with or endorsed by Etsy, Inc.
