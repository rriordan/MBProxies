#!/usr/bin/env python3
import time
import csv
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# === SETTINGS ===
PROXY_LIST_FILE        = "TestProxies.txt"                # one per line: host:port or scheme://host:port
OUTPUT_CSV             = "proxy_results.csv"
TEST_URL               = "http://ipv4.download.thinkbroadband.com/5MB.zip"
TIMEOUT                = 10                           # seconds before giving up
CHUNK_SIZE             = 256 * 1024                  # 256 KB per chunk
DEFAULT_TOTAL_BYTES    = 5 * 1024 * 1024             # 5 MB default
HIGH_SPEED_THRESHOLD   = 10.0                        # MB/s threshold
HIGH_SPEED_TOTAL_BYTES = 10 * 1024 * 1024            # 10 MB for fast proxies
MAX_THREADS            = 20                          # concurrency level

# === LOGGING SETUP ===
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger()

def parse_proxy_entry(entry: str):
    """
    Parse a line into (scheme, address).
    - Explicit schemes (http://, https://, socks4://, socks5://) are honored.
    - Otherwise autodetect by port for SOCKS4/5 or default to HTTP.
    """
    if "://" in entry:
        scheme, address = entry.split("://", 1)
        return scheme, address
    port = entry.split(":")[-1]
    if port in {"1080", "9050", "9150"}:
        return "socks5", entry
    if port in {"1081", "1084"}:
        return "socks4", entry
    return "http", entry

def test_proxy(entry: str, idx: int, total: int) -> dict:
    """
    Test a proxy’s latency & throughput, logging progress.
    Returns: dict(proxy, latency_s, speed_mb_s, score).
    """
    scheme, address = parse_proxy_entry(entry)
    proxies = {
        "http":  f"{scheme}://{address}",
        "https": f"{scheme}://{address}"
    }
    log.info(f"[{idx}/{total}] Testing {entry} (scheme={scheme})")
    result = {"proxy": entry, "latency_s": None, "speed_mb_s": None, "score": None}
    try:
        start = time.time()
        resp = requests.get(TEST_URL, proxies=proxies, stream=True, timeout=TIMEOUT)
        resp.raise_for_status()

        # 1️⃣ First chunk → measure latency & initial speed
        first = next(resp.iter_content(chunk_size=CHUNK_SIZE), b'')
        latency = time.time() - start
        if not first:
            log.info(f"[{idx}/{total}] {entry} – no data received")
            return result

        initial_speed = (len(first) / latency) / (1024 * 1024)  # MB/s
        total_bytes = HIGH_SPEED_TOTAL_BYTES if initial_speed > HIGH_SPEED_THRESHOLD else DEFAULT_TOTAL_BYTES

        # 2️⃣ Continue download up to total_bytes
        downloaded = len(first)
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk or downloaded >= total_bytes:
                break
            downloaded += len(chunk)

        elapsed = time.time() - start
        speed_mb_s = (downloaded / elapsed) / (1024 * 1024)
        score = speed_mb_s / latency if latency > 0 else None

        result.update({
            "latency_s": round(latency, 3),
            "speed_mb_s": round(speed_mb_s, 3),
            "score": round(score, 3)
        })
        log.info(
            f"[{idx}/{total}] {entry} → latency: {result['latency_s']}s, "
            f"speed: {result['speed_mb_s']} MB/s, score: {result['score']}"
        )
    except Exception as e:
        log.info(f"[{idx}/{total}] {entry} FAILED: {e}")
    return result

def load_proxies(path: str) -> list:
    with open(path) as f:
        entries = [line.strip() for line in f if line.strip()]
    log.info(f"Loaded {len(entries)} proxies from '{path}'")
    return entries

def save_results(results: list, path: str):
    fieldnames = ["proxy", "latency_s", "speed_mb_s", "score"]
    with open(path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda x: x["score"] or 0, reverse=True):
            writer.writerow(row)
    log.info(f"Results saved to '{path}'")

def main():
    entries = load_proxies(PROXY_LIST_FILE)
    total = len(entries)
    if total == 0:
        log.info("No proxies to test – exiting.")
        return

    log.info(f"🚀 Starting tests for {total} proxies...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {
            executor.submit(test_proxy, e, idx+1, total): e
            for idx, e in enumerate(entries)
        }
        for future in as_completed(futures):
            res = future.result()
            if res["score"] is not None:
                results.append(res)

    save_results(results, OUTPUT_CSV)
    log.info(f"✅ Completed {len(results)}/{total} successful tests.")

if __name__ == "__main__":
    main()
