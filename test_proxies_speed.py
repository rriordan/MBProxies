import requests
from time import time
from concurrent.futures import ThreadPoolExecutor
import csv

# SETTINGS
PROXY_FILE = "TestProxies.txt"
GOOD_FILE = "working-fast.txt"
BAD_FILE = "bad.txt"
CSV_FILE = "results.csv"
TEST_URL = "http://ipv4.download.thinkbroadband.com/100MB.zip"
TIMEOUT = 11  # seconds
CHUNK_SIZE = 64 * 1024  # 64 KB
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_THREADS = 125

good = []
bad = []
csv_rows = []

# 🧠 Port-based proxy type detection
def detect_scheme(proxy):
    port = proxy.split(":")[-1]
    if port in {"9050", "9150", "1080"}:
        return "socks5"
    elif port in {"1081", "1084"}:
        return "socks4"
    else:
        return "http"

def test_proxy(proxy):
    scheme = detect_scheme(proxy)
    proxy_dict = {
        "http": f"{scheme}://{proxy}",
        "https": f"{scheme}://{proxy}",
    }

    try:
        # HEAD request for latency
        start_latency = time()
        r = requests.head(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT)
        latency = time() - start_latency
        if r.status_code != 200:
            raise Exception(f"Non-200 HEAD response: {r.status_code}")

        # GET request for download speed (10MB)
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

        print(f"[+] {proxy} ({scheme}) - Latency: {latency:.2f}s - 10MB in {download_time:.2f}s - {speed_mbps} MB/s - Score: {score}")
        good.append(f"{proxy} ({scheme})  # latency={latency:.2f}s, 10MB={download_time:.2f}s, speed={speed_mbps}MB/s, score={score}")
        csv_rows.append([proxy, scheme, round(latency, 3), round(download_time, 3), speed_mbps, score])

    except Exception as e:
        print(f"[x] {proxy} ({scheme}) - FAIL: {e}")
        bad.append(proxy)

def main():
    with open(PROXY_FILE, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.map(test_proxy, proxies)

    with open(GOOD_FILE, "w") as f:
        f.write("\n".join(good))

    with open(BAD_FILE, "w") as f:
        f.write("\n".join(bad))

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Proxy", "Type", "Latency (s)", "10MB Download Time (s)", "Speed (MB/sec)", "Score"])
        writer.writerows(csv_rows)

    print(f"\n✅ FINISHED: {len(good)} good, {len(bad)} bad proxies")
    print(f"→ Good saved to: {GOOD_FILE}")
    print(f"→ Bad saved to: {BAD_FILE}")
    print(f"→ CSV saved to: {CSV_FILE}")

if __name__ == "__main__":
    main()
