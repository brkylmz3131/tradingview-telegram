# TradingView Tarama → Telegram Bildirimi

TradingView Stock Screener (hisse taraması) alarmlarını Telegram'a bağlar.
Bir hisse taramana girdiğinde Telegram'a şöyle bir mesaj düşer:

```
🔔 Yeni hisse taramaya geldi

📊 Tarama: Momentum Taraması
📈 Hisse: THYAO
💰 Fiyat: 312.50
🕐 Saat: 25.10.2026 18:05:32
```

---

## Nasıl çalışır?

```
TradingView tarama alarmı
        │  (webhook - HTTPS POST)
        ▼
  Bu sunucu (app.py)
        │  mesajı biçimler + geliş saatini ekler
        ▼
   Telegram Bot API
        ▼
  Senin Telegram'ın
```

- **Hisse adı** ve **fiyat** → TradingView'in alarm mesajındaki `{{ticker}}` ve `{{close}}` ile gelir.
- **Geliş saati** → sunucu kendisi damgalar (her zaman İstanbul saati, boş kalmaz).
- **Hangi tarama** → her taraman için ayrı alarm kurarsın; tarama adını alarm mesajına sen yazarsın.

---

## Gereksinimler

1. **Ücretli TradingView planı (Essential ve üzeri).** Webhook bildirimi ücretsiz planda yok.
2. TradingView hesabında **2FA (iki faktörlü doğrulama) açık** olmalı — webhook için şart.
3. Bir **Telegram hesabı**.
4. Sunucunun yayında olacağı bir yer (Railway, Render, bir VPS... aşağıda anlattım). TradingView sadece **443/80 portuna** ve **HTTPS**'e istek atar.

---

## Adım 1 — Telegram botunu oluştur

1. Telegram'da **@BotFather**'a yaz.
2. `/newbot` komutunu gönder, bir isim ve kullanıcı adı ver.
3. BotFather sana `123456789:ABCdef...` formatında bir **token** verir. Bunu sakla → `TELEGRAM_BOT_TOKEN`.

---

## Adım 2 — Chat ID'yi öğren

Mesajın nereye gideceğini bulman gerekiyor.

**En kolay yol:**
1. Oluşturduğun bota Telegram'dan bir "merhaba" mesajı at (bot sana yazamaz, önce sen başlatmalısın).
2. Tarayıcıda şu adresi aç (TOKEN yerine kendi token'ını koy):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Dönen JSON içinde `"chat":{"id":123456789 ...}` göreceksin. Bu sayı → `TELEGRAM_CHAT_ID`.

> **Bir gruba/kanala** göndermek istersen: botu gruba ekle, gruba bir mesaj at, yine `getUpdates` ile grup ID'sini al. Grup ID'leri genelde `-100...` ile başlar.

---

## Adım 3 — Sunucuyu yayına al

### Seçenek A — Railway (önerilen, basit)

1. [railway.app](https://railway.app) hesabı aç.
2. Bu klasörü bir GitHub deposuna yükle, Railway'de **New Project → Deploy from GitHub** de.
3. **Variables** sekmesine şu değişkenleri gir:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `WEBHOOK_SECRET` (uzun, rastgele bir metin — ör. `k9f2mXp7qL`)
   - `TIMEZONE` = `Europe/Istanbul`
4. Railway otomatik bir HTTPS adresi verir, ör: `https://seninuygulaman.up.railway.app`
5. Webhook adresin şu olur:
   ```
   https://seninuygulaman.up.railway.app/webhook/<WEBHOOK_SECRET>
   ```

> Render, Fly.io veya kendi VPS'in de olur. Hepsinde mantık aynı: `requirements.txt` kurulur, `Procfile`'daki `gunicorn app:app` komutu çalışır.

### Lokalde test etmek istersen
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...   # Windows'ta: set TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export WEBHOOK_SECRET=test123
python app.py
```
Sonra başka bir terminalde dışarı açmak için **ngrok** kullan:
```bash
ngrok http 8080
```
ngrok sana bir HTTPS adresi verir; TradingView'e onu girersin.

**Hızlı test** (sunucunun çalışıp çalışmadığını Telegram'a mesaj atarak dene):
```bash
curl -X POST https://seninadresin/webhook/test123 \
  -H "Content-Type: application/json" \
  -d '{"tarama":"Test Taraması","hisse":"THYAO","fiyat":"312.50"}'
```

---

## Adım 4 — TradingView tarama alarmını kur

**Her taraman için ayrı bir alarm** kurarsın (tarama adını böyle ayırt ederiz).

1. TradingView'de **Stock Screener**'ı aç, taramanı seç/çalıştır.
2. Screener'daki **alarm (⏰) / "Create Alert"** butonuna bas.
3. **Condition:** taramaya yeni bir hisse eklendiğinde tetiklenecek seçeneği seç.
4. **Notifications** sekmesinde **Webhook URL**'i işaretle ve adresini yapıştır:
   ```
   https://seninadresin/webhook/<WEBHOOK_SECRET>
   ```
5. **Message** (mesaj) kutusuna şu JSON'u yapıştır — `tarama` değerini o taramaya göre değiştir:
   ```json
   {
     "tarama": "Momentum Taraması",
     "hisse": "{{ticker}}",
     "fiyat": "{{close}}"
   }
   ```
6. Kaydet. İkinci taraman için aynısını tekrarla, sadece `"tarama"` değerini değiştir (ör. `"Hacim Patlaması"`).

---

## Fiyat gelmezse?

Bazı planlarda/screener alarmlarında `{{close}}` değeri gelmeyebilir. O durumda mesajda fiyat yerine `—` görürsün — sistem yine de **hisse, tarama ve saat** ile mesajı gönderir. İstersen mesajdan `"fiyat"` satırını tamamen çıkarabilirsin; bir şey bozulmaz.

Alarmın gerçekten ne gönderdiğini **TradingView → Alarm kaydı (Alert log)** ekranından görebilirsin; mesajın tam metni ve webhook'un başarılı/başarısız durumu orada yazar.

---

## Güvenlik notları

- Webhook adresindeki `WEBHOOK_SECRET` kısmı bir parola gibidir; **tahmin edilmesi zor, uzun** olsun. Yanlış anahtarla gelen istekler reddedilir (403).
- Token'ını ve chat ID'ni kimseyle paylaşma, koda gömme — hep ortam değişkeni olarak gir.

## Sorun giderme

| Sorun | Bak |
|---|---|
| Mesaj hiç gelmiyor | Önce `curl` ile test et. Gelmiyorsa token/chat ID yanlış ya da bota hiç `/start` atılmamış. |
| TradingView "failed" diyor | Adres HTTPS mi? `WEBHOOK_SECRET` URL'dekiyle aynı mı? Port 443 mü? |
| Fiyat `—` geliyor | Planın screener alarmında `{{close}}` doldurmuyordur; normal, yukarıya bak. |
| Saat yanlış | `TIMEZONE` değişkenini `Europe/Istanbul` yap. |
