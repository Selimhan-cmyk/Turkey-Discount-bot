# Türkiye İndirim Botu (ilk sürüm)

Telegram'a bildirim gönderen, Amazon Türkiye / Trendyol / Hepsiburada / n11'in herkese açık kampanya sayfalarını en fazla 15 dakikada bir kontrol eden bir başlangıç projesi.

## Kapsam ve sınırlar

- Bu sürüm bütün ürün kataloğunu taramaz. Yalnızca kaynak sayfada görünür ürün bağlantılarını kontrol eder.
- Sayfada fiyat okunabiliyorsa önceki kontrolle karşılaştırıp düşüşü bildirir; yeni görünen kampanya bağlantılarını da bildirir.
- İlk çalıştırmada mevcut liste başlangıç olarak kaydedilir; eski fırsatları toplu halde göndermemek için yalnızca kurulum mesajı yollar.
- Mağaza sayfası JavaScript/login isterse, robots.txt erişimi engellerse veya HTTP 403/429 verirse bot o kaynağı atlar. CAPTCHA, oturum açma, gizli API veya engel aşma yoktur.
- Kampanya sayfaları değişebilir. Dört sitede de her fırsatın bulunacağı veya her fiyat düşüşünün yakalanacağı garanti edilmez. Güvenilir tam kapsam için mağazaların onaylı veri akışı/API erişimi gerekir.
- Fiyat, liste kartındaki metinden çıkarılmaya çalışılır; kupon, sepet, üyelik, varyant ve kargo şartları her zaman anlaşılamayabilir. Satın almadan önce mağaza sayfasını kontrol edin.

## Telegram kurulum

1. Telegram'da **@BotFather** üzerinden `/newbot` ile bot oluşturun ve tokenı alın.
2. Botla özel sohbet açıp `/start` gönderin. Grup bildirimi isterseniz botu gruba ekleyin ve grupta bir mesaj yazın.
3. Tokenı yerel ortam değişkeni olarak ayarlayıp `python get_chat_id.py` çalıştırın; uygun sohbet ID'sini not edin. Tokenı sohbet mesajına veya kaynak koda yazmayın.
4. GitHub'da özel bir repository açıp bu klasörün içeriğini yükleyin.
5. Repository → **Settings → Secrets and variables → Actions** bölümünde şu repository secrets değerlerini ekleyin:
   - `TELEGRAM_BOT_TOKEN`: BotFather tokenı
   - `TELEGRAM_CHAT_ID`: 3. adımda bulduğunuz sohbet/grup ID'si
6. `.github/workflows/monitor.yml` varsayılan dala yüklendikten sonra workflow otomatik olarak yaklaşık 15 dakikada bir çalışır. İlk çalıştırmayı **Actions → Marketplace deal monitor → Run workflow** ile başlatabilirsiniz.

GitHub zamanlanmış işleri yoğunlukta gecikebilir; bu anlık alarm garantisi değildir. Yerelde test için Python 3.10+, `pip install -r requirements.txt`, gerekli iki ortam değişkeni ve `python bot.py` yeterlidir.

## Kaynak sayfaları

`sources.json` içinde URL'ler düzenlenebilir. Yalnızca herkese açık sayfaları kullanın ve ilgili sitelerin koşullarını kontrol edin. Bot 403/429 veya robots engelini aşmaya çalışmaz.
