# deal-sniffer-dogbot

## Redis-based fetcher/parser split

Install dependencies including Redis client:

```bash
pip install redis
```

### 1) Run fetcher (collect HTML -> push to Redis queue)

```bash
python src/crawler.py \
  --mode fetcher
```

### 2) Run parser (consume queue -> parse -> save output)

```bash
python src/crawler.py \
  --mode parser
```

Fixed Redis/parser settings are defined in `src/crawler/config.py`:

```bash
redis_host=127.0.0.1
redis_port=6379
redis_db=0
redis_queue_key=deal_sniffer:clp:raw_html
parser_consume_count=100
parser_block_timeout_sec=5
```
