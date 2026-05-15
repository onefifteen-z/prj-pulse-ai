import requests
import time
from bs4 import BeautifulSoup

HN_API = "https://hacker-news.firebaseio.com/v0"

def clean_html(text):
    return BeautifulSoup(text, "html.parser").get_text()

def fetch_item(id):
    return requests.get(f"{HN_API}/item/{id}.json").json()

def fetch_top_ai(limit=20):
    ids = requests.get(f"{HN_API}/topstories.json").json()
    results = []
    now = time.time()

    for id in ids[:50]:
        item = fetch_item(id)
        if not item or item.get("type") != "story":
            continue

        if now - item.get("time", 0) > 60 * 60 * 48:
            continue

        title = item.get("title", "").lower()
        if not any(k in title for k in ["ai", "gpt", "llm", "agent", "model"]):
            continue

        comments = []
        for cid in item.get("kids", [])[:3]:
            c = fetch_item(cid)
            if c and "text" in c:
                comments.append(clean_html(c["text"]))

        results.append({
            "title": item["title"],
            "url": item.get("url"),
            "points": item.get("score"),
            "comments": item.get("descendants"),
            "comments_text": comments
        })

        if len(results) >= limit:
            break

    return results
