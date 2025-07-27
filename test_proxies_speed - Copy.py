import requests
from time import time
from concurrent.futures import ThreadPoolExecutor

# SETTINGS
PROXY_FILE = "proxies.txt"
GOOD_FILE = "working-fast.txt"
BAD_FILE = "bad.txt"
TEST_URL = "http://ipv4.download.thinkbroadband.com/100MB.zip"  # Replace with another large file if needed
TIMEOUT = 5  # seconds
CHUNK_SIZE = 1024  # 1 KB
MAX_BYTES = 500 * 1024  # 500 KB
MAX_THREADS = 50  # Tune based on your system

good = []
bad = []

def test_proxy(proxy):
    proxy_dict = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        # First: latency check (HEAD request)
        start_latency = time()
        r = requests.head(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT)
        latency = time() - start_latency
        if r.status_code != 200:
            raise Exception(f"Non-200 HEAD response: {r.status_code}")

        # Then: download first 500KB
        start_download = time()
        r = requests.get(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT, stream=True)
        downloaded = 0
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            downloaded += len(chunk)
            if downloaded >= MAX_BYTES:
                break
        download_time = time() - start_download

        print(f"[+] {proxy} - Latency: {latency:.2f}s - DL 500KB in {download_time:.2f}s")
        good.append(f"{proxy}  # latency={latency:.2f}s, 500KB={download_time:.2f}s")
    except Exception as e:
        print(f"[x] {proxy} - FAIL: {e}")
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

    print(f"\n✅ FINISHED: {len(good)} good, {len(bad)} bad proxies")
    print(f"→ Good saved to: {GOOD_FILE}")
    print(f"→ Bad saved to: {BAD_FILE}")

if __name__ == "__main__":
    main()
