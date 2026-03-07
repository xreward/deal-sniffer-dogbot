import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from ..config import CrawlConfig
from ..io import ensure_directory


class ClpParser:
    def __init__(self, config: CrawlConfig):
        self.config = config
        ensure_directory(config.output_dir)

    def parse_fetch_result(self, fetch_result: dict) -> dict:
        if "error" in fetch_result:
            return fetch_result

        request_info = dict(fetch_result.get("request_info", {}))
        response_info = dict(fetch_result.get("response_info", {}))

        result = {
            "request_info": request_info,
            "response_info": response_info,
            "products": [],
        }

        status_code = response_info.get("status_code")
        if status_code != 200:
            return result

        html = str(fetch_result.get("html", ""))
        result["products"] = self.parse_clp_products(html)
        result["html_content_length"] = len(html)
        result["is_challenge_page"] = "chlgeId" in html or len(html) < 5000

        target_url = request_info.get("target_url") or request_info.get("url", "")
        category_id = self._extract_category_id(str(target_url))
        page = self._extract_page(str(target_url))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"parsed_{category_id}_{page}_{ts}.json"
        self.save_parsed_json(result, filename)
        return result

    def fetch_and_parse_clp(self, fetcher, target_url: str) -> dict:
        return self.parse_fetch_result(fetcher.fetch(target_url=target_url))

    @staticmethod
    def _extract_category_id(url: str) -> str:
        match = re.search(r"/np/categories/(\d+)", url)
        return match.group(1) if match else "unknown"

    @staticmethod
    def _extract_page(url: str) -> str:
        match = re.search(r"[?&]page=(\d+)", url)
        return match.group(1) if match else "na"

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
