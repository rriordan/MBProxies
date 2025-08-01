#!/usr/bin/env python3
import time
import csv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# === SETTINGS ===
PROXY_LIST_FILE        = "proxies.txt"
OUTPUT_CSV             = "proxy_results.csv"
TEST_URL               = "http://ipv4.download.thinkbroadband.com/5MB.zip"
TIMEOUT                = 10
CHUNK_SIZE             = 256 * 1024      # 256 KB chunks
DEFAULT_TOTAL_BYTES    = 5 * 1024 * 1024 # 5 MB
HIGH_SPEED_THRESHOLD   = 10.0            # MB/s
HIGH_SPEED_TOTAL_BYTES = 10 * 1024 * 1024# 10 MB
MAX_THREADS            = 20

def test_proxy(proxy: str, idx: int, total: int) -> dict:
    """Test latency & throughput, with logging."""
    print(f"[{idx}/{total}] Testing {proxy}...", flush=True)
    result = {"proxy": proxy, "latency_s": None, "speed_mb_s": None, "score": None}
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        start = time.time()
        resp = requests.get(TEST_URL, proxies=proxies, stream=True, timeout=TIMEOUT)
        resp.raise_for_status()

        first_chunk = next(resp.iter_content(chunk_size=CHUNK_SIZE), b'')
        latency = time.time() - start
        if not first_chunk:
            print(f"[{idx}/{total}] {proxy} – no data", flush=True)
            return result

        initial_speed = (len(first_chunk) / latency) / (1024*1024)
        total_bytes = HIGH_SPEED_TOTAL_BYTES if initial_speed > HIGH_SPEED_THRESHOLD else DEFAULT_TOTAL_BYTES

        downloaded = len(first_chunk)
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk or downloaded >= total_bytes:
                break
            downloaded += len(chunk)

        elapsed = time.time() - start
        speed_mb_s = (downloaded / elapsed) / (1024*1024)
        score = speed_mb_s / latency if latency > 0 else None

        result.update({
            "latency_s": round(latency, 3),
            "speed_mb_s": round(speed_mb_s, 3),
            "score": round(score, 3)
        })
        print(f"[{idx}/{total}] {proxy} → latency: {result['latency_s']}s, "
              f"speed: {result['speed_mb_s']}MB/s, score: {result['score']}", flush=True)
    except Exception as e:
        print(f"[{idx}/{total}] {proxy} FAILED: {e}", flush=True)
    return result

def load_proxies(path: str) -> list:
    print(f"Loading proxies from {path}...", flush=True)
    with open(path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(proxies)} proxies.", flush=True)
    return proxies

def save_results(results: list, path: str):
    print(f"Saving results to {path}...", flush=True)
    fieldnames = ["proxy", "latency_s", "speed_mb_s", "score"]
    with open(path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(results, key=lambda x: x["score"] or 0, reverse=True):
            writer.writerow(row)
    print("Save complete.", flush=True)

def main():
    proxies = load_proxies(PROXY_LIST_FILE)
    if not proxies:
        print("No proxies to test – exiting.", flush=True)
        return
    results = []
    total = len(proxies)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {
            executor.submit(test_proxy, p, idx+1, total): p
            for idx, p in enumerate(proxies)
        }
        for future in as_completed(futures):
            res = future.result()
            if res["score"] is not None:
                results.append(res)

    save_results(results, OUTPUT_CSV)
    print(f"Tested {len(results)}/{total} successful proxies.", flush=True)

if __name__ == "__main__":
    main()
