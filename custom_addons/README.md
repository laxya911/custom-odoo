# Custom Addons & Operations Guide

This directory (`custom_addons/`) contains custom applications, integrations, and extensions developed for this Odoo 20 instance.

---

## 📦 Custom Addons & Apps Overview

| Module Name | Category | Key Dependencies | Description |
|---|---|---|---|
| **`geotek_ecom_api`** | Website / eCommerce | `product`, `website_sale` | Headless JSON-RPC API endpoints powering external eCommerce storefronts (e.g. Next.js). Provides optimized payloads for product catalogs, variants, pricing, and cart checkout. |
| **`odoo_debranding`** | Core / Debranding | `web`, `mail`, `digest` | Unified debranding module. Removes "Powered by Odoo" and promotional branding from standard transactional emails, portal layouts, PDF report footers, and periodic KPI digest emails. |
| **`pos_aggregator_gateway`** | Point of Sale / Delivery | `pos_order_api`, `pos_remote_print` | Webhook ingestion gateway for third-party food delivery aggregators (e.g., UberEats, DoorDash). Normalizes external payloads, maps product/store IDs, and injects orders via `pos_order_api`. |
| **`pos_order_api`** | Point of Sale / Backend | `point_of_sale`, `pos_self_order` | Core service layer allowing external systems, webhooks, and self-order apps to inject orders directly into active POS sessions. Handles idempotency (UUIDs), session validation, tax computations, and POS delivery status widgets. |
| **`pos_remote_print`** | Point of Sale / Kitchen | `point_of_sale`, `pos_order_api` | Automated kitchen order printing system. Listens to Odoo Bus websocket notifications when remote orders arrive and triggers printing on active POS terminal printers without requiring cashier intervention. |
| **`table_booking_core`** | Sales / Restaurant | `point_of_sale`, `pos_restaurant`, `pos_order_api`, `mail` | Core booking engine for restaurant reservations. Manages table resources, seating capacity rules, shift schedules, and collision-proof time slot allocation algorithms. |
| **`table_booking_pos`** | Point of Sale / Restaurant | `pos_restaurant`, `table_booking_core`, `pos_remote_print` | Real-time POS floor plan integration for table reservations. Adds live booking status overlays to restaurant floor tables, notification badges, reservation detail popups, and quick seating actions. |

---

## 🛠️ Odoo Management Commands (Run from Root Directory)

All commands below should be executed from the root repository directory (`e:\Projects\odoo-20`).

### 1. Starting the Server

- **Standard Run (using configuration file):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local
  ```

- **Developer Mode with Auto-Reload (restarts automatically on Python code changes):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local --dev=reload
  ```

- **Full Developer Mode (Python auto-reload, XML view reload from disk, unminified assets, qweb debug):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local --dev=all
  ```

- **Specify Custom HTTP Port (e.g. 8070):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local --http-port=8070
  ```

---

### 2. Module Installation & Updates

- **Install a Single Custom Module:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i <module_name> --stop-after-init
  ```
  *Example:*
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -i geotek_ecom_api --stop-after-init
  ```

- **Update / Upgrade an Existing Module (reloads XML views, Python models, data files):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -u <module_name> --stop-after-init
  ```

- **Update Multiple Modules:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -u pos_order_api,pos_remote_print --stop-after-init
  ```

- **Update All Installed Modules in the Database:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local -u all --stop-after-init
  ```

---

### 3. Interactive Shell & Debugging

- **Open Interactive Python Shell with Odoo Environment:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin shell -c odoo.conf -d odoo20_local
  ```
  *Inside the shell:*
  ```python
  # Explore records using the ORM:
  users = env['res.users'].search([])
  print(users.mapped('name'))
  
  # Commit changes:
  env.cr.commit()
  ```

- **Run with Detailed SQL Query Logging:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local --log-sql
  ```

- **Run with Detailed HTTP / Controller Request Logging:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_local --log-web
  ```

---

### 4. Database Operations

- **Initialize a Brand New Database (e.g. `odoo20_test`):**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo20_test -i base --stop-after-init
  ```

- **Dump / Backup an Odoo Database to a Zip File:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin db dump -c odoo.conf -d odoo20_local backup.zip
  ```

- **Restore / Load a Database from a Zip File:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin db load -c odoo.conf -d odoo20_restored backup.zip
  ```

---

### 5. Creating a New Custom Addon

- **Scaffold a New Module Skeleton into `custom_addons/`:**
  ```powershell
  .\.venv\Scripts\python.exe odoo-bin scaffold my_custom_module custom_addons
  ```

---

## ⚙️ Configuration File Reference (`odoo.conf`)

Located in the project root (ignored by Git):

```ini
[options]
addons_path = E:\Projects\odoo-20\odoo\addons,E:\Projects\odoo-20\addons,E:\Projects\odoo-20\custom_addons
admin_passwd = admin
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
db_template = template1
pg_path = C:\Program Files\PostgreSQL\18\bin
http_port = 8069
log_level = info
```
