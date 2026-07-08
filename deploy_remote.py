#!/usr/bin/env python3
"""Deploy MCQ assistant to a remote Linux VPS with sslip.io HTTPS."""
from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from interview_assistent.sslip import ip_to_sslip_hostname  # noqa: E402

REMOTE_DIR = "/opt/interview-assistent"
SERVICE_NAME = "interview-assistent"

SKIP_DIRS = {".venv", "__pycache__", ".git"}
SKIP_FILES = {".env"}


def make_tarball() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            rel = path.relative_to(ROOT)
            parts = rel.parts
            if parts and parts[0] in SKIP_DIRS:
                continue
            if any(p in SKIP_DIRS for p in parts):
                continue
            if path.name in SKIP_FILES:
                continue
            if path.is_file():
                tar.add(path, arcname=str(rel))
    buffer.seek(0)
    return buffer.read()


def run(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _, stdout, stderr = ssh.exec_command(command, get_pty=True)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err


def main() -> int:
    host = os.environ.get("DEPLOY_HOST", "139.84.130.152")
    user = os.environ.get("DEPLOY_USER", "root")
    password = os.environ.get("DEPLOY_PASSWORD")
    if not password:
        print("DEPLOY_PASSWORD is required", file=sys.stderr)
        return 1

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        print("GROQ_API_KEY is required", file=sys.stderr)
        return 1

    license_pepper = os.environ.get("LICENSE_PEPPER", "").strip()
    license_admin = os.environ.get("LICENSE_ADMIN_PASSWORD", "").strip()
    if not license_pepper:
        import secrets

        license_pepper = secrets.token_hex(24)
    if not license_admin:
        import secrets

        license_admin = secrets.token_urlsafe(16)
        print(f"Generated LICENSE_ADMIN_PASSWORD={license_admin}")

    sslip_enable = os.environ.get("SSLIP_ENABLE", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    sslip_host = os.environ.get("SSLIP_HOST", "").strip() or ip_to_sslip_hostname(host)
    certbot_email = os.environ.get("CERTBOT_EMAIL", "admin@sslip.io").strip()
    public_url = os.environ.get("PUBLIC_URL", "").strip() or (
        f"https://{sslip_host}" if sslip_enable else f"http://{host}:8765"
    )
    app_host = "127.0.0.1" if sslip_enable else "0.0.0.0"

    print(f"Connecting to {user}@{host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=30)

    print("Installing system packages...")
    packages = "python3 python3-venv python3-pip"
    if sslip_enable:
        packages += " nginx certbot python3-certbot-nginx"
    code, out, err = run(
        ssh,
        "export DEBIAN_FRONTEND=noninteractive; "
        f"apt-get update -qq && apt-get install -y -qq {packages}",
    )
    if code != 0:
        print(out, err)
        return code

    print("Uploading project...")
    run(ssh, f"mkdir -p {REMOTE_DIR}")
    tarball = make_tarball()
    sftp = ssh.open_sftp()
    with sftp.file(f"{REMOTE_DIR}/app.tar.gz", "wb") as remote:
        remote.write(tarball)
    sftp.close()

    env_content = f"""MODE=mcq
GROQ_API_KEY={groq_key}
OPENAI_BASE_URL=https://api.groq.com/openai/v1
VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
MCQ_REASONING_MODEL=llama-3.3-70b-versatile
MCQ_REASONING_MODELS=llama-3.3-70b-versatile,openai/gpt-oss-120b,qwen/qwen3-32b
MCQ_TWO_STEP=true
MCQ_ANSWER_ONLY=true
MCQ_ALLOW_DESKTOP_GRAB=false
HOST={app_host}
PORT=8765
ROLE=Software Engineer
EXTRA_CONTEXT=Focus on concise MCQ answers
LICENSE_REQUIRED=true
LICENSE_DB_PATH=data/licenses.db
LICENSE_PEPPER={license_pepper}
LICENSE_ADMIN_PASSWORD={license_admin}
GUMROAD_WEBHOOK_SECRET=
PUBLIC_URL={public_url}
SSLIP_HOST={sslip_host}
"""

    nginx_block = ""
    if sslip_enable:
        nginx_block = f"""
cat > /etc/nginx/sites-available/{SERVICE_NAME} << 'NGINXEOF'
server {{
    listen 80;
    server_name {sslip_host};

    location / {{
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }}
}}
NGINXEOF
ln -sf /etc/nginx/sites-available/{SERVICE_NAME} /etc/nginx/sites-enabled/{SERVICE_NAME}
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
certbot --nginx -d {sslip_host} --non-interactive --agree-tos -m {certbot_email} --redirect || echo "Certbot: will retry on next deploy if rate-limited"
"""

    setup_script = f"""set -e
cd {REMOTE_DIR}
tar -xzf app.tar.gz
rm -f app.tar.gz
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
cat > .env << 'ENVEOF'
{env_content}ENVEOF
chmod 600 .env

cat > /etc/systemd/system/{SERVICE_NAME}.service << 'UNITEOF'
[Unit]
Description=Interview MCQ Assistant
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_DIR}
ExecStart={REMOTE_DIR}/.venv/bin/python -m interview_assistent --mode mcq
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable {SERVICE_NAME}
systemctl restart {SERVICE_NAME}
{nginx_block}
sleep 2
systemctl is-active {SERVICE_NAME}
curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8765/ || true
"""

    print("Setting up app and service...")
    code, out, err = run(ssh, setup_script)
    print(out)
    if err:
        print(err, file=sys.stderr)
    if code != 0:
        _, logs, _ = run(ssh, f"journalctl -u {SERVICE_NAME} -n 20 --no-pager")
        print(logs)
        return code

    if sslip_enable:
        _, https_code, _ = run(
            ssh,
            f"curl -s -o /dev/null -w '%{{http_code}}' https://{sslip_host}/ || true",
        )
        print(f"HTTPS check: {https_code.strip()}")

    print(f"\nDeployed!")
    print(f"  Public URL:  {public_url}")
    if sslip_enable:
        print(f"  sslip.io:    https://{sslip_host}")
        print(f"  License URL: {public_url}/u/YOURKEY")
    else:
        print(f"  Open:        http://{host}:8765")
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())