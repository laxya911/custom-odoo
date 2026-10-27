# Custom Addons Architecture, Operations & Integration Guide

This guide documents the architecture, dependencies, operational workflows, and frontend integration protocols for all custom Odoo 20 addons located in `custom_addons/`.

---

## 1. Architectural Overview & Dependency Graph

### 📦 Custom Modules Directory

| Module | Purpose | Key Dependencies |
|---|---|---|
| **`pos_order_api`** | Core engine for headless remote orders into POS. Enforces idempotency, session resolution, tax computation, and live POS audio/visual alerts. | `point_of_sale`, `pos_self_order` |
| **`pos_remote_print`** | Auto-kitchen printing service. Listens to Odoo Bus WebSocket events when remote orders land and prints directly via active POS printers without cashier interaction. | `point_of_sale`, `pos_order_api` |
| **`pos_aggregator_gateway`** | Webhook ingestion gateway for Uber Eats, DoorDash, Zomato, and Swiggy. Handles HMAC signature verification, OAuth 2.0 token management, and payload normalization. | `pos_order_api`, `pos_remote_print` |
| **`table_booking_core`** | Restaurant reservation engine. Manages dining shift schedules, capacity limits, party sizes, and collision-proof time-slot availability algorithms. | `point_of_sale`, `pos_restaurant`, `pos_order_api`, `mail` |
| **`table_booking_pos`** | Real-time POS floor plan integration. Overlays live booking status badges, guest party information, and one-click "Seat Guest" workflows onto restaurant tables. | `pos_restaurant`, `table_booking_core`, `pos_remote_print` |
| **`geotek_ecom_api`** | Headless eCommerce API layer providing fast JSON-RPC endpoints for catalogs, categories, variants, and cart management. | `product`, `website_sale` |
| **`odoo_debranding`** | Removes "Powered by Odoo" promotional footers, branding links, and enterprise marketing from emails, portals, and PDF reports. | `web`, `mail`, `digest` |

### 🕸️ Dependency Graph

```
                                  [ point_of_sale ]
                                   /      |      \
                                  /       |       \
                   [ pos_self_order ]     |     [ pos_restaurant ]
                          \               |            /       \
                           \              |           /         \
                         [ pos_order_api ]           /           \
                           /            \           /             \
                          /              \         /               \
              [ pos_remote_print ]     [ table_booking_core ]       \
                     /                       \                      /
                    /                         \                    /
      [ pos_aggregator_gateway ]           [ table_booking_pos ]
```

---

## 2. Proper Installation Sequence (Zero-Dependency-Error Flow)

To avoid `"Missing Dependency"` or unresolved foreign key errors on a fresh database or during migrations, install the modules in strict topological order:

### Phase 1: Core Odoo Standard Dependencies
```powershell
.\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i point_of_sale,pos_restaurant,pos_self_order,mail,website_sale --stop-after-init
```

### Phase 2: POS Order API & Printing Backbone
```powershell
.\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i pos_order_api,pos_remote_print --stop-after-init
```

### Phase 3: Table Booking Suite & Aggregators
```powershell
.\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i table_booking_core,table_booking_pos,pos_aggregator_gateway --stop-after-init
```

### Phase 4: eCommerce Headless & Debranding (Optional)
```powershell
.\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i geotek_ecom_api,odoo_debranding --stop-after-init
```

> [!TIP]
> **One-Command Installation (All Modules):**
> ```powershell
> .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i pos_order_api,pos_remote_print,table_booking_core,table_booking_pos,pos_aggregator_gateway,geotek_ecom_api,odoo_debranding --stop-after-init
> ```

---

## 3. Operational Manual & Configuration Guide

### 🚚 Feature 1: Remote Ordering & POS Delivery Sessions (`pos_order_api`)

#### 1. Enablement in POS Configuration
1. Navigate to **Point of Sale → Configuration → Settings**.
2. Select your POS shop/restaurant profile (e.g., *Main Bar & Kitchen*).
3. Under the **Remote & Online Ordering** section:
   - Check **Accept Remote Orders** (`accept_remote_orders = True`).
   - Select default payment journal (e.g., *Online Payment / Bank*).
