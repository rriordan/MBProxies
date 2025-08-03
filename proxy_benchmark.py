import requests
from time import time, perf_counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import csv

# SETTINGS
PROXY_FILE_HTTP = "TestProxies.txt"
PROXY_FILE_SOCKS5 = "Socks5.txt"
PROXY_FILE_SOCKS4 = "Socks4.txt"
CSV_FILE = "results.csv"
GOOD_FILE = "working-fast.txt"
BAD_FILE = "bad.txt"
TEST_URL = "http://ipv4.download.thinkbroadband.com/100MB.zip"
CHUNK_RANGE = "bytes=0-10485759"  # First 10MB
TIMEOUT = 8
MAX_THREADS = 125

good, bad, csv_rows = [], [], []

def try_proxy(proxy, scheme):
    proxies = {
        "http": f"{scheme}://{proxy}",
        "https": f"{scheme}://{proxy}"
    }
    headers = {"Range": CHUNK_RANGE}
    try:
        start = time()
        response = requests.get(TEST_URL, headers=headers, proxies=proxies, stream=True, timeout=TIMEOUT)
        response.raise_for_status()
        total = 0
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total >= 10 * 1024 * 1024:
                break
        elapsed = time() - start
        speed = total / elapsed / 1024 / 1024  # MB/s
        latency = response.elapsed.total_seconds()
        score = speed / (latency + 0.01)
        good.append(proxy)
        csv_rows.append([proxy, scheme, f"{latency:.3f}", f"{speed:.2f}", f"{score:.2f}"])
        return f"[+] {proxy} ({scheme}) - ✅ {speed:.2f} MB/s @ {latency:.3f}s -> Score: {score:.2f}"
    except Exception:
        bad.append(proxy)
        return f"[-] {proxy} ({scheme}) - ❌ Failed"

def load_proxies(filename):
    try:
        with open(filename) as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

def main():
    print("🧪 Starting proxy benchmark...\n")
    start_time = perf_counter()
    results = []

    http_proxies = load_proxies(PROXY_FILE_HTTP)
    socks5_proxies = load_proxies(PROXY_FILE_SOCKS5)
    socks4_proxies = load_proxies(PROXY_FILE_SOCKS4)

    all_tasks = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        for proxy in http_proxies:
            all_tasks.append(executor.submit(try_proxy, proxy, "http"))
        for proxy in socks5_proxies:
            all_tasks.append(executor.submit(try_proxy, proxy, "socks5"))
        for proxy in socks4_proxies:
            all_tasks.append(executor.submit(try_proxy, proxy, "socks4"))

        with tqdm(total=len(all_tasks), desc="Progress", unit="proxy") as pbar:
            for future in as_completed(all_tasks):
                result = future.result()
                results.append(result)
                pbar.update(1)

    duration = perf_counter() - start_time

    with open(GOOD_FILE, "w") as f:
        f.write("\n".join(good))
    with open(BAD_FILE, "w") as f:
        f.write("\n".join(bad))
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Proxy", "Protocol", "Latency (s)", "Speed (MB/s)", "Score"])
        for row in csv_rows:
            writer.writerow(row)

    print("\n🔍 Test Summary:")
    print(f"✅ Good proxies: {len(good)}")
    print(f"❌ Bad proxies: {len(bad)}")
    print(f"📊 CSV saved to: '{CSV_FILE}'")
    print(f"⏱️ Elapsed time: {duration:.2f}s\n")

    for r in results:
        print(r)

if __name__ == "__main__":
    main()
