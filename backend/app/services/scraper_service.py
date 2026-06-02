import httpx
from bs4 import BeautifulSoup


async def fetch_and_extract(url: str) -> dict:
    headers = {
        "User-Agent": "DecentraKnow/0.1 (Knowledge Indexer)"
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = ""
    if soup.title:
        title = soup.title.string or ""

    article = soup.find("article") or soup.find("main") or soup.body
    if article is None:
        article = soup

    text = article.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    return {
        "url": url,
        "title": title.strip(),
        "content": clean_text,
        "word_count": len(clean_text.split()),
    }
