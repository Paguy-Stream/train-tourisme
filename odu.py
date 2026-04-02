import aiohttp
import asyncio
from bs4 import BeautifulSoup

BASE = "https://www.ecovelo.mobi"
TIMEOUT = aiohttp.ClientTimeout(total=8)

async def fetch(session, url):
    try:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            return await r.text()
    except:
        return None

async def fetch_json(session, url):
    try:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            return await r.json()
    except:
        return None

async def discover_ecovelo():
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        html = await fetch(session, BASE)
        if not html:
            print("❌ Impossible de charger ecovelo.mobi")
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)

        systems = []
        for a in links:
            href = a["href"]
            if "/opendata/" in href or "/gbfs" in href:
                continue

            if href.startswith("/"):
                city = href.strip("/").lower()
                manifest = f"https://api.gbfs.ecovelo.mobi/{city}/gbfs.json"
                systems.append((city, manifest))

        # Test des systèmes
        results = []
        for city, url in systems:
            data = await fetch_json(session, url)
            if data:
                results.append({
                    "id": city,
                    "url": url,
                    "version": data.get("version", "unknown"),
                    "feeds": [f["name"] for f in data["data"]["feeds"]]
                })

        return results

if __name__ == "__main__":
    systems = asyncio.run(discover_ecovelo())
    print("=== SYSTÈMES ECOVELO DÉTECTÉS ===")
    for s in systems:
        print(f" - {s['id']} ({s['version']}) → {s['url']}")
