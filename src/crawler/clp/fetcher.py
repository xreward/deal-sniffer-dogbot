import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from curl_cffi import requests

from ..config import CrawlConfig
from ..session import build_proxy_url


class ClpFetcher:
    DEFAULT_HEADERS = {
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Dnt": "1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://www.coupang.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Priority": "u=0, i",
        "Connection": "keep-alive",
    }

    def __init__(self, config: CrawlConfig, cookie_header: Optional[str] = None):
        self.config = config
        self.cookie_header = (cookie_header or "").strip() or self._load_cookie_header()
        if not self.cookie_header:
            print(
                "[WARN] Cookie is missing. Configure cookies.json or COUPANG_COOKIE in .env."
            )

    def _load_cookie_header(self) -> str:
        if self.config.cookie_path.exists():
            try:
                payload = json.loads(self.config.cookie_path.read_text(encoding="utf-8"))
                return str(payload.get("cookie_string", "")).strip()
            except Exception as exc:
                print(f"[WARN] Failed to read {self.config.cookie_path}: {exc}")

        return os.getenv("COUPANG_COOKIE", "").strip()

    def _cookie_dict(self) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        for part in re.split(r";\s*", self.cookie_header):
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key:
                pairs[key] = value.strip()
        return pairs

    def _proxy_url(self) -> Optional[str]:
        return build_proxy_url(self.config)

    def fetch(self, target_url: str) -> dict:
        headers = dict(self.DEFAULT_HEADERS)
        headers["Referer"] = target_url

        request_cookies = None
        if self.config.use_cookie_header and self.cookie_header:
            headers["Cookie"] = self.cookie_header
        else:
            request_cookies = self._cookie_dict() or None
            headers.pop("Cookie", None)

        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            "cookies": request_cookies,
            "impersonate": self.config.impersonate,
            "timeout": self.config.request_timeout_sec,
            "allow_redirects": True,
        }

        proxy_url = self._proxy_url()
        if proxy_url:
            request_kwargs["proxy"] = proxy_url

        try:
            response = requests.get(
                target_url,
                **request_kwargs,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "request_info": {
                    "target_url": target_url,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        html = response.text or ""
        return {
            "request_info": {
                "url": str(response.url),
                "method": "GET",
                "timestamp": datetime.now().isoformat(),
                "target_url": target_url,
            },
            "response_info": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "cookies": dict(response.cookies) if response.cookies else {},
                "content_length": len(response.content),
            },
            "html": html,
        }
