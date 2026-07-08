# Interview Screen — MCQ Assistant

Screenshot MCQ solver with multi-model verification. Phone + laptop workflow with license keys.

## For customers

### 1. Phone (during exam)

Open your personal link (you receive this after purchase):

```
http://YOUR-SERVER:8765/u/ABCDEFGH
```

The key is in the URL — no typing needed. Tap **Grab laptop screen**, **Upload**, or **Paste**.

### 2. Laptop (once before exam)

**Linux — one command install:**

```bash
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash
~/interview-screen-client/start-laptop-client.sh
```

**Windows:**

1. Download: https://github.com/linaelmarzouki-etu-dev/interview-screen/archive/refs/heads/main.zip
2. Extract, run `install-windows-client.bat`
3. Run `start-laptop-client.bat` and leave it open

Client download page: `http://YOUR-SERVER:8765/download`

## For seller (you)

### Generate license + share URL

Admin panel: `http://YOUR-SERVER:8765/admin`

Or CLI:

```bash
python admin_license.py generate --plan 24h --email buyer@email.com
```

Send customer:

- **Share URL:** `http://YOUR-SERVER:8765/u/XXXXXXXX`
- **Linux client:** install command above
- **Windows client:** ZIP link above

### Plans

| Plan | Duration | Questions |
|------|----------|-----------|
| 24h  | 24 hours | 100       |
| 7d   | 7 days   | 500       |
| 30d  | 30 days  | 2000      |

## Server deploy (VPS)

```bash
export DEPLOY_PASSWORD='your-vps-password'
export GROQ_API_KEY='your-groq-key'
export LICENSE_ADMIN_PASSWORD='your-admin-password'
python3 deploy_remote.py
```

## Environment

Copy `.env.example` to `.env`. Key settings:

- `PUBLIC_URL` — used for share links (e.g. `http://139.84.130.152:8765`)
- `LICENSE_REQUIRED=true`
- `LICENSE_ADMIN_PASSWORD` — admin panel at `/admin`