4. Save the configuration.

#### 2. Operating the Live Delivery Session
- When the cashier or kitchen manager opens a POS session, remote order acceptance is controlled live on the POS screen:
  - **Top Navigation Bar:** Features an active **Delivery Toggle** switch (`delivery_active`).
  - **Green Indicator:** Session is currently accepting incoming online / aggregator orders.
  - **Grey/Disabled Indicator:** Kitchen is overloaded or paused; incoming orders via API will be cleanly rejected with `400: Kitchen not accepting orders at this time`.
- **Live Notifications:** When a new online order arrives:
  - An audible alert chime rings on the POS browser.
  - A notification toast flashes: `"New Online Order #POS/2026/XXXX - ₹XXX"`.
  - The order is queued into the kitchen display and auto-synced into the POS orders ledger.

#### 3. Delivery Lifecycle Tracking
Orders created via API include full status tracking:
- `received` → Newly created order from website or delivery platform.
- `preparing` → Kitchen acknowledged and cooking.
- `ready` → Packaged and awaiting courier / customer pickup.
- `on_the_way` → Dispatched with courier.
- `delivered` → Completed delivery.
- `cancelled` → Refunded or cancelled.

---

### 🖨️ Feature 2: Automated Kitchen Remote Printing (`pos_remote_print`)

- **Problem Solved:** External API orders normally land in the database silently; without `pos_remote_print`, cashiers had to manually open each order and tap "Print".
- **How It Works:**
  1. `pos_order_api` fires a WebSocket bus message: `('pos.order.api.notification', order_data)` on channel `pos_order_created`.
  2. Any active POS terminal connected to that POS configuration receives the event.
  3. `pos_remote_print` claims a printer lock to ensure only **one** terminal prints the order (preventing duplicate duplicate tickets).
  4. The kitchen order receipt is dispatched directly to the configured IoT / Network / USB kitchen printer.

---

### 🍽️ Feature 3: Table Booking Engine (`table_booking_core`)

#### 1. Configuration (`table.booking.config`)
Navigate to **Point of Sale → Table Bookings → Configuration**:
- **Active Booking:** Check to open online reservations.
- **POS Configuration:** Link to your restaurant POS shop.
- **Slot Duration:** Average dining duration per table (default: `90 minutes`).
- **Slot Interval:** Spacing between reservation arrival times (e.g., `15` or `30 minutes`).
- **Party Size Limits:** Min (1) to Max (e.g., 12 guests).
- **Cancellation Window:** Hours before reservation where customer cancellation is permitted (e.g., `2 hours`).

#### 2. Table Resource Setup (`restaurant.table` integration)
- In **Point of Sale → Floor Plans**, each table defines its seating capacity:
  - Table 1 (Seats: 2, Min: 1)
  - Table 2 (Seats: 4, Min: 2)
  - Table 3 (Seats: 8, Min: 4)
- **Collision-Proof Algorithm:** When a customer requests a slot for 4 guests:
  1. Searches tables where `seats >= party_size`.
  2. Filters out tables already booked or checked in during `(start_time - slot_duration) < existing_booking < (start_time + slot_duration)`.
  3. Returns only true available slots.
  4. At checkout, executes an atomic lock and re-checks for collision before confirming.

---

### 🗺️ Feature 4: POS Floor Plan Booking Overlays (`table_booking_pos`)

- **Floor Plan Visual Overlays:**
  - Tables with reservations in the current shift display a **Calendar / Clock Badge**.
  - **Green Badge:** Table free now, reserved in > 1 hour.
  - **Amber / Orange Badge:** Guest arrival imminent (< 30 minutes).
  - **Blue Badge:** Guest currently seated / active reservation.
- **POS Top Bar Notification Widget:**
  - Displays total upcoming bookings for the current day.
  - Clicking opens the **Today's Reservations Drawer** with customer names, contact phone numbers, party sizes, and notes.
