#!/usr/bin/env python3
import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests
from dotenv import load_dotenv
import undetected_chromedriver as uc

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawler.browser.anti_detection_browser import AntiDetectionBrowser

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class CrawlConfig:
    base_url: str = "https://www.coupang.com"
    category_url: str = "https://www.coupang.com/np/categories/195050?listSize=120"
    filter_type: str = "rocket"
    list_size: int = 120
    pages: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9)
    request_timeout_sec: int = 30
    impersonate: str = "chrome120"
    use_cookie_header: bool = False
    sleep_min_sec: float = 0.1
    sleep_max_sec: float = 0.3
    category_list_path: Path = REPO_ROOT / "category_list.txt"
    cookie_path: Path = REPO_ROOT / "cookies.json"
    output_dir: Path = REPO_ROOT / "output"
    debug_root_dir: Path = REPO_ROOT / "test_log"
    proxy_ip: str = ""
    proxy_port: Optional[int] = None
    proxy_scheme: str = "socks5"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coupang category crawler")
    parser.add_argument(
        "--category-url",
        default=DEFAULT_CONFIG.category_url,
        help="Session bootstrap category URL",
    )
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace) -> CrawlConfig:
    return CrawlConfig(
        category_url=str(args.category_url),
        proxy_ip=PROXY_IP,
        proxy_port=PROXY_PORT,
        proxy_scheme=PROXY_SCHEME,
    )


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def load_category_ids(path: Path) -> List[str]:
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_clp_report(path: Path, results: List[dict]) -> None:
    success_count = 0
    fail_count = 0
    lines: List[str] = []

    for category in results:
        is_success = bool(category["success"])
        if is_success:
            success_count += 1
        else:
            fail_count += 1

        status_text = "SUCCESS" if is_success else "FAIL"
        lines.append(
            f"[{status_text}] category={category['category_id']} total_products={category['total_products']}"
        )

        for page in category["pages"]:
            lines.append(
                f"  - page={page['page']} status={page['status_code']} products={page['products']}"
            )

    lines.append("")
    lines.append(f"TOTAL: success={success_count}, fail={fail_count}, total={len(results)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_cookie_header(cookies: List[dict]) -> str:
    parts = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def build_proxy_url(config: CrawlConfig) -> Optional[str]:
    proxy_ip = config.proxy_ip.strip()
    proxy_port = config.proxy_port
    if not proxy_ip or proxy_port is None:
        return None

    proxy_scheme = (config.proxy_scheme or "socks5").strip()
    return f"{proxy_scheme}://{proxy_ip}:{proxy_port}"


def save_cookie_header(cookie_header: str, cookie_path: Path) -> None:
    payload = {
        "cookie_string": cookie_header,
        "last_updated": datetime.now().isoformat(),
        "status": "valid",
    }

    if cookie_path.exists():
        try:
            existing = json.loads(cookie_path.read_text(encoding="utf-8"))
            existing.update(payload)
            payload = existing
        except Exception:
            pass

    cookie_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def page_is_blocked(html: str) -> bool:
    if not html:
        return True
    lowered = html.lower()
    return any(signal in lowered for signal in BLOCKED_SIGNALS)


def has_product_cards(driver) -> bool:
    for selector in PRODUCT_CARD_SELECTORS:
        try:
            if driver.find_elements("css selector", selector):
                return True
        except Exception:
            continue
    return False


def snapshot_page(driver, out_dir: Path, tag: str) -> dict:
    snapshot = {
        "tag": tag,
        "url": driver.current_url,
        "title": driver.title,
        "cookies": [],
    }

    try:
        cookies = driver.get_cookies()
        snapshot["cookies"] = [c for c in cookies if c.get("name") in COOKIE_ALLOWLIST]
    except Exception:
        pass

    try:
        save_text(out_dir / f"{tag}.html", driver.page_source)
    except Exception:
        pass
    return snapshot


def prepare_browser_session(
    driver,
    config: CrawlConfig,
    debug_dir: Path,
    report: dict,
) -> Tuple[bool, str]:
    try:
        warmup_steps = [
            ("01_google", "https://www.google.com/", 1.0),
            ("02_coupang_main", f"{config.base_url}/", 1.0),
            ("03_coupang_category", config.category_url, 10.0),
        ]

        for tag, url, wait_sec in warmup_steps:
            driver.get(url)
            time.sleep(wait_sec)
            report["steps"].append(snapshot_page(driver, debug_dir, tag))

        try:
            html = driver.page_source or ""
        except Exception:
            html = ""

        if page_is_blocked(html) or not has_product_cards(driver):
            return False, ""

        cookies = driver.get_cookies()
        cookie_header = build_cookie_header(cookies)
        if not cookie_header:
            return False, ""

        save_cookie_header(cookie_header, config.cookie_path)
        print(f"[COOKIE] Updated: {config.cookie_path}")
        return True, cookie_header
    finally:
        time.sleep(2.0)
        try:
            driver.quit()
        except Exception:
            pass


def default_user_data_dir() -> Path:
    if Path("/.dockerenv").exists():
        return Path("/tmp") / "deal-sniffer-dogbot" / "chrome-profile"

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (
                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "User Data"
                / "Coupang_UC_Profile"
                / "TestProfile"
            )
        return Path.home() / "AppData" / "Local" / "deal-sniffer-dogbot" / "chrome-profile"

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Coupang_UC_Profile"
            / "TestProfile"
        )

    return Path.home() / ".config" / "deal-sniffer-dogbot" / "chrome-profile"


