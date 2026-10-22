# 🚀 Tancoin (TAN) — cPanel Deployment Guide

This guide walks you through deploying **Tancoin (Tanzania Digital Coin)** onto any **cPanel** hosting account with **CloudLinux "Setup Python App"** (Phusion Passenger).

---

## 📦 What Was Prepared for cPanel

The project has been configured for cPanel:
1. **`passenger_wsgi.py`**: The Phusion Passenger entry point that connects cPanel's web server directly to Django.
2. **`.htaccess`**: Apache rules to protect sensitive files (`db.sqlite3`, `data/*.json`, `.env`), enable static asset caching, and route requests cleanly.
3. **`tancoin/settings.py`**: Updated to support environment variables (`ALLOWED_HOSTS`, `DJANGO_DEBUG`, `CSRF_TRUSTED_ORIGINS`, `DJANGO_SECRET_KEY`), `STATIC_ROOT`, and **WhiteNoise** for high-performance static file serving without complex Apache aliases.
4. **`requirements.txt`**: Added `whitenoise>=6.6.0` alongside Django, ecdsa, and segno.
5. **`staticfiles/`**: All 137 static files (CSS, JS, fonts, images) are pre-collected and ready to serve.
6. **`tancoin_cpanel_upload.zip`**: A clean, lightweight zip archive ready for 1-click upload and extraction via cPanel File Manager (excludes local `.venv`, git, and cache files).

---

## 🛠️ Step-by-Step Deployment Instructions

### Step 1: Upload Project Files to cPanel
1. Log into your **cPanel Dashboard**.
2. Open **File Manager** (under *Files*).
3. Decide where you want your application files to live:
   - For a dedicated folder (recommended): create a folder like `/home/username/tancoin` (outside `public_html`), or navigate into `/home/username/public_html` if deploying to the primary root.
4. Click **Upload** at the top menu.
5. Select the file:
   ```
   tancoin_cpanel_upload.zip
   ```
6. Once the upload reaches 100%, close the upload tab and return to **File Manager**.
7. Right-click on `tancoin_cpanel_upload.zip` and select **Extract** -> **Extract Files**.
8. Verify that files such as `passenger_wsgi.py`, `manage.py`, `.htaccess`, `tancoin/`, and `data/` are now present in the directory.

---

### Step 2: Create the Python Application in cPanel
1. In cPanel, navigate to the **Software** section and click **Setup Python App** (or *Python Selector*).
2. Click the **Create Application** button.
3. Fill in the fields:
   * **Python version**: Select **Python 3.10**, **3.11**, or **3.12**.
   * **Application root**: The path where you extracted the files (e.g. `tancoin` or `public_html`).
   * **Application URL**: Select your domain or subdomain (e.g. `tancoin.yourdomain.com` or `yourdomain.com`).
   * **Application startup file**: Enter `passenger_wsgi.py`
   * **Application Entry point**: Enter `application`
4. Click **Create** (top right).

---

### Step 3: Install Dependencies
1. On the same Python App configuration page, scroll down to **Configuration files**.
2. In the text box, type:
   ```
   requirements.txt
   ```
   and click **Add**.
3. Once added, click the button **Run Pip Install** next to `requirements.txt`.
4. Wait 30–60 seconds while cPanel installs Django, ecdsa, segno, and whitenoise into your isolated virtual environment. You will see a success message when finished.

> **Alternative via cPanel Terminal**:
> At the top of the Python App page, cPanel shows a command to activate your virtual environment:
> ```bash
> source /home/username/virtualenv/tancoin/3.11/bin/activate && cd /home/username/tancoin
> pip install -r requirements.txt
> ```

---

### Step 4: Configure Production Environment Variables (Recommended)
Under the **Environment variables** section in Setup Python App, click **Add Variable** for each:

| Variable Name | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `DJANGO_DEBUG` | `False` | Disables debug mode for production security |
| `DJANGO_SECRET_KEY` | *(A random 50-character string)* | Cryptographic security key for sessions |
| `ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com` | Prevents HTTP Host header attacks |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com` | Prevents CSRF errors on form submissions |

*(If you are testing initially, you can leave `DJANGO_DEBUG` as `True` until you verify everything works).*

---

### Step 5: Database Migrations & Static Files
Open **Terminal** in cPanel (or use SSH):
1. Copy the virtual environment activation line from the top of your Python App page and paste it into Terminal:
   ```bash
   source /home/username/virtualenv/tancoin/3.11/bin/activate && cd /home/username/tancoin
   ```
2. Run database migrations to initialize authentication tables:
   ```bash
   python manage.py migrate
   ```
3. Run static files collection:
   ```bash
   python manage.py collectstatic --noinput
   ```
4. *(Optional)* Create an administrator user for the Django Admin dashboard:
   ```bash
   python manage.py createsuperuser
   ```

---

### Step 6: Restart & Launch Your Node!
1. Back in cPanel **Setup Python App**, click the **Restart** button at the top.
2. Open your website in your browser:
   ```
   https://yourdomain.com/
   ```
3. **Congratulations!** Your Tancoin blockchain explorer, wallet GUI, mempool viewer, and documentation are now live on cPanel!

---

## 🔒 Security Best Practices on cPanel
- **File Permissions**:
  - Folders: `755`
  - Files: `644`
  - `data/chain.json` and `db.sqlite3` must be writable by the web server process (default cPanel permissions handle this).
- **Genesis Key Security**:
  - `data/genesis_wallet.json` contains the initial miner private key. In production, protect or move this file and ensure debug mode (`DJANGO_DEBUG=False`) is active so the `/api/dev/genesis-wallet/` endpoint is disabled.
- **Enable SSL**: In cPanel, go to **SSL/TLS Status** and run **AutoSSL** to ensure your site runs over secure HTTPS.
