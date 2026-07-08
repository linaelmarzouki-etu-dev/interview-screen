from __future__ import annotations

import re

_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def is_ipv4(value: str) -> bool:
    text = value.strip()
    if not _IPV4_RE.match(text):
        return False
    return all(0 <= int(part) <= 255 for part in text.split("."))


def ip_to_sslip_hostname(ip: str) -> str:
    """139.84.130.152 -> 139-84-130-152.sslip.io"""
    normalized = ip.strip()
    if not is_ipv4(normalized):
        raise ValueError(f"Not an IPv4 address: {ip}")
    return normalized.replace(".", "-") + ".sslip.io"


def public_url_for_ip(ip: str, *, https: bool = True) -> str:
    host = ip_to_sslip_hostname(ip)
    return f"https://{host}" if https else f"http://{host}"