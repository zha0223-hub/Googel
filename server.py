"""Googel backend (free-hosting version).
1. Theme check with WordNet FIRST. Off-theme words never trigger a search.
2. Search the web (DuckDuckGo via the free `ddgs` package, no API key).
3. Visit the top pages and count how often the word appears.
Local run: pip install -r requirements.txt && python server.py  ->  http://localhost:5000"""
import json, os, re
from concurrent.futures import ThreadPoolExecutor

import nltk, requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from flask import Flask, jsonify, request, send_from_directory
from nltk.corpus import wordnet as wn

try:
    wn.ensure_loaded()
except LookupError:
    nltk.download("wordnet", quiet=True)

app = Flask(__name__)
MAX_PAGES = 8
SKIP = ("google.", "youtube.", "gstatic.")
# theme key -> (search noun, WordNet categories the word must fall under)
THEMES = {
    "animal": ("animal", ["animal.n.01"]),
    "plant": ("plant", ["plant.n.02"]),
    "food": ("food", ["food.n.01", "food.n.02", "edible_fruit.n.01", "dish.n.02", "vegetable.n.01", "baked_goods.n.01"]),
    "fruit": ("fruit", ["edible_fruit.n.01", "fruit.n.01"]),
    "sport": ("sport", ["sport.n.01", "game.n.01", "athletic_game.n.01", "play.n.17"]),
    "instrument": ("musical instrument", ["musical_instrument.n.01"]),
    "country": ("country", ["country.n.02"]),
    "city": ("city", ["city.n.01"]),
    "language": ("language", ["language.n.01"]),
    "color": ("color", ["color.n.01"]),
}
CACHE_FILE = "cache.json"
cache = json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}


def on_theme(word, cats):
    targets = {wn.synset(c) for c in cats}
    for s in wn.synsets(word.replace(" ", "_"), pos=wn.NOUN):
        if s in targets or targets & set(s.closure(lambda a: a.hypernyms() + a.instance_hypernyms())):
            return True
    return False


def scan(args):
    url, word_re, noun_re = args
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        text = soup.get_text(" ")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        return {"url": url, "title": title[:90], "count": len(word_re.findall(text)),
                "theme": bool(noun_re.search(text))}
    except Exception:
        return None


@app.get("/api/score")
def score():
    word = request.args.get("word", "").strip().lower()
    theme = request.args.get("theme", "").strip().lower()
    if theme not in THEMES:
        return jsonify(ok=False, error="Unknown theme.")
    if not re.fullmatch(r"[^\W\d_]+(?:['-][^\W\d_]+)*", word):
        return jsonify(ok=False, error="One word only, letters only.")
    noun, cats = THEMES[theme]
    if not on_theme(word, cats):                      # no search happens for off-theme words
        return jsonify(ok=False, error="“%s” isn’t a %s. Try another word. No attempt used." % (word, theme))
    key = word + "|" + theme
    try:
        if key not in cache:
            hits = DDGS().text(word + " " + noun, max_results=15)
            urls = []
            for h in hits:
                u = h.get("href", "")
                if u.startswith("http") and not any(s in u for s in SKIP) and u not in urls:
                    urls.append(u)
            word_re = re.compile(r"\b" + re.escape(word) + r"\b", re.I)
            noun_re = re.compile(r"\b" + re.escape(noun) + r"s?\b", re.I)
            with ThreadPoolExecutor(6) as ex:
                pages = [p for p in ex.map(scan, [(u, word_re, noun_re) for u in urls[:MAX_PAGES]]) if p]
            total = sum(p["count"] for p in pages)
            cache[key] = {"total": total, "valid": total > 0, "pages": pages}
            try:
                json.dump(cache, open(CACHE_FILE, "w"))
            except OSError:
                pass
        return jsonify(ok=True, **cache[key])
    except Exception as e:
        return jsonify(ok=False, error="Search failed, try again in a moment. (%s)" % e)


@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    return r


@app.get("/health")
def health():
    return "ok"


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
