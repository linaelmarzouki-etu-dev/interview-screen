# Interview Screen — MCQ Assistant

Screenshot MCQ solver with multi-model verification. Phone + laptop workflow with license keys.

> **Important:** Every command below shows `XXXXXXXX` as a **placeholder**.
> Replace it with your **real 8-letter key** from the seller (e.g. `ZLHUFEAZ`).
> Do **not** type the letters `YOURKEY` or `XXXXXXXX` literally.

## For customers

### 1. Phone (during exam)

Open the link you receive (key is already in the URL):

```
https://139-84-130-152.sslip.io/u/XXXXXXXX
```

Example with a real key:

```
https://139-84-130-152.sslip.io/u/ZLHUFEAZ
```

Tap **Grab laptop screen**, **Upload**, or **Paste**. No typing on phone if you use the full URL.

---

### 2. Laptop (once before exam)

Use the **same key** as on the phone. Laptop and phone are paired — other users cannot connect to your session.

#### Linux

**Option A — install + run (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s XXXXXXXX
~/interview-screen-client/start-laptop-client.sh XXXXXXXX
```

**Option B — one command:**

```bash
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/client.sh | bash -s XXXXXXXX
```

**Option C — environment variable:**

```bash
LICENSE_KEY=XXXXXXXX curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash
~/interview-screen-client/start-laptop-client.sh
```

**Real example** (if your key is `ZLHUFEAZ`):

```bash
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s ZLHUFEAZ
~/interview-screen-client/start-laptop-client.sh ZLHUFEAZ
```

You should see: `Laptop paired with your license. Ready for GRAB.`

---

#### Windows

1. Download ZIP: https://github.com/linaelmarzouki-etu-dev/interview-screen/archive/refs/heads/main.zip  
2. Extract the folder  
3. Open **Command Prompt** in that folder  
4. Install (replace `XXXXXXXX` with your key):

```bat
install-windows-client.bat XXXXXXXX
```

5. Before exam, run (same key):

```bat
start-laptop-client.bat XXXXXXXX
```

**Real example:**

```bat
install-windows-client.bat ZLHUFEAZ
start-laptop-client.bat ZLHUFEAZ
```

If no key is passed, the script will **ask you to type it** in the window.

---

### 3. Quick reference

| Step | Linux | Windows |
|------|-------|---------|
| Phone | `https://139-84-130-152.sslip.io/u/XXXXXXXX` | same |
| Laptop install | `curl ... \| bash -s XXXXXXXX` | `install-windows-client.bat XXXXXXXX` |
| Laptop start | `./start-laptop-client.sh XXXXXXXX` | `start-laptop-client.bat XXXXXXXX` |

Download page: https://139-84-130-152.sslip.io/download  
Laptop setup help: https://139-84-130-152.sslip.io/laptop/XXXXXXXX

---

## For seller (you)

### Generate license + share URL

Admin panel: https://139-84-130-152.sslip.io/admin

Or CLI on VPS:

```bash
python admin_license.py generate --plan 24h --email buyer@email.com
```

Send customer **all three** (with their real key instead of `XXXXXXXX`):

```
Phone:  https://139-84-130-152.sslip.io/u/XXXXXXXX

Linux:
curl -fsSL https://raw.githubusercontent.com/linaelmarzouki-etu-dev/interview-screen/main/install-linux-client.sh | bash -s XXXXXXXX
~/interview-screen-client/start-laptop-client.sh XXXXXXXX

Windows:
install-windows-client.bat XXXXXXXX
start-laptop-client.bat XXXXXXXX
```

### Plans

| Plan | Duration | Questions |
|------|----------|-----------|
| 24h  | 24 hours | 100       |
| 7d   | 7 days   | 500       |
| 30d  | 30 days  | 2000      |

---

## Server deploy (VPS)

```bash
export DEPLOY_PASSWORD='your-vps-password'
export GROQ_API_KEY='your-groq-key'
export LICENSE_ADMIN_PASSWORD='your-admin-password'
python3 deploy_remote.py
```

## Environment

Copy `.env.example` to `.env`. Key settings:

- `PUBLIC_URL` — HTTPS via sslip.io (e.g. `https://139-84-130-152.sslip.io`)
- `SSLIP_HOST` — `139.84.130.152` → `139-84-130-152.sslip.io`
- `LICENSE_REQUIRED=true`
- `LICENSE_ADMIN_PASSWORD` — admin panel at `/admin`