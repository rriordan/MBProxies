import requests
from time import time
from concurrent.futures import ThreadPoolExecutor

# SETTINGS
PROXY_FILE = "proxies.txt"
GOOD_FILE = "working-fast.txt"
BAD_FILE = "bad.txt"
TEST_URL = "http://example.com"
TIMEOUT = 8  # seconds
MAX_THREADS = 50  # adjust depending on your system

good = []
bad = []

def test_proxy(proxy):
    proxy_dict = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    try:
        start = time()
        r = requests.get(TEST_URL, proxies=proxy_dict, timeout=TIMEOUT)
        elapsed = time() - start
        if r.status_code == 200:
            print(f"[+] {proxy} - {elapsed:.2f}s")
            return (proxy, elapsed)
        else:
            print(f"[-] {proxy} - HTTP {r.status_code}")
            return (proxy, None)
    except Exception as e:
        print(f"[x] {proxy} - ERROR: {str(e)}")
        return (proxy, None)

def main():
    with open(PROXY_FILE, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = executor.map(test_proxy, proxies)

    for proxy, speed in results:
        if speed is not None:
            good.append(f"{proxy}  # {speed:.2f}s")
        else:
            bad.append(proxy)

    with open(GOOD_FILE, "w") as f:
        f.write("\n".join(good))

    with open(BAD_FILE, "w") as f:
        f.write("\n".join(bad))

    print(f"\n✅ Done! {len(good)} working, {len(bad)} bad proxies.\nSaved to:")
    print(f"- {GOOD_FILE}")
    print(f"- {BAD_FILE}")

if __name__ == "__main__":
    main()
