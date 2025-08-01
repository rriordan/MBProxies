import requests
from time import time
from concurrent.futures import ThreadPoolExecutor
import threading
import csv

# SETTINGS
PROXY_FILE = "TestProxies.txt"
GOOD_FILE = "working-fast.txt"
BAD_FILE = "bad.txt"
CSV_FILE = "results.csv"
TEST_URL = "http://ipv4.download.thinkbroadband.com/100MB.zip"
TIMEOUT = 12
CHUNK_SIZE = 64 * 1024
MAX_BYTES = 10 * 1024 * 1024
MAX_THREADS = 125
SAVE_INTERVAL = 5000  # Save results after every N proxies

good = []
bad = []
csv_rows = []

progress_count = 0
start_time = time()
progress_lock = threading.Lock()

def detect_scheme(proxy):
    port = proxy.split(":")[-1]
    if port in {"9050", "9150", "1080"}:
        return "socks5"
    elif port in {"1081", "1084"}:
        return "socks4"
    else:
        return "http"

def save_progress():
    with open(GOOD_FILE, "w") as f:
        f.write("\n".join(good))
    with open(BAD_FILE, "w") as f:
        f.write("\n".join(bad))
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Proxy", "Type", "Latency (s)", "10MB Download Time (s)", "Speed (MB/sec)", "Score"])
        writer.writerows(csv_rows)

def test_proxy(proxy):
    global progress_count
    scheme = detect_scheme(proxy)
    proxy_dict = {
        "http": f"{scheme}://{proxy}",
        "https": f"{scheme}://{proxy}",
    }

    proxy_start = time()

    try:
        start_latency = time()
        r = requests.head(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT)
        latency = time() - start_latency
        if r.status_code != 200:
            raise Exception(f"Non-200 HEAD response: {r.status_code}")

        start_download = time()
        r = requests.get(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT, stream=True)
        downloaded = 0
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            downloaded += len(chunk)
            if downloaded >= MAX_BYTES:
                break
        download_time = time() - start_download

        speed_mbps = round(10 / download_time, 3)
        score = round(speed_mbps / latency, 3) if latency > 0 else 0

        with progress_lock:
            good.append(f"{proxy} ({scheme})  # latency={latency:.2f}s, 10MB={download_time:.2f}s, speed={speed_mbps}MB/s, score={score}")
            csv_rows.append([proxy, scheme, round(latency, 3), round(download_time, 3), speed_mbps, score])
            progress_count += 1

    except Exception as e:
        with progress_lock:
            bad.append(proxy)
            progress_count += 1
            print(f"[x] {proxy} ({scheme}) - FAIL: {e}", end=" ")

    with progress_lock:
        elapsed = time() - start_time
        avg_time = elapsed / progress_count if progress_count > 0 else 0
        remaining = total_proxies - progress_count
        eta = remaining * avg_time
        eta_fmt = f"{int(eta // 60)}m {int(eta % 60)}s" if eta >= 60 else f"{int(eta)}s"
        print(f"✔ {progress_count}/{total_proxies}  ⏳ ETA: {eta_fmt}")

        if progress_count % SAVE_INTERVAL == 0 or progress_count == total_proxies:
            save_progress()

def main():
    global total_proxies
    with open(PROXY_FILE, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    total_proxies = len(proxies)

    print(f"🚀 Starting {total_proxies} proxy tests with {MAX_THREADS} threads...\n")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.map(test_proxy, proxies)

    save_progress()
    print(f"\n✅ FINISHED: {len(good)} good, {len(bad)} bad proxies")
    print(f"→ Good saved to: {GOOD_FILE}")
    print(f"→ Bad saved to: {BAD_FILE}")
    print(f"→ CSV saved to: {CSV_FILE}")

if __name__ == "__main__":
    main()
