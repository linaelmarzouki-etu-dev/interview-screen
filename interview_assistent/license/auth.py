from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from interview_assistent.license.store import LicenseRecord, LicenseStore, SessionRecord


@dataclass(frozen=True)
class LicenseContext:
    license: LicenseRecord
    session: SessionRecord | None = None
    via_agent: bool = False

    @property
    def license_id(self) -> int:
        return self.license.id


def _client_meta(request: Request) -> tuple[str, str]:
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    return ip, user_agent


def extract_token(
    request: Request,
    x_license_token: str | None = None,
) -> str | None:
    if x_license_token:
        return x_license_token.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token")


def build_license_dependency(store: LicenseStore, *, required: bool):
    async def optional_license(
        request: Request,
        x_license_token: str | None = Header(default=None, alias="X-License-Token"),
    ) -> LicenseContext | None:
        token = extract_token(request, x_license_token)
        if not token:
            if required:
                raise HTTPException(
                    status_code=401,
                    detail="License required. Enter your 8-letter key.",
                )
            return None
        ip, user_agent = _client_meta(request)
        try:
            license_row, session_row = store.validate_token(
                token, ip=ip, user_agent=user_agent
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return LicenseContext(license=license_row, session=session_row)

    return optional_license