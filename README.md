# Etsy Shop Home Assistant Integration

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.8.3%2B-blue.svg)](https://www.home-assistant.io/)
[![HACS Compatible](https://img.shields.io/badge/HACS-Compatible-green.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Monitor your Etsy shop metrics directly in Home Assistant with regular updates on listings, orders, and shop statistics.

## ✨ Features

- 📊 **Real-time Shop Monitoring**: Track sales, listings, and transactions
- 🔐 **Secure OAuth2 Authentication**: OAuth2 with PKCE support (Big thanks to @svrooij for implementing [this feature](https://github.com/home-assistant/core/pull/139509))
- 🏪 **Multi-Shop Support**: Monitor multiple Etsy shops from one integration
- 🎯 **Dual Connection Modes**: Direct API (with dev key) or Proxy Service (coming soon)
- 📈 **Four Sensors**: Shop info, active listings, recent orders, and statistics
- 🔄 **Automatic Updates**: Configurable refresh intervals (60-3600 seconds) for Direct API
- 🛠️ **Service Calls**: Manual refresh and detailed statistics retrieval

## 📦 Installation

### Prerequisites

- Home Assistant 2025.8.3+
- Etsy seller account with active shop
- (Direct API) Etsy developer account for access
- (Coming Soon) Free Tier for Proxy Service, where no dev account is needed.

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Install" on the Etsy Shop integration
6. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `custom_components/etsyapp` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## 🏷️ Naming Convention

When you add an Etsy Shop integration, it will be named:
- **Integration Name**: `ShopName (ShopID) - Direct` or `ShopName (ShopID) - Proxy`
  - Example: `TestEtsyShop (56636211) - Direct`
- **Device Name**: Just the shop name (e.g., `TestEtsyShop`)

This naming helps distinguish between:
- Multiple shops (each has a unique ID)
- Connection types (Direct API vs Proxy)

## 🚀 Setup

### Direct Etsy API Connection (Available Now)

Best for users with Etsy developer accounts who want direct API access.

1. **Create an Etsy App**:
   - Visit [Etsy Developer Dashboard](https://www.etsy.com/developers/your-apps)
   - Create a new app and note your App Keystring and Shared Secret

2. **Add Integration**:
   - Go to Settings → Integrations → Add Integration
   - Search for "Etsy Shop"
   - Select "Direct Etsy API" connection mode

3. **Enter Credentials**:
   - App Keystring: Your Etsy app's keystring
   - Shared Secret: Your Etsy app's shared secret

4. **Authorize**:
   - You'll be redirected to Etsy to authorize the app
   - Select which shop to monitor (if you have multiple)

### Proxy Service Connection (Coming Soon!)

**Status: In Development - Expected Q1 2025**

I'm building a proxy service that will eliminate the need for an Etsy developer account!

**Planned Features:**
- ✅ No Etsy developer account required
- ✅ Simplified setup process
- ✅ Automatic token management
- ✅ Enhanced security with HMAC authentication
- ✅ Managed service with 99.9% uptime

The proxy service code is complete and tested, but I'm finalizing the infrastructure for a reliable, scalable deployment.

**Want to be notified when it's ready?** Watch this repository for updates!

## 📊 Sensors

The integration provides four sensors with detailed attributes:

### 1. Etsy Shop Info
- **State**: Shop name
- **Attributes**: Shop ID, currency, creation date, announcement, sale message

### 2. Etsy Active Listings
- **State**: Number of active listings
- **Attributes**: Recent listings details, total views, total favorites

### 3. Etsy Recent Orders
- **State**: Number of recent transactions
- **Attributes**: Transaction details, recent revenue, buyer information

### 4. Etsy Shop Statistics
- **State**: Total sales count
- **Attributes**: Active listings, total views, favorites, revenue, ratings

## 🛠️ Services

### `etsyapp.refresh_data`
Manually refresh shop data from Etsy API.

### `etsyapp.get_shop_stats`
Get detailed shop statistics with optional filtering for listings and transactions.

## 🔧 Configuration Options

After setup, you can configure:
- **Listings Display Limit**: Number of listings to show in sensor attributes (1-25)
- **Transactions Display Limit**: Number of recent orders to display (1-25)
- **Stock Threshold**: Alert when stock falls below this number (1-100)

## 🧪 Development

### Running Tests
```bash
pytest tests/
```

## 📝 Requirements

- Home Assistant 2025.8.3+ (for PKCE OAuth2 support)
- Python 3.11+
- Etsy Developer Account (for direct API connection)

## ⚡ Automation Triggers

The integration provides device triggers for automations:

- **New Order**: Triggers when a new order is received
- **New Review**: Triggers when a new review is posted  
- **Low Stock**: Triggers when a listing falls below the configured stock threshold

### Example Automation
```yaml
automation:
  - alias: "Notify on New Etsy Order"
    trigger:
      - platform: device
        device_id: YOUR_DEVICE_ID
        domain: etsyapp
        type: new_order
    action:
      - service: notify.mobile_app
        data:
          message: "You have a new Etsy order!"
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: [Report bugs or request features](https://github.com/jmdevita/etsy-shop-ha-integration/issues)

## 🙏 Acknowledgments

- Built on Home Assistant's OAuth2 framework
- Inspired by the Home Assistant community
- Leveraged Claude to help review, clean up, and comment on my code.

---

**Note**: This integration is not affiliated with or endorsed by Etsy Inc.
