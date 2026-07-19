"""S3-compatible object store adapter (Dev MinIO). T4.2 — never ship MinIO server in customer package."""
from __future__ import annotations

import hashlib
import hmac
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.object_store")

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass
class S3Config:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)


def get_config() -> S3Config:
    load_dotenv()
    if _env("AOS_S3_DISABLED", "").lower() in {"1", "true", "yes"}:
        return S3Config(endpoint="", bucket="", access_key="", secret_key="")
    endpoint = _env("AOS_S3_ENDPOINT") or _env("MINIO_ENDPOINT")
    if not endpoint:
        wsl = _env("AOS_WSL_IP")
        endpoint = f"http://{wsl}:9000" if wsl else "http://127.0.0.1:9000"
    return S3Config(
        endpoint=endpoint,
        bucket=_env("AOS_S3_BUCKET", "aos-media"),
        access_key=_env("AOS_S3_ACCESS_KEY", _env("MINIO_ROOT_USER", "aosdev")),
        secret_key=_env("AOS_S3_SECRET_KEY", _env("MINIO_ROOT_PASSWORD", "aos_dev_only_change_me")),
        region=_env("AOS_S3_REGION", "us-east-1"),
    )


def _endpoint_candidates(cfg: S3Config) -> list[str]:
    eps = [cfg.endpoint.rstrip("/")]
    if "127.0.0.1" in cfg.endpoint:
        wsl = _env("AOS_WSL_IP")
        if not wsl:
            try:
                import subprocess

                wsl = (
                    subprocess.check_output(
                        ["wsl", "-d", "Ubuntu", "-e", "hostname", "-I"],
                        text=True,
                        timeout=3,
                    )
                    .strip()
                    .split()[0]
                )
            except Exception:  # noqa: BLE001
                wsl = ""
        if wsl:
            eps.append(cfg.endpoint.replace("127.0.0.1", wsl).rstrip("/"))
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for e in eps:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _aws4_request(
    *,
    method: str,
    url: str,
    host: str,
    path: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    region: str,
    content_type: str = "application/octet-stream",
    timeout: float = 30,
) -> tuple[int, bytes, dict[str, str]]:
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    if method.upper() == "GET":
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        headers = {
            "Host": host,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
        }
    else:
        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
        headers = {
            "Content-Type": content_type,
            "Host": host,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
        }
    canonical_request = "\n".join(
        [
            method,
            path,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{datestamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region, "s3"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    req = urllib.request.Request(
        url, data=body if method.upper() != "GET" else None, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.read(), resp_headers
    except urllib.error.HTTPError as exc:
        body_err = exc.read() if hasattr(exc, "read") else b""
        raise RuntimeError(f"s3_http_{exc.code}: {body_err[:200]!r}") from exc


def object_key_for(
    rid: str,
    name: str,
    *,
    org_id: str,
    project_id: str,
) -> str:
    """TWA.8 — key always under {org}/{project}/mediasets/…"""
    from aos_api.tenant_prefix import build_object_key

    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]
    return build_object_key(org_id, project_id, "mediasets", rid, safe or "blob")


def put_bytes(
    *,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    cfg: S3Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or get_config()
    if not cfg.enabled:
        raise RuntimeError("object_store_not_configured")
    last_err: Exception | None = None
    for endpoint in _endpoint_candidates(cfg):
        try:
            host = endpoint.split("://", 1)[-1]
            path = f"/{cfg.bucket}/{quote(key, safe='/')}"
            url = f"{endpoint}{path}"
            status, _body, headers = _aws4_request(
                method="PUT",
                url=url,
                host=host,
                path=path,
                body=data,
                access_key=cfg.access_key,
                secret_key=cfg.secret_key,
                region=cfg.region,
                content_type=content_type,
            )
            etag = headers.get("etag", "").strip('"')
            log.info(
                "s3_put key=%s status=%s bytes=%s etag=%s endpoint=%s",
                key,
                status,
                len(data),
                etag,
                endpoint,
            )
            return {
                "ok": status in (200, 204),
                "key": key,
                "etag": etag,
                "bytes": len(data),
                "bucket": cfg.bucket,
                "endpoint": endpoint,
            }
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log.warning("s3_put_retry endpoint=%s err=%s", endpoint, exc)
    raise RuntimeError(str(last_err) if last_err else "s3_put_failed")


def get_bytes(*, key: str, cfg: S3Config | None = None) -> bytes:
    cfg = cfg or get_config()
    if not cfg.enabled:
        raise RuntimeError("object_store_not_configured")
    last_err: Exception | None = None
    for endpoint in _endpoint_candidates(cfg):
        try:
            host = endpoint.split("://", 1)[-1]
            path = f"/{cfg.bucket}/{quote(key, safe='/')}"
            url = f"{endpoint}{path}"
            status, body, _headers = _aws4_request(
                method="GET",
                url=url,
                host=host,
                path=path,
                body=b"",
                access_key=cfg.access_key,
                secret_key=cfg.secret_key,
                region=cfg.region,
            )
            if status != 200:
                raise RuntimeError(f"s3_get_status_{status}")
            log.info("s3_get key=%s bytes=%s endpoint=%s", key, len(body), endpoint)
            return body
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log.warning("s3_get_retry endpoint=%s err=%s", endpoint, exc)
    raise RuntimeError(str(last_err) if last_err else "s3_get_failed")


def health_probe() -> dict[str, Any]:
    """Put then get a tiny probe object."""
    cfg = get_config()
    if not cfg.enabled:
        return {"ok": False, "detail": "not_configured", "endpoint": cfg.endpoint}
    key = "dev-probes/aos-t42-probe.txt"
    payload = b"aos-t42-probe"
    try:
        put_bytes(key=key, data=payload, content_type="text/plain", cfg=cfg)
        got = get_bytes(key=key, cfg=cfg)
        ok = got == payload
        return {
            "ok": ok,
            "endpoint": cfg.endpoint,
            "bucket": cfg.bucket,
            "probeKey": key,
            "roundTrip": ok,
            "accessKeyRef": "env:AOS_S3_ACCESS_KEY|MINIO_ROOT_USER",
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("s3_health_fail err=%s", exc)
        return {
            "ok": False,
            "endpoint": cfg.endpoint,
            "bucket": cfg.bucket,
            "detail": str(exc),
            "accessKeyRef": "env:AOS_S3_ACCESS_KEY|MINIO_ROOT_USER",
        }