# Clp: Category Listing Page
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

    def fetch(self, category_id: str, page: int) -> dict:
        url = f"{self.config.base_url}/np/categories/{category_id}"
        params: Dict[str, Any] = {
            "listSize": self.config.list_size,
            "page": int(page),
        }
        if self.config.filter_type:
            params["filterType"] = self.config.filter_type

        headers = dict(self.DEFAULT_HEADERS)
        if int(page) > 1:
            headers["Referer"] = f"{self.config.base_url}/np/categories/{category_id}"

        request_cookies = None
        if self.config.use_cookie_header and self.cookie_header:
            headers["Cookie"] = self.cookie_header
        else:
            request_cookies = self._cookie_dict() or None
            headers.pop("Cookie", None)

        request_kwargs: Dict[str, Any] = {
            "params": params,
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
                url,
                **request_kwargs,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "request_info": {
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        return {
            "response": response,
            "request_info": {
                "url": str(response.url),
                "method": "GET",
                "timestamp": datetime.now().isoformat(),
                "category_id": category_id,
                "list_size": self.config.list_size,
                "page": int(page),
            },
        }


class ClpParser:
    def __init__(self, config: CrawlConfig):
        self.config = config
        ensure_directory(config.output_dir)

    def fetch_and_parse_clp(
        self,
        fetcher: ClpFetcher,
        category_id: str,
        page: int,
    ) -> dict:
        fetch_result = fetcher.fetch(category_id=category_id, page=page)
        if "error" in fetch_result:
            return fetch_result

        response = fetch_result["response"]
        result = {
            "request_info": fetch_result["request_info"],
            "response_info": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "cookies": dict(response.cookies) if response.cookies else {},
                "content_length": len(response.content),
            },
            "products": [],
        }

        if response.status_code != 200:
            return result

        html = response.text
        result["products"] = self.parse_clp_products(html)
        result["html_content_length"] = len(html)
        result["is_challenge_page"] = "chlgeId" in html or len(html) < 5000

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"parsed_{category_id}_{page}_{ts}.json"
        self.save_parsed_json(result, filename)
        return result

    def parse_clp_products(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        products = self._parse_clp_products_from_html(soup)
        json_ld_map = self._extract_json_ld_products(soup)

        for product in products:
            product_id = self._extract_product_id(product.get("url", ""))
            if not product_id:
                continue
            json_ld = json_ld_map.get(product_id)
            if not json_ld:
                continue

            if not product.get("price") and json_ld.get("price"):
                product["price"] = json_ld["price"]
            if not product.get("rating") and json_ld.get("rating"):
                product["rating"] = json_ld["rating"]
            if not product.get("review_count") and json_ld.get("review_count"):
                product["review_count"] = json_ld["review_count"]
            if not product.get("image") and json_ld.get("image"):
                product["image"] = json_ld["image"]

        return products

    def _parse_clp_products_from_html(self, soup: BeautifulSoup) -> List[dict]:
        products: List[dict] = []
        seen_urls = set()
        links = soup.find_all("a", href=re.compile(r"/vp/products/\d+"))

        for link in links:
            raw_href = str(link.get("href", "")).strip()
            if not raw_href:
                continue

            url = self._to_absolute_url(raw_href)
            if not url or url in seen_urls:
                continue

            parent = link.find_parent(["li", "div", "article"]) or link
            name = self._extract_name(parent, link)
            if not name or len(name) < 3:
                continue

            text = link.get_text(" ", strip=True)
            price = self._extract_price(parent, text)
            rating = self._extract_rating(parent)
            image = self._extract_image(parent, link)

            seen_urls.add(url)
            products.append(
                {
                    "position": len(products) + 1,
                    "name": name,
                    "url": url,
                    "image": image,
                    "price": price,
                    "currency": "KRW",
                    "rating": rating,
                    "review_count": None,
                }
            )

            if len(products) >= self.config.list_size:
                break

        return products

    def _extract_name(self, parent, link) -> Optional[str]:
        selectors = [
            "dt.name",
            "div.name",
            "span.name",
            "a.name",
            "h3",
            "h4",
            "dt",
            "[class*='name']",
            "[class*='title']",
        ]

        for selector in selectors:
            element = parent.select_one(selector)
            if not element:
                continue
            name = self._clean_name(element.get_text(" ", strip=True))
            if name:
                return name

        return self._clean_name(link.get_text(" ", strip=True))

    def _clean_name(self, text: str) -> Optional[str]:
        if not text:
            return None

        cleaned = re.sub(r"\d{1,3}(?:,\d{3})*\s*원.*$", "", text)
        cleaned = re.sub(r"\(?\d+.*리뷰.*\)?", "", cleaned)
        cleaned = re.sub(r"\(?\d+[,.]?\d*개.*\)?", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned or len(cleaned) < 3:
            return None
        if re.match(r"^\d+[,.]?\d*", cleaned):
            return None
        return cleaned

    def _extract_price(self, parent, fallback_text: str) -> Optional[int]:
        selectors = [
            "strong.price",
            "em.price",
            "span.price",
            "[class*='price']",
            "[class*='cost']",
            "strong",
            "em",
        ]

        for selector in selectors:
            element = parent.select_one(selector)
            if not element:
                continue
            price = self._parse_price_text(element.get_text(" ", strip=True))
            if price is not None:
                return price

        return self._parse_price_text(fallback_text)

    def _parse_price_text(self, text: str) -> Optional[int]:
        if not text:
            return None

        matches = re.findall(r"(\d{1,3}(?:,\d{3})*)\s*원", text)
        if not matches:
            return None

        prices = [int(value.replace(",", "")) for value in matches]
        if len(prices) >= 2 and prices[1] < prices[0]:
            return prices[1]
        return prices[-1]

    def _extract_rating(self, parent) -> Optional[float]:
        element = parent.select_one("[class*='rating'], [class*='star']")
        if not element:
            return None

        match = re.search(r"(\d+\.?\d*)", element.get_text(" ", strip=True))
        if not match:
            return None

        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _extract_image(self, parent, link) -> Optional[str]:
        img = parent.select_one("img") or link.select_one("img")
        if not img:
            return None

        src = img.get("src") or img.get("data-img-src") or img.get("data-src")
        if not src:
            return None

        src = str(src)
        if src.startswith("//"):
            return f"https:{src}"
        if src.startswith("/"):
            return f"{self.config.base_url}{src}"
        return src

    def _extract_json_ld_products(self, soup: BeautifulSoup) -> Dict[str, dict]:
        products: Dict[str, dict] = {}

        for script in soup.find_all("script", type="application/ld+json"):
            payload = script.string or script.get_text()
            if not payload:
                continue

            try:
                data = json.loads(payload)
            except Exception:
                continue

            if not isinstance(data, dict) or data.get("@type") != "ItemList":
                continue

            for item in data.get("itemListElement", []):
                if not isinstance(item, dict):
                    continue

                product = item.get("item", {})
                if not isinstance(product, dict):
                    continue

                product_url = str(product.get("url", ""))
                product_id = self._extract_product_id(product_url)
                if not product_id:
                    continue

                offers = product.get("offers", {})
                rating = product.get("aggregateRating", {})
                image_value = product.get("image")
                image = image_value[0] if isinstance(image_value, list) and image_value else image_value

                products[product_id] = {
                    "price": offers.get("price") if isinstance(offers, dict) else None,
                    "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
                    "review_count": rating.get("reviewCount") if isinstance(rating, dict) else None,
                    "image": image,
                }

        return products

    @staticmethod
    def _extract_product_id(url: str) -> Optional[str]:
        match = re.search(r"/vp/products/(\d+)", url)
        return match.group(1) if match else None

    def _to_absolute_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{self.config.base_url}{href}"
        return f"{self.config.base_url}/{href}"

    def save_parsed_json(self, data: dict, filename: str) -> str:
        output_path = self.config.output_dir / filename
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(output_path)


def crawl_pages(
    fetcher: ClpFetcher,
    parser: ClpParser,
    config: CrawlConfig,
    category_ids: List[str],
) -> Tuple[List[dict], bool]:
    results = []
    blocked = False

    for category_id in category_ids:
        if blocked:
            break

        category_pages = []
        total_products = 0
        success = False

        for page in config.pages:
            parsed = parser.fetch_and_parse_clp(fetcher, category_id, page)
            if "error" in parsed:
                status_code = None
                product_count = 0
            else:
                status_code = parsed.get("response_info", {}).get("status_code")
                product_count = len(parsed.get("products", []))

            total_products += product_count
            if status_code == 200 and product_count > 0:
                success = True

            category_pages.append(
                {
                    "page": page,
                    "status_code": status_code,
                    "products": product_count,
                }
            )

            if status_code == 403 or (status_code == 200 and product_count == 0):
                print(
                    f"[WARN] Blocked or empty response. status={status_code}, products={product_count}"
                )
                blocked = True
                break

            time.sleep(random.uniform(config.sleep_min_sec, config.sleep_max_sec))

        results.append(
            {
                "category_id": category_id,
                "success": success,
                "total_products": total_products,
                "pages": category_pages,
            }
        )

    return results, blocked


def run() -> int:
    args = parse_args()
    config = build_runtime_config(args)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_dir = config.debug_root_dir / f"debug_main_{timestamp}"
    ensure_directory(debug_dir)
    ensure_directory(config.output_dir)

    category_ids = load_category_ids(config.category_list_path)
    if not category_ids:
        print(f"[ERROR] category IDs are missing: {config.category_list_path}")
        return 1

    browser = AntiDetectionBrowser()
    report = {"steps": []}

    profile_dir = default_user_data_dir()
    ensure_directory(profile_dir)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    proxy_url = build_proxy_url(config)
    if proxy_url:
        options.add_argument(f"--proxy-server={proxy_url}")

    driver = browser.launch(custom_options=options)

    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})
        except Exception:
            pass

        session_ok, cookie_header = prepare_browser_session(
            driver,
            config,
            debug_dir,
            report,
        )
        if not session_ok:
            print("[WARN] Session preparation failed due to blocked/empty page.")
            return 1

        fetcher = ClpFetcher(config=config, cookie_header=cookie_header)
        parser = ClpParser(config=config)

        results, _ = crawl_pages(
            fetcher=fetcher,
            parser=parser,
            config=config,
            category_ids=category_ids,
        )

        report_path = config.output_dir / f"coupang_report_{timestamp}.txt"
        write_clp_report(report_path, results)
        print(f"[REPORT] Saved: {report_path}")

        debug_report_path = debug_dir / "debug_report.json"
        debug_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DEBUG] Saved: {debug_dir}")
        return 0
    finally:
        try:
            browser.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(run())
