from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class CrawlConfig:
    base_url: str = "https://www.coupang.com"
    category_url: str = "https://www.coupang.com/np/categories/195050?listSize=120"
    list_size: int = 120
    request_timeout_sec: int = 30
    impersonate: str = "chrome120"
    use_cookie_header: bool = False
    sleep_min_sec: float = 0.1
    sleep_max_sec: float = 0.3
    category_list_path: Path = SRC_ROOT / "category_list.txt"
    cookie_path: Path = SRC_ROOT / "cookies.json"
    output_dir: Path = SRC_ROOT / "output"
    debug_root_dir: Path = SRC_ROOT / "test_log"
    proxy_ip: str = ""
    proxy_port: Optional[int] = None
    proxy_scheme: str = "socks5"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_queue_key: str = "deal_sniffer:clp:raw_html"
    parser_consume_count: int = 100
    parser_block_timeout_sec: int = 5


DEFAULT_CONFIG = CrawlConfig()

COOKIE_ALLOWLIST = {
    "_coupang_session",
    "PCID",
    "coupang_tracking",
    "visit_id",
}

BLOCKED_SIGNALS = [
    "access denied",
    "request blocked",
    "robot check",
    "akamai",
    "captcha",
    "error code 403",
    "status code 403",
]

PRODUCT_CARD_SELECTORS = [
    "div.ProductUnit_productNameV2__cV9cw",
    "li.search-product",
    "li.search-product-wrap",
    "li.search-product.search-product__ad-badge",
    "div.search-product",
    "ul#productList > li",
    "ul#productList li",
]

# Proxy setting for curl_cffi requests (set directly in code)
PROXY_IP = "192.168.1.195"
PROXY_PORT: Optional[int] = 10000
PROXY_SCHEME = "http"