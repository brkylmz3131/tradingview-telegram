"""
TradingView Tarama (Screener) -> Telegram köprüsü
--------------------------------------------------
TradingView alarmından gelen webhook isteğini yakalar, içinden
hisse / fiyat / tarama adını okur, üzerine geliş saatini ekler ve
Telegram'a biçimli bir mesaj gönderir.

Çalıştırmak için gereken ortam değişkenleri (environment variables):
  TELEGRAM_BOT_TOKEN  -> BotFather'dan aldığın bot token'ı
  TELEGRAM_CHAT_ID    -> Mesajın gideceği sohbet/kanal ID'si
  WEBHOOK_SECRET      -> URL'ye koyacağın gizli anahtar (güvenlik)
  TIMEZONE            -> Saat dilimi (varsayılan: Europe/Istanbul)
"""

import os
import re
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Ayarlar (ortam değişkenlerinden okunur)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "lutfen-bu-anahtari-degistir")
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Istanbul")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------
def send_telegram(text: str) -> None:
    """Hazır metni Telegram'a gönderir. Hata olursa yukarı fırlatır."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil.")

    resp = requests.post(
        TELEGRAM_API,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()


def parse_payload(req) -> dict:
    """
    TradingView alarm mesajı JSON de olabilir, düz metin de.
    İkisini de ele alır; JSON değilse ham metni '_raw' olarak döndürür.
    """
    data = req.get_json(silent=True)
    if isinstance(data, dict):
        return data
    raw = (req.get_data(as_text=True) or "").strip()
    return {"_raw": raw}


def split_symbols(value: str):
    """Birden fazla hisse virgül/boşluk/satır ile ayrılmış olabilir."""
    parts = re.split(r"[,\n;]+", value)
    return [p.strip() for p in parts if p.strip()]


def clean(value, default="—"):
    """Boş veya doldurulmamış placeholder'ları temizler."""
    if value is None:
        return default
    s = str(value).strip()
    # TradingView placeholder'ı değerle değiştirmediyse (ör. plan desteklemiyorsa)
    if not s or s.startswith("{{"):
        return default
    return s


def format_message(data: dict) -> str:
    """Gelen veriyi okunur bir Telegram mesajına çevirir."""
    tarama = clean(data.get("tarama") or data.get("screener"), "Tarama")
    raw_hisse = data.get("hisse") or data.get("ticker") or data.get("_raw") or ""
    fiyat = clean(data.get("fiyat") or data.get("price"))

    now = datetime.now(ZoneInfo(TIMEZONE)).strftime("%d.%m.%Y %H:%M:%S")

    symbols = split_symbols(str(raw_hisse))

    tarama_e = html.escape(tarama)

    # Tek hisse
    if len(symbols) <= 1:
        hisse_e = html.escape(symbols[0]) if symbols else "—"
        lines = [
            "🔔 <b>Yeni hisse taramaya geldi</b>",
            "",
            f"📊 <b>Tarama:</b> {tarama_e}",
            f"📈 <b>Hisse:</b> {hisse_e}",
            f"💰 <b>Fiyat:</b> {html.escape(fiyat)}",
            f"🕐 <b>Saat:</b> {now}",
        ]
        return "\n".join(lines)

    # Birden fazla hisse
    liste = "\n".join(f"• <b>{html.escape(s)}</b>" for s in symbols)
    lines = [
        "🔔 <b>Taramaya yeni hisseler geldi</b>",
        "",
        f"📊 <b>Tarama:</b> {tarama_e}",
        f"📈 <b>Hisseler ({len(symbols)}):</b>",
        liste,
        f"🕐 <b>Saat:</b> {now}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rotalar (endpoints)
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    """Sağlık kontrolü – tarayıcıdan açınca çalıştığını görürsün."""
    return "OK – TradingView -> Telegram webhook ayakta.", 200


@app.route("/test/<secret>", methods=["GET"])
def test(secret):
    """
    Tarayıcıdan açarak sistemi test et:
      https://<adresin>/test/<WEBHOOK_SECRET>
    Telegram'a örnek bir mesaj gönderir. Mesaj düşüyorsa her şey tamam.
    """
    if secret != WEBHOOK_SECRET:
        abort(403)
    try:
        ornek = format_message({
            "tarama": "KURULUM TESTİ",
            "hisse": "THYAO",
            "fiyat": "312.50",
        })
        send_telegram("✅ <b>Kurulum testi başarılı</b> — sistem çalışıyor!\n\n" + ornek)
    except Exception as exc:  # noqa: BLE001
        print("TEST HATASI:", repr(exc))
        return f"HATA: {exc}", 500
    return "Test mesaji gonderildi. Telegram'ini kontrol et.", 200


@app.route("/webhook/<secret>", methods=["POST"])
def webhook(secret):
    # URL'deki gizli anahtar doğru mu?
    if secret != WEBHOOK_SECRET:
        abort(403)

    data = parse_payload(request)

    try:
        message = format_message(data)
        send_telegram(message)
    except Exception as exc:  # noqa: BLE001
        # Hatayı logla; TradingView alarm kaydında 'failed' görünsün
        print("WEBHOOK HATASI:", repr(exc))
        return f"error: {exc}", 500

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
