# Interview Screen — MCQ Assistant

Screenshot MCQ solver with multi-model verification. Phone + laptop workflow with license keys.

## For customers

### 1. Phone (during exam)

Open your personal link (you receive this after purchase):

```
https://139-84-130-152.sslip.io/u/ABCDEFGH
```

The key is in the URL — no typing needed. Tap **Grab laptop screen**, **Upload**, or **Paste**.

### 2. Laptop (once before exam)

**Linux — replace `YOURKEY` with your 8-letter key:**

```bash
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s YOURKEY
~/interview-screen-client/start-laptop-client.sh YOURKEY
```

**Windows:**

1. Download: https://github.com/linaelmarzouki-etu-dev/interview-screen/archive/refs/heads/main.zip
2. Extract, run `install-windows-client.bat`
3. Run `start-laptop-client.bat` and leave it open

Client download page: `https://139-84-130-152.sslip.io/download`

## For seller (you)

### Generate license + share URL

Admin panel: `https://139-84-130-152.sslip.io/admin`

Or CLI:

```bash
python admin_license.py generate --plan 24h --email buyer@email.com
```

Send customer:

- **Share URL:** `https://139-84-130-152.sslip.io/u/XXXXXXXX`
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

- `PUBLIC_URL` — HTTPS share links via sslip.io (e.g. `https://139-84-130-152.sslip.io`)
- `SSLIP_HOST` — hostname derived from VPS IP (`139.84.130.152` → `139-84-130-152.sslip.io`)
- `LICENSE_REQUIRED=true`
- `LICENSE_ADMIN_PASSWORD` — admin panel at `/admin`