- **One-Click Seating:**
  - Tapping an arrival guest card offers a **"Seat Guest"** button.
  - Automatically transitions the booking status from `confirmed` to `checked_in` and opens the table for ordering.

---

### 🛵 Feature 5: Delivery Aggregators Gateway (`pos_aggregator_gateway`)

#### 1. Supported Providers
- **Uber Eats** (Full HMAC Webhook & OAuth 2.0 API)
- **DoorDash** (Drive & Marketplace Webhooks)
- **Zomato / Swiggy** (Webhook ingestion & mapping)

#### 2. Configuration Setup
Navigate to **Point of Sale → Delivery Aggregators → Configuration**:
1. Click **Create**:
   - **Name:** *Uber Eats Main Outlet*
   - **Provider:** `Uber Eats`
   - **Environment:** `Sandbox` (testing) or `Production`
   - **Store UUID:** Aggregator outlet ID (e.g. `9523e60b-c7d1-49c1-8733-6ba52c00bc5a`)
   - **Client ID & Client Secret:** Aggregator Developer credentials.
   - **Webhook Signing Key:** HMAC secret key provided in the developer console.
2. **Authorize OAuth:** Click "Authorize with Uber" to exchange tokens and establish continuous API access.

#### 3. Webhook Endpoints
- **Uber Eats Webhook URL:**
  ```http
  POST https://your-odoo-domain.com/api/delivery/uber
  Header: X-Uber-Signature: <hmac_sha256_signature>
  ```
- **Security Check:**
  The gateway computes HMAC SHA256 against `request.httprequest.data` using `webhook_signing_key`. If the signature does not match, it immediately rejects with `403 Forbidden`.
- **Payload Normalization:**
  Extracts customer name, delivery address, order line items, and special cooking instructions, maps external item barcodes/SKUs to internal `product.product`, and calls `pos.order.create_api_order()`.

---

## 4. Frontend Custom App Integration (Next.js / Headless)

The external storefront (e.g. Next.js App Router in `test-storefront/`) communicates directly with Odoo via high-performance REST and JSON-RPC endpoints.

### 🔑 Environment Configuration (`.env.local`)
```ini
ODOO_URL=http://localhost:8069
ODOO_DB=odoo20_local
ODOO_API_KEY=d540ada8888a2c6e901b6b43775282534091aed2
CATALOG_MODE=pos
NEXT_PUBLIC_CURRENCY_SYMBOL=₹
```

---

### 📡 API Protocols & Contracts

#### 1. Public Elevated Image Streaming Endpoint
```http
GET /api/pos/product/image/<model>/<id>?v=1
```
- `<model>`: `product.template` or `product.product`
- `<id>`: Integer ID
- **Features:**
  - Elevated `sudo()` execution — serves images for POS products regardless of eCommerce publication status.
  - Automatically identifies image MIME type (`image/png`, `image/jpeg`, `image/webp`).
  - Sets browser cache header: `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`.
  - Next.js Proxy: `http://localhost:3001/api/product-image/[id]`.

---

#### 2. Food Menu Catalog Ingestion
External apps query Odoo's native `/json/2/` REST API with Bearer token:
```typescript
POST /json/2/product.template/search_read
Headers:
  Authorization: Bearer <API_KEY>
  X-Odoo-Database: <DB_NAME>
Body:
{
  "domain": [
    ["sale_ok", "=", true],
    ["available_in_pos", "=", true],
    ["type", "!=", "service"]
  ],
  "fields": [
    "id", "name", "list_price", "description_sale", "pos_categ_ids", 
    "attribute_line_ids", "product_variant_ids", "combo_ids"
  ]
}
```

##### Food Option Rules
- **Variant Attributes (`create_variant !== 'no_variant'`):** Required selection (e.g., Size).
- **Food Extras & Toppings (`create_variant === 'no_variant'`):** Optional multi-toggle selections (e.g., Extra Cheese, Mushrooms).
- **Combos (`product.combo`):** Mandatory selections up to `combo.qty_free`.

---

