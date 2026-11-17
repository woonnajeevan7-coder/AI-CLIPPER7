# Twitch EventSub Local Development Setup via Cloudflare Tunnel

> **Purpose:** Twitch EventSub requires a publicly reachable **HTTPS** callback endpoint with a valid SSL/TLS certificate. During local development (`http://localhost:8000`), Cloudflare Tunnel (`cloudflared`) provides a free, zero-config secure HTTPS ingress that forwards Twitch webhook dispatches directly to your local FastAPI backend.

---

## 1. Quickstart (Free Ad-Hoc Tunnel)

### Step 1: Install `cloudflared`

On Windows (PowerShell):
```powershell
winget install Cloudflare.cloudflared
```
*(Or download the standalone executable from [Cloudflare Releases](https://github.com/cloudflare/cloudflared/releases) and place in your PATH).*

Verify installation:
```powershell
cloudflared --version
```

---

### Step 2: Launch Tunnel to Local FastAPI Backend

Ensure your FastAPI server is running on port `8000`:
```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

In a separate terminal, expose port `8000`:
```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare will output a public HTTPS URL:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://whispering-ocean-abc123.trycloudflare.com                                         |
+--------------------------------------------------------------------------------------------+
```

---

### Step 3: Update `.env` Configuration

Copy the generated HTTPS URL and update your `.env` file:

```ini
# Security & Token Encryption
TOKEN_ENCRYPTION_KEY=ReuO4DTAmNr_e0_B5Q4bi-A0yiU2nRp38Lua542Q4bs=

# Twitch Credentials & EventSub Configuration
TWITCH_CLIENT_ID=your_twitch_client_id_from_developer_console
TWITCH_CLIENT_SECRET=your_twitch_client_secret
TWITCH_REDIRECT_URI=https://whispering-ocean-abc123.trycloudflare.com/api/v1/twitch/callback
TWITCH_EVENTSUB_SECRET=generate_a_random_32_byte_secret_for_eventsub_hmac
TWITCH_WEBHOOK_CALLBACK_URL=https://whispering-ocean-abc123.trycloudflare.com/api/v1/twitch/webhook
```

Restart or reload your FastAPI app so it picks up the updated environment.

---

## 2. Testing EventSub Webhooks with Twitch CLI

The official [Twitch CLI](https://github.com/twitchdev/twitch-cli) allows simulating all EventSub events locally without going live on Twitch.

### Install Twitch CLI
```powershell
# Via Scoop (Windows)
scoop bucket add twitch https://github.com/twitchdev/scoop-bucket.git
scoop install twitch-cli
```

### 1. Verify Handshake Challenge
Simulate a subscription handshake verification:
```powershell
twitch event trigger stream.online `
  -F https://whispering-ocean-abc123.trycloudflare.com/api/v1/twitch/webhook `
  -s generate_a_random_32_byte_secret_for_eventsub_hmac `
  -T webhook_callback_verification
```
**Expected Response:** Status `200 OK` returning the challenge string in plain text.

### 2. Simulate `stream.online`
```powershell
twitch event trigger stream.online `
  -F https://whispering-ocean-abc123.trycloudflare.com/api/v1/twitch/webhook `
  -s generate_a_random_32_byte_secret_for_eventsub_hmac
```
**Result in Database:**
- An EventSub payload arrives.
- HMAC-SHA256 signature is verified.
- Replay check validates `Twitch-Eventsub-Message-Id` and `Timestamp`.
- A `LiveSession` row is created with `status="starting"` and `rights_confirmed=True`.

### 3. Simulate `stream.offline`
```powershell
twitch event trigger stream.offline `
  -F https://whispering-ocean-abc123.trycloudflare.com/api/v1/twitch/webhook `
  -s generate_a_random_32_byte_secret_for_eventsub_hmac
```
**Result in Database:**
- Existing active `LiveSession` for the broadcaster is updated to `status="stopping"` with `stopped_at = UTC NOW`.

---

## 3. Production Persistent Cloudflare Tunnel (Named Tunnel)

For persistent domains (e.g. `twitch-webhook.yourdomain.com`):

1. **Authenticate Cloudflare CLI:**
   ```bash
   cloudflared tunnel login
   ```
2. **Create Named Tunnel:**
   ```bash
   cloudflared tunnel create live-clipper
   ```
3. **Configure Routing (`~/.cloudflared/config.yml`):**
   ```yaml
   tunnel: <TUNNEL_ID>
   credentials-file: /path/to/<TUNNEL_ID>.json

   ingress:
     - hostname: twitch-webhook.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
4. **Create DNS Record:**
   ```bash
   cloudflared tunnel route dns live-clipper twitch-webhook.yourdomain.com
   ```
5. **Run Tunnel as Service:**
   ```bash
   cloudflared tunnel run live-clipper
   ```
