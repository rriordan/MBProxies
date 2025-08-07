import aiohttp
import asyncio
import csv
from time import perf_counter
from tqdm.asyncio import tqdm

# SETTINGS
PROXY_FILE_HTTP   = "TestProxies.txt"
PROXY_FILE_SOCKS5 = "Socks5.txt"
PROXY_FILE_SOCKS4 = "Socks4.txt"
CSV_FILE          = "results.csv"
GOOD_FILE         = "working-fast.txt"
BAD_FILE          = "bad.txt"
TOP_N_FILE        = "TopProxies.txt"
ROTATION_FILE     = "RotationList.txt"

TEST_URL          = "http://ipv4.download.thinkbroadband.com/100MB.zip"
CHUNK_RANGE       = "bytes=0-10485759"  # first 10 MB
TIMEOUT           = 10                  # seconds
CONCURRENT_LIMIT  = 200                 # max simultaneous tasks
TOP_N_COUNT       = 150                 # number of top proxies to select

# GLOBAL RESULTS
good, bad, csv_rows = [], [], []

# Throttle total concurrency
sem = asyncio.Semaphore(CONCURRENT_LIMIT)

async def try_proxy(session, proxy: str, scheme: str) -> tuple:
    """
    Test a single proxy: download ~10MB, measure latency & speed,
    compute score = speed / (latency + 0.01).
    Returns (result_str, proxy, scheme, score)
    """
    proxy_url = f"{scheme}://{proxy}"
    headers   = {"Range": CHUNK_RANGE}
    try:
        async with sem:
            start = perf_counter()
            async with session.get(TEST_URL, headers=headers, proxy=proxy_url, timeout=TIMEOUT) as resp:
                if resp.status not in (200, 206):
                    raise Exception(f"HTTP {resp.status}")
                total = 0
                # read up to 10MB
                async for chunk in resp.content.iter_chunked(65536):
                    total += len(chunk)
                    if total >= 10 * 1024 * 1024:
                        break
                elapsed = perf_counter() - start
                speed   = total / elapsed / 1024 / 1024   # MB/s
                latency = elapsed
                score   = speed / (latency + 0.01)        # MB/s per sec
                good.append(proxy)
                csv_rows.append([proxy, scheme, latency, speed, score])
                return f"[+] {proxy} ({scheme}) – {speed:.2f} MB/s @ {latency:.3f}s → Score {score:.2f}", proxy, scheme, score
    except Exception as e:
        bad.append(proxy)
        return f"[-] {proxy} ({scheme}) – ✖ {e}", proxy, scheme, 0.0

async def run_tests(proxies: list[str], scheme: str) -> list[tuple]:
    """
    Run try_proxy() on all proxies of a given scheme concurrently.
    """
    connector = aiohttp.TCPConnector(ssl=False, limit=None)
    timeout   = aiohttp.ClientTimeout(total=TIMEOUT)
    results   = []
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [try_proxy(session, p, scheme) for p in proxies]
        for coro in tqdm(asyncio.as_completed(tasks),
                         total=len(tasks),
                         desc=f"Testing {scheme.upper()}",
                         unit="proxy"):
            res = await coro
            results.append(res)
    return results

def load_proxies(path: str) -> list[str]:
    """
    Read non-empty lines from a proxy file.
    """
    try:
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

async def main():
    t0 = perf_counter()

    http_list   = load_proxies(PROXY_FILE_HTTP)
    socks5_list = load_proxies(PROXY_FILE_SOCKS5)
    socks4_list = load_proxies(PROXY_FILE_SOCKS4)

    all_results = []
    all_results += await run_tests(http_list,   "http")
    all_results += await run_tests(socks5_list, "socks5")
    all_results += await run_tests(socks4_list, "socks4")

    elapsed = perf_counter() - t0

    # 1) Sort CSV rows by score descending
    sorted_rows = sorted(csv_rows, key=lambda r: r[4], reverse=True)

    # 2) Write full sorted CSV
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Proxy","Protocol","Latency (s)","Speed (MB/s)","Score"])
        for proxy, scheme, lat, spd, sc in sorted_rows:
            writer.writerow([proxy, scheme, f"{lat:.3f}", f"{spd:.2f}", f"{sc:.2f}"])

    # 3) Top-N filtering → TopProxies.txt
    top_n = sorted_rows[:TOP_N_COUNT]
    with open(TOP_N_FILE, "w") as f:
        for proxy, scheme, *_ in top_n:
            f.write(f"{scheme}://{proxy}\n")

    # 4) Auto rotation list (round-robin order) → RotationList.txt
    with open(ROTATION_FILE, "w") as f:
        for proxy, scheme, *_ in sorted_rows:
            f.write(f"{scheme}://{proxy}\n")

    # Summary
    print("\n🔍 Test Summary:")
    print(f"✅ Good proxies: {len(good)} → {GOOD_FILE}")
    print(f"❌ Bad proxies:  {len(bad)} → {BAD_FILE}")
    print(f"📊 CSV report:   {CSV_FILE}")
    print(f"🏆 Top {TOP_N_COUNT}:      {TOP_N_FILE}")
    print(f"🔄 Rotation list: {ROTATION_FILE}")
    print(f"⏱️ Total time:    {elapsed:.2f}s\n")

    # Print per-proxy results
    for line, *_ in all_results:
        print(line)

if __name__ == "__main__":
    asyncio.run(main())
