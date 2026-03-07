import argparse

from .config import CrawlConfig, DEFAULT_CONFIG, PROXY_IP, PROXY_PORT, PROXY_SCHEME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coupang category crawler")
    parser.add_argument(
        "--mode",
        choices=["fetcher", "parser"],
        default="fetcher",
        help="Execution mode: fetcher pushes HTML to Redis, parser consumes Redis.",
    )
    parser.add_argument(
        "--category-url",
        default=DEFAULT_CONFIG.category_url,
        help="Session bootstrap category URL",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers for target URLs (default: 4)",
    )
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace) -> CrawlConfig:
    return CrawlConfig(
        category_url=str(args.category_url),
        proxy_ip=PROXY_IP,
        proxy_port=PROXY_PORT,
        proxy_scheme=PROXY_SCHEME,
    )
