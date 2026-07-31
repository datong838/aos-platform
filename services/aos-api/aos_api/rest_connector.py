"""Platform-neutral, read-only REST GET engine with safe pagination and retries."""
from __future__ import annotations

import email.utils
import ipaddress
import json
import random
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib import error, parse, request


class RestConnectorError(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str


@dataclass(frozen=True)
class Pagination:
    mode: str = "none"
    page_param: str = "page"
    page_size_param: str = "page_size"
    page_size: int = 100
    offset_param: str = "offset"
    cursor_param: str = "cursor"
    next_cursor_path: str = ""
    has_more_path: str = ""


@dataclass(frozen=True)
class RestRequest:
    url: str
    response_path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    pagination: Pagination = field(default_factory=Pagination)
    max_pages: int = 100
    max_items: int = 10_000
    timeout: float = 10
    deadline: float = 120
    max_attempts: int = 3
    initial_delay: float = 1
    qps: float = 0


@dataclass
class RestResult:
    items: list[Any]
    pages: int
    payloads: list[Any]


Transport = Callable[[str, dict[str, str], float], HttpResponse]


class _SafeRedirectHandler(request.HTTPRedirectHandler):
    def __init__(self, policy: "SafeUrlPolicy") -> None:
        super().__init__()
        self.policy = policy

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.policy.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SafeUrlPolicy:
    def __init__(self, *, allow_http_hosts: set[str] | None = None, resolver=socket.getaddrinfo) -> None:
        self.allow_http_hosts = {h.lower() for h in (allow_http_hosts or set())}
        self.resolver = resolver

    def validate(self, url: str) -> None:
        parts = parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.username or parts.password or not host:
            raise RestConnectorError("CONNECTOR_URL_FORBIDDEN")
        if parts.scheme != "https" and not (parts.scheme == "http" and host in self.allow_http_hosts):
            raise RestConnectorError("CONNECTOR_URL_FORBIDDEN")
        if host in {"localhost", "metadata.google.internal"}:
            raise RestConnectorError("CONNECTOR_URL_FORBIDDEN")
        try:
            literal_ip = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            literal_ip = None
        if literal_ip is not None and not literal_ip.is_global:
            raise RestConnectorError("CONNECTOR_URL_FORBIDDEN")
        try:
            addresses = {row[4][0] for row in self.resolver(host, parts.port or (443 if parts.scheme == "https" else 80))}
        except OSError as exc:
            raise RestConnectorError("CONNECTOR_DNS_FAILED") from exc
        for raw in addresses:
            ip = ipaddress.ip_address(raw)
            if not ip.is_global or ip.is_loopback or ip.is_private or ip.is_link_local:
                raise RestConnectorError("CONNECTOR_URL_FORBIDDEN")


class RestGetEngine:
    RETRYABLE = {408, 429, 500, 502, 503, 504}

    def __init__(self, *, transport: Transport | None = None, policy: SafeUrlPolicy | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 jitter: Callable[[], float] = random.random) -> None:
        self.policy, self.clock, self.sleep, self.jitter = policy or SafeUrlPolicy(), clock, sleep, jitter
        self.transport = transport or self._urllib_transport
        self._next_request: dict[tuple[str, str], float] = {}

    def fetch(self, spec: RestRequest, *, org_workspace: str, connection_id: str,
              bearer_token: str = "") -> RestResult:
        if spec.pagination.mode not in {"none", "page", "offset", "cursor"}:
            raise RestConnectorError("CONNECTOR_PAGINATION_INVALID")
        if spec.max_pages < 1 or spec.max_items < 1 or spec.timeout <= 0 or spec.deadline <= 0 or spec.max_attempts < 1:
            raise RestConnectorError("CONNECTOR_LIMIT_INVALID")
        started, items, payloads, seen = self.clock(), [], [], set()
        page, offset, cursor = 1, 0, ""
        for page_index in range(max(1, spec.max_pages)):
            params: dict[str, Any] = {}
            p = spec.pagination
            if p.mode == "page": params = {p.page_param: page, p.page_size_param: p.page_size}
            elif p.mode == "offset": params = {p.offset_param: offset, p.page_size_param: p.page_size}
            elif p.mode == "cursor" and cursor: params = {p.cursor_param: cursor}
            url = self._with_query(spec.url, params)
            headers = {**spec.headers, "Accept": "application/json"}
            if bearer_token: headers["Authorization"] = "Bearer " + bearer_token
            response = self._request(url, headers, spec, started, (org_workspace, connection_id))
            try: payload = json.loads(response.body.decode("utf-8")) if response.body else None
            except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise RestConnectorError("CONNECTOR_RESPONSE_INVALID") from exc
            payloads.append(payload)
            batch = self._path(payload, spec.response_path) if spec.response_path else payload
            batch_items = batch if isinstance(batch, list) else ([] if batch is None else [batch])
            items.extend(batch_items[: max(0, spec.max_items - len(items))])
            if len(items) >= spec.max_items or p.mode == "none": break
            if p.has_more_path and not bool(self._path(payload, p.has_more_path)): break
            if p.mode == "cursor":
                next_cursor = str(self._path(payload, p.next_cursor_path) or "")
                if not next_cursor: break
                if next_cursor in seen: raise RestConnectorError("CONNECTOR_CURSOR_REPEATED")
                seen.add(next_cursor); cursor = next_cursor
            elif len(batch_items) < p.page_size and not p.has_more_path: break
            elif p.mode == "page": page += 1
            elif p.mode == "offset": offset += p.page_size
        return RestResult(items=items, pages=len(payloads), payloads=payloads)

    def _request(self, url, headers, spec, started, limiter_key):
        for attempt in range(spec.max_attempts):
            remaining = spec.deadline - (self.clock() - started)
            if remaining <= 0: raise RestConnectorError("CONNECTOR_DEADLINE_EXCEEDED")
            self.policy.validate(url)
            self._limit(limiter_key, spec.qps)
            remaining = spec.deadline - (self.clock() - started)
            if remaining <= 0: raise RestConnectorError("CONNECTOR_DEADLINE_EXCEEDED")
            try: response = self.transport(url, headers, min(spec.timeout, remaining))
            except (TimeoutError, socket.timeout): response = None
            except OSError: response = None
            if response is not None:
                self.policy.validate(response.final_url)
                if 200 <= response.status < 300: return response
                if response.status not in self.RETRYABLE: raise RestConnectorError("CONNECTOR_UPSTREAM_REJECTED", status=response.status)
            if attempt + 1 >= spec.max_attempts:
                code = "CONNECTOR_TIMEOUT" if response is None else ("CONNECTOR_RATE_LIMITED" if response.status == 429 else "CONNECTOR_UPSTREAM_RETRY_EXHAUSTED")
                raise RestConnectorError(code, status=response.status if response else None)
            delay = self._retry_after(response) if response and response.status == 429 else spec.initial_delay * (2 ** attempt) * (1 + self.jitter())
            if self.clock() - started + delay >= spec.deadline: raise RestConnectorError("CONNECTOR_DEADLINE_EXCEEDED")
            self.sleep(delay)
        raise RestConnectorError("CONNECTOR_UPSTREAM_RETRY_EXHAUSTED")

    def _limit(self, key, qps):
        if qps <= 0: return
        now, due = self.clock(), self._next_request.get(key, self.clock())
        if due > now: self.sleep(due - now)
        self._next_request[key] = max(now, due) + 1 / qps

    @staticmethod
    def _retry_after(response):
        raw = response.headers.get("Retry-After", "")
        try: return max(0.0, float(raw))
        except ValueError:
            try: return max(0.0, (email.utils.parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
            except Exception: return 1.0

    @staticmethod
    def _with_query(url, params):
        parts = parse.urlsplit(url); query = parse.parse_qsl(parts.query, keep_blank_values=True); query.extend((k, str(v)) for k, v in params.items())
        return parse.urlunsplit(parts._replace(query=parse.urlencode(query)))

    @staticmethod
    def _path(payload, path):
        current = payload
        for part in filter(None, path.split(".")):
            if not isinstance(current, dict): return None
            current = current.get(part)
        return current

    def _urllib_transport(self, url, headers, timeout):
        req = request.Request(url, headers=headers, method="GET")
        opener = request.build_opener(_SafeRedirectHandler(self.policy))
        try:
            with opener.open(req, timeout=timeout) as resp:
                return HttpResponse(
                    int(resp.status),
                    dict(getattr(resp, "headers", {}) or {}),
                    resp.read(),
                    resp.geturl() if hasattr(resp, "geturl") else url,
                )
        except error.HTTPError as exc:
            return HttpResponse(int(exc.code), dict(exc.headers), exc.read(), exc.geturl())