#### 3. Real-Time POS Order Simulation & Creation
Orders are created through `/api/pos/order/create` (JSON-RPC 2.0).

##### Payload Schema:
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "uuid": "web-order-1793102869826-a9f2",
    "simulate": false,
    "api_source": "native_web",
    "api_customer_name": "Rahul Sharma",
    "api_customer_phone": "+91 98765 43210",
    "api_delivery_address": "Flat 402, Green Valley Apartments, Mumbai",
    "api_order_notes": "Please ring doorbell twice",
    "payment_method": "online",
    "lines": [
      {
        "product_id": 15,
        "qty": 1,
        "price_unit": 18.00,
        "note": "Extra spicy",
        "attribute_value_ids": [217]
      },
      {
        "product_id": 37,
        "qty": 1,
        "price_unit": 20.00,
        "combo_line_ids": [
          { "product_id": 23, "qty": 1, "extra_price": 0.0 },
          { "product_id": 24, "qty": 1, "extra_price": 0.0 },
          { "product_id": 27, "qty": 1, "extra_price": 0.0 }
        ]
      }
    ]
  }
}
```

##### Responses:
- **Simulation Response (`"simulate": true`):**
  ```json
  {
    "status": "success",
    "amount_total": 38.00,
    "amount_tax": 1.90,
    "currency_symbol": "₹",
    "lines": [...]
  }
  ```
- **Order Confirmation Response (`"simulate": false`):**
  ```json
  {
    "status": "success",
    "order_id": 84,
    "pos_ref": "Order 00084-001-0001"
  }
  ```

---

#### 4. Online Table Booking Endpoints

##### 1. Fetch Booking Configuration
```http
POST /api/table_booking/config
Body: { "params": { "pos_config_id": 1 } }
```
Returns: Slot duration, intervals, deposit rules, and party size bounds.

##### 2. Check Available Slots
```http
POST /api/table_booking/slots
Body: { 
  "params": { 
    "date": "2026-10-28", 
    "party_size": 4, 
    "config_id": 1 
  } 
}
```
Returns: Collision-checked slots `[ { "start_time": "2026-10-28 19:00:00", "end_time": "2026-10-28 20:30:00", "tables": [...] } ]`.

##### 3. Create Reservation
```http
POST /api/table_booking/book
Body: {
  "params": {
    "config_id": 1,
    "party_size": 4,
    "slot": {
      "start_time": "2026-10-28 19:00:00",
      "end_time": "2026-10-28 20:30:00",
      "tables": [{ "id": 12 }]
    },
    "customer": {
      "name": "Priya Patel",
      "phone": "+91 91234 56789",
      "email": "priya@example.com",
      "notes": "Window seat preferred"
    }
  }
}
```
Returns: Confirmation reference (e.g., `TB/2026/0014`) and guest cancellation token.

---

## 5. Operations & Troubleshooting Checklist

| Issue | Root Cause | Solution |
|---|---|---|
| `Order Rejected: No active POS session found` | Cashier has not opened a session or `delivery_active` is toggled off. | Open POS session and ensure the **Delivery Toggle** switch in the top bar is green. |
| `Images showing NO IMAGE placeholder` | Browser or Next.js cached earlier placeholder SVG when items were unpublished. | Images now stream via `/api/pos/product/image` with `?v=1`. Verify `odoo.conf` has `custom_addons` in `addons_path`. |
| `Cannot complete order without selecting extras` | Attribute was treated as mandatory single-variant. | Ensure storefront is updated with latest [ItemConfiguratorModal.tsx](file:///e:/Projects/odoo-20/test-storefront/src/components/ItemConfiguratorModal.tsx) where `no_variant` extras are optional multi-toggles. |
| `Uber Webhook 403 Forbidden` | `X-Uber-Signature` mismatch or missing `webhook_signing_key`. | Verify that the signing secret in **Point of Sale → Delivery Aggregators** matches the key in Uber Developer Dashboard. |
| `Table collision on booking` | Two guests submitted the same slot simultaneously. | Engine executes atomic lock. Frontend displays "Table just taken, please select another slot" automatically. |
