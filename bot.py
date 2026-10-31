#!/usr/bin/env python3
"""Best-effort public campaign-page monitor; does not bypass site protections."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "sources.json"
STATE_FILE = ROOT / "state.json"
USER_AGENT = "PersonalDealPageMonitor/0.1 (public campaign pages; respects robots.txt)"
TIMEOUT = 20
PRICE_RE = re.compile(
    r"(?<![\d.,])((?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[.,]\d{1,2})?)\s*(?:TL|₺)",
    re.IGNORECASE,
)
DISCOUNT_HINT_RE = re.compile(r"%\s*\d+|indirim|kampanya|fırsat|firsat|kupon|kaçmaz|kazanç", re.I)
TRACKING_KEYS = ("utm_", "ref", "tag", "campaign", "tracking", "source")


def fetch(url: str, *, accept: str = "text/html,application/xhtml+xml") -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2048), dict(exc.headers.items()) if exc.headers else {}


def robots_allows(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    robots_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    status, body, _ = fetch(robots_url, accept="text/plain,*/*")
    if status == 404:
        return True
    if status != 200:
        # Fail closed on a blocked or unavailable robots policy; never retry with stealth/browser tricks.
        return False
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT, url)


def canonical_url(href: str, base_url: str) -> str:
    absolute = urllib.parse.urljoin(base_url, href)
    p = urllib.parse.urlsplit(absolute)
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not any(k.lower().startswith(x) for x in TRACKING_KEYS)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", urllib.parse.urlencode(query), ""))


def _normalize_amount(raw: str) -> float | None:
    raw = re.sub(r"\s+", "", raw)
    if "." in raw and "," in raw:
        # Whichever separator appears last is the decimal separator.
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[1]
        raw = raw.replace(",", ".") if len(tail) in (1, 2) else raw.replace(",", "")
    elif "." in raw:
        tail = raw.rsplit(".", 1)[1]
        if len(tail) == 3:
            raw = raw.replace(".", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def parse_price(text: str) -> float | None:
    matches = PRICE_RE.findall(text)
    if not matches:
        return None
    return _normalize_amount(matches[-1])


def _price_from_structured(card: Any) -> float | None:
    selectors = [
        '[itemprop="price"]',
        'meta[property="product:price:amount"]',
        '[data-price]',
    ]
    for selector in selectors:
        for node in card.select(selector):
            raw = node.get("content") or node.get("data-price") or node.get_text(" ", strip=True)
            if raw:
                # Structured price values often omit the currency suffix.
                digits = re.sub(r"[^0-9,.]", "", str(raw))
                if digits:
                    normalized = _normalize_amount(digits)
                    if normalized is not None:
                        return normalized
    return None


def _matches_product_url(url: str, source_key: str) -> bool:
    path = urllib.parse.urlsplit(url).path.lower()
    patterns = {
        "amazon-tr": r"/(?:dp|gp/product)/",
        "trendyol": r"-p-[a-z0-9]+",
        "hepsiburada": r"-p-[a-z0-9]+",
        "n11": r"/(?:urun|product)/|(?:/|-)?p-\d+",
    }
    if source_key in patterns:
        return bool(re.search(patterns[source_key], path))
    return len(path.strip("/")) > 12


def parse_listing_page(html: str, source: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    base = source["url"]
    host = urllib.parse.urlsplit(base).hostname or ""
    key = source["key"]
    found: dict[str, dict[str, Any]] = {}

    for anchor in soup.select("a[href]"):
        url = canonical_url(str(anchor.get("href", "")), base)
        if urllib.parse.urlsplit(url).hostname != host:
            continue
        if not _matches_product_url(url, key):
            continue
        title = " ".join((anchor.get("aria-label") or anchor.get_text(" ", strip=True) or "").split())
        if len(title) < 8:
            image = anchor.select_one("img[alt]")
            title = " ".join((image.get("alt", "") if image else "").split())
        if len(title) < 8:
            continue
        title = title[:180]

        card = anchor
        card_text = " ".join(anchor.get_text(" ", strip=True).split())
        for parent in list(anchor.parents)[:7]:
            text = " ".join(parent.get_text(" ", strip=True).split())
            if len(text) > 700:
                break
            if PRICE_RE.search(text) or DISCOUNT_HINT_RE.search(text):
                card, card_text = parent, text
                # Prefer the smallest surrounding card that has meaningful offer text.
                break
        price = _price_from_structured(card) or parse_price(card_text)
        if price is None and not DISCOUNT_HINT_RE.search(card_text):
            continue
        found[url] = {
            "source": source["name"],
            "title": title,
            "url": url,
            "price": price,
        }
    return list(found.values())


def load_sources() -> list[dict[str, str]]:
    data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    return data["sources"]


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"initialized": False, "items": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise RuntimeError("state.json okunamadı; dosyayı elle silmeden önce yedeğini kontrol edin.")


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    fd, tmp = tempfile.mkstemp(prefix="state-", suffix=".json", dir=ROOT)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(state, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write("\n")
        os.replace(tmp, STATE_FILE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ortam değişkenleri gerekli.")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": message, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("ok"):
                raise RuntimeError("Telegram mesajı gönderilemedi; bot tokenı/sohbet kimliğini kontrol edin.")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Telegram API HTTP {exc.code}; bot tokenı ve sohbet erişimini kontrol edin.") from None


def format_alert(kind: str, item: dict[str, Any], old_price: float | None = None) -> str:
    icon = "📉" if kind == "Fiyat düştü" else "🆕"
    price = item.get("price")
    price_text = f"{price:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".") if price is not None else "fiyat sayfada okunamadı"
    before = ""
    if old_price is not None and price is not None:
        old_text = f"{old_price:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
        before = f"\nÖnce: {old_text}"
    return f"{icon} {kind}\n{item['source']} — {item['title']}\nŞimdi: {price_text}{before}\n{item['url']}"


def run() -> int:
    state = load_state()
    old_items: dict[str, dict[str, Any]] = state.get("items", {})
    current: dict[str, dict[str, Any]] = {}
    successful_sources = 0
    source_notes: list[str] = []

    for source in load_sources():
        url = source["url"]
        try:
            if not robots_allows(url):
                source_notes.append(f"{source['name']}: robots/policy nedeniyle atlandı")
                continue
            status, body, headers = fetch(url)
            if status != 200:
                source_notes.append(f"{source['name']}: HTTP {status}; korumayı aşmadan atlandı")
                continue
            if len(body) > 8_000_000:
                source_notes.append(f"{source['name']}: sayfa boyutu sınırı nedeniyle atlandı")
                continue
            found = parse_listing_page(body.decode("utf-8", errors="replace"), source)
            successful_sources += 1
            for item in found:
                current[item["url"]] = item
            print(f"{source['name']}: {len(found)} ürün/fırsat kartı bulundu")
        except Exception as exc:
            # Keep logs useful while avoiding credentials or response bodies.
            source_notes.append(f"{source['name']}: erişim/ayrıştırma hatası ({type(exc).__name__})")

    if successful_sources == 0:
        for note in source_notes:
            print(note, file=sys.stderr)
        print("Hiçbir kaynak okunamadı; state güncellenmedi.", file=sys.stderr)
        return 2

    alerts: list[str] = []
    if state.get("initialized"):
        for url, item in current.items():
            previous = old_items.get(url)
            if previous is None:
                alerts.append(format_alert("Yeni kampanya fırsatı", item))
                continue
            old_price = previous.get("price")
            new_price = item.get("price")
            if isinstance(old_price, (int, float)) and isinstance(new_price, (int, float)) and new_price < old_price:
                alerts.append(format_alert("Fiyat düştü", item, float(old_price)))

    # Send first; only save state after successful delivery so failed messages can retry.
    for alert in alerts:
        send_telegram(alert[:3900])
    if not state.get("initialized"):
        send_telegram(
            f"✅ İndirim botu kuruldu. {len(current)} fırsat kartı başlangıç olarak kaydedildi. "
            "Sonraki kontrollerde yeni kartları ve görünen fiyat düşüşlerini bildireceğim."
        )

    merged = dict(old_items)
    for url, item in current.items():
        previous = merged.get(url, {})
        merged[url] = {**previous, **item, "last_seen": datetime.now(timezone.utc).isoformat()}
    state["initialized"] = True
    state["items"] = merged
    save_state(state)

    for note in source_notes:
        print(note)
    print(f"Tamamlandı: {successful_sources} kaynak, {len(current)} aktif kart, {len(alerts)} bildirim.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        raise SystemExit(1)
