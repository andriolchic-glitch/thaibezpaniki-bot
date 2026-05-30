import os
import asyncio
import logging
import json
import requests
from bs4 import BeautifulSoup
import feedparser
from deep_translator import GoogleTranslator
from telegram import Bot
from telegram.error import TelegramError
 
# ── Настройки ─────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
 
CHANNEL_ID      = "@thaibezpaniki"
CHECK_INTERVAL  = 3600
SENT_LINKS_FILE = "sent_links.json"
 
# ── RSS-источники ──────────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "AseanNow (ThaiVisa)",     "url": "https://aseannow.com/applications/core/interface/rss/rss.php?id=1"},
    {"name": "The Thaiger",             "url": "https://thethaiger.com/feed"},
    {"name": "Coconuts Bangkok",        "url": "https://coconuts.co/bangkok/feed/"},
    {"name": "Bangkok Post",            "url": "https://www.bangkokpost.com/rss/data/topstories.xml"},
    {"name": "Khaosod English",         "url": "https://www.khaosodenglish.com/feed/"},
    {"name": "Thai Examiner",           "url": "https://www.thaiexaminer.com/feed/"},
    {"name": "Nation Thailand",         "url": "https://www.nationthailand.com/rss.xml"},
    {"name": "Thai PBS World",          "url": "https://www.thaipbsworld.com/feed/"},
    {"name": "Pattaya Mail",            "url": "https://www.pattayamail.com/feed"},
    {"name": "Richard Barrow Thailand", "url": "https://www.richardbarrow.com/feed/"},
    {"name": "Expat Den",               "url": "https://expatden.com/feed/"},
    {"name": "Thailand Starter Kit",    "url": "https://www.thailandstarterkit.com/feed/"},
    {"name": "Thaiest (рус.)",          "url": "https://thaiest.ru/feed"},
    {"name": "Samui Times",             "url": "https://www.samuittimes.com/feed/"},
    {"name": "Chiang Mai Citylife",     "url": "https://www.chiangmaicitylife.com/feed/"},
    {"name": "Phuket News",             "url": "https://www.thephuketnews.com/rss.php"},
]
 
# ── Ключевые слова ─────────────────────────────────────────────────────
REQUIRED_KEYWORDS = [
    # Визы и типы виз
    "tourist visa", "retirement visa", "non-immigrant visa",
    "elite visa", "LTR visa", "work permit", "visa exemption",
    "visa on arrival", "visa extension", "visa run", "border run",
    "e-visa", "digital nomad visa",
    # Иммиграционные процедуры
    "TM30", "TM47", "TM6", "immigration",
    "overstay", "90-day report", "re-entry permit",
    "departure card", "blacklist", "deportation",
    "immigration office", "immigration bureau",
    # Изменения в политике
    "immigration law", "immigration rules", "immigration policy",
    "new visa", "visa change", "visa update", "visa regulation",
    "crackdown", "immigration crackdown",
    # Русские эквиваленты
    "виза", "иммиграция", "иммиграционный",
    "ТМ30", "ТМ47", "депортация", "овerstay", "овerstay",
    "рабочая виза", "туристическая виза", "пограничный бег",
    "продление визы", "90-дневный отчёт", "консульство",
    "миграционная политика", "миграционные правила",
]
 
BANNED_KEYWORDS = [
    "sex work", "prostitut", "casino", "gambling", "drug",
    "murder", "crime", "accident", "flood", "fire",
    "football", "soccer", "sport", "concert", "festival",
    "restaurant", "food", "recipe", "hotel", "resort",
    "крипта", "криптовалюта", "инвестиции", "заработок",
    "real estate", "property", "condo", "недвижимость",
    "weather", "погода", "tsunami", "earthquake",
    # Тайцы за рубежом — нас не интересует
    "thai workers", "thai nationals", "thai fishermen",
    "thai sailors", "thai migrants", "тайским рабочим",
    "тайские рабочие", "тайских рабочих",
    # Другие страны как основная тема
    "in japan", "в японии", "in korea", "в корее",
    "in china", "в китае", "in malaysia", "в малайзии",
    "in singapore", "в сингапуре", "in australia", "в австралии",
    "in taiwan", "в тайване", "in usa", "в сша",
    "in europe", "в европе", "in uk", "в британии",
    # Прочее нерелевантное
    "lobster", "омар", "fishing", "рыбалка", "seafood",
]
 
# ── Логирование ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
 
translator = GoogleTranslator(source='auto', target='ru')
 
 
def translate(text: str) -> str:
    try:
        if not text:
            return text
        return translator.translate(text[:4000])
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        return text
 
 
def fetch_article_text(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs[:5])
        return text[:1500]
    except Exception as e:
        logger.warning(f"Не удалось скачать статью {url}: {e}")
        return ""
 
 
def build_post(title: str, body: str, link: str, source: str) -> str:
    title_ru = translate(title)
    body_ru  = translate(body) if body else ""
    msg = f"🇹🇭 *{source}*\n\n📌 *{title_ru}*"
    if body_ru:
        msg += f"\n\n{body_ru}"
    msg += f"\n\n🔗 [Читать полностью]({link})"
    return msg
 
 
THAILAND_KEYWORDS = [
    "thailand", "thai", "bangkok", "phuket", "pattaya",
    "chiang mai", "samui", "таиланд", "тайланд", "бангкок",
    "пхукет", "паттайя", "чиангмай", "самуи",
]
 
def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    if any(bad.lower() in text for bad in BANNED_KEYWORDS):
        return False
    # Обязательно должен упоминаться Таиланд
    if not any(loc.lower() in text for loc in THAILAND_KEYWORDS):
        return False
    return any(kw.lower() in text for kw in REQUIRED_KEYWORDS)
 
 
def load_sent_links() -> set:
    if os.path.exists(SENT_LINKS_FILE):
        try:
            with open(SENT_LINKS_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logger.warning(f"Ошибка загрузки sent_links: {e}")
    return set()
 
 
def save_sent_links(links: set):
    try:
        with open(SENT_LINKS_FILE, "w") as f:
            json.dump(list(links), f)
    except Exception as e:
        logger.warning(f"Ошибка сохранения sent_links: {e}")
 
 
async def check_rss(bot: Bot, sent_links: set):
    logger.info("Проверяю RSS...")
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]:
                link    = entry.get("link", "")
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
 
                if not link or link in sent_links:
                    continue
 
                if is_relevant(title, summary):
                    body = fetch_article_text(link) or summary
                    try:
                        msg = build_post(title, body, link, feed_info["name"])
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=msg,
                            parse_mode="Markdown",
                            disable_web_page_preview=False,
                        )
                        logger.info(f"✅ {title[:60]}")
                        await asyncio.sleep(5)
                    except TelegramError as e:
                        logger.error(f"Ошибка публикации: {e}")
 
                sent_links.add(link)
 
        except Exception as e:
            logger.error(f"Ошибка RSS {feed_info['name']}: {e}")
 
    save_sent_links(sent_links)
 
 
async def main():
    logger.info("Запускаю бота...")
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"Бот: @{me.username}")
 
    sent_links = load_sent_links()
    logger.info(f"Загружено ссылок: {len(sent_links)}")
 
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ *Тай Без Паники — работает!*\n\nПубликую новости про визы, въезд и документы на русском языке. 🇹🇭",
            parse_mode="Markdown",
        )
    except TelegramError as e:
        logger.error(f"Не могу написать в канал: {e}")
 
    while True:
        await check_rss(bot, sent_links)
        logger.info(f"Следующая проверка через {CHECK_INTERVAL // 60} минут")
        await asyncio.sleep(CHECK_INTERVAL)
 
 
if __name__ == "__main__":
    asyncio.run(main())
