
"""
=======================================================================
 ТАЙ БЕЗ ПАНИКИ — Telegram-бот для канала @thaibezpaniki
=======================================================================
 Что делает бот:
  1. Мониторит RSS-ленты тайских новостных сайтов и блогов
  2. Читает Telegram-каналы экспатов (через Telethon)
  3. Скачивает текст статьи, переводит на русский (Google Translate)
  4. Публикует готовый пост в канал @thaibezpaniki
 
 ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (настраиваются в Railway → Variables):
   BOT_TOKEN   — токен Telegram-бота (от @BotFather)
   TG_API_ID   — числовой ID из my.telegram.org
   TG_API_HASH — хеш из my.telegram.org
 
=======================================================================
 ИНСТРУКЦИЯ: КАК ПОЛУЧИТЬ TG_API_ID и TG_API_HASH
=======================================================================
 1. Открой браузер и перейди на https://my.telegram.org
 2. Введи номер телефона своего аккаунта Telegram (с кодом страны, напр. +79991234567)
 3. Telegram пришлёт код в приложение — введи его на сайте
 4. На следующей странице нажми "API development tools"
 5. Заполни форму:
      App title: thaibezpaniki-bot  (любое название)
      Short name: thaibezpaniki     (латиницей, без пробелов)
      Platform: Other
 6. Нажми "Create application"
 7. Ты увидишь:
      App api_id:   1234567         ← это TG_API_ID (число)
      App api_hash: abcdef1234...   ← это TG_API_HASH (длинная строка)
 8. Скопируй оба значения в Railway → Variables
 
 ⚠️  ВАЖНО: Первый запуск Telethon требует авторизации по телефону.
     Для этого нужно один раз запустить файл setup_telethon.py
     на своём компьютере (не на Railway!), а потом загрузить
     созданный файл tg_session.session в Railway Volume /data/
     Подробнее — в файле setup_telethon.py
 
=======================================================================
"""
 
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
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
 
# ── Настройки ─────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["BOT_TOKEN"]
TG_API_ID   = int(os.environ["TG_API_ID"])
TG_API_HASH = os.environ["TG_API_HASH"]
 
CHANNEL_ID       = "@thaibezpaniki"
CHECK_INTERVAL   = 3600
SENT_LINKS_FILE  = "/data/sent_links.json"
SENT_TG_IDS_FILE = "/data/sent_tg_ids.json"
TG_SESSION_FILE  = "/data/tg_session"
 
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
 
# ── Telegram-каналы для мониторинга ───────────────────────────────────
TG_CHANNELS = [
    # Англоязычные — официальные и новостные
    "thailand_visa_news",
    "ThailandExpats",
    "thaivisa_official",
    "phuket_expats",
    "BangkokExpats",
    "ChiangMaiExpats",
    "thailand_immigration",
    # Русскоязычные — жизнь и документы в Таиланде
    "thai_visa_ru",
    "thailand_ru",
    "phuket_ru",
    "bangkokru",
    "tailand_emigrant",
    "thailand_expat_ru",
    "samui_ru",
    "chiangmai_ru",
    "RusskiyTailang",
    "tailand_dlya_svoikh",
    "ThailandRussia",
]
 
# ── Ключевые слова ─────────────────────────────────────────────────────
REQUIRED_KEYWORDS = [
    "visa", "immigration", "passport", "entry", "border",
    "TM30", "TM47", "overstay", "extension", "permit",
    "foreigner", "tourist visa", "expat", "residence",
    "work permit", "BOI", "elite visa", "LTR visa",
    "retirement visa", "non-immigrant", "re-entry",
    "90-day report", "departure card", "blacklist",
    "immigration office", "Thai immigration",
    "виза", "иммиграция", "паспорт", "въезд", "граница",
    "разрешение", "продление", "переезд", "документы",
    "ТМ30", "ТМ47", "депортация", "резидент", "ВНЖ",
    "рабочая виза", "туристическая виза", "пограничный бег",
    "border run", "консульство", "посольство",
]
 
BANNED_KEYWORDS = [
    "sex work", "prostitut", "casino", "gambling", "drug",
    "murder", "crime", "accident", "flood", "fire",
    "football", "soccer", "sport", "concert", "festival",
    "restaurant", "food", "recipe", "hotel", "resort",
    "крипта", "криптовалюта", "инвестиции", "заработок",
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
    """Скачивает первые ~500 символов текста статьи."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # Берём первые абзацы
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs[:5])
        return text[:1500]
    except Exception as e:
        logger.warning(f"Не удалось скачать статью {url}: {e}")
        return ""
 
 
def build_post(title: str, body: str, link: str, source: str) -> str:
    """Формирует пост: переведённый заголовок + краткое содержание."""
    title_ru = translate(title)
    body_ru  = translate(body) if body else ""
 
    msg = f"🇹🇭 *{source}*\n\n📌 *{title_ru}*"
    if body_ru:
        msg += f"\n\n{body_ru}"
    msg += f"\n\n🔗 [Читать полностью]({link})"
    return msg
 
 
def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    if any(bad.lower() in text for bad in BANNED_KEYWORDS):
        return False
    return any(kw.lower() in text for kw in REQUIRED_KEYWORDS)
 
 
# ── Хранение отправленных ID ───────────────────────────────────────────
def load_json_set(filepath: str) -> set:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logger.warning(f"Ошибка загрузки {filepath}: {e}")
    return set()
 
 
def save_json_set(filepath: str, data: set):
    try:
        with open(filepath, "w") as f:
            json.dump(list(data), f)
    except Exception as e:
        logger.warning(f"Ошибка сохранения {filepath}: {e}")
 
 
# ── RSS-мониторинг ─────────────────────────────────────────────────────
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
                        logger.info(f"✅ RSS: {title[:60]}")
                        await asyncio.sleep(5)
                    except TelegramError as e:
                        logger.error(f"Ошибка публикации: {e}")
 
                sent_links.add(link)
 
        except Exception as e:
            logger.error(f"Ошибка RSS {feed_info['name']}: {e}")
 
    save_json_set(SENT_LINKS_FILE, sent_links)
 
 
# ── Telegram-мониторинг ────────────────────────────────────────────────
async def check_telegram_channels(tg_client: TelegramClient, bot: Bot, sent_tg_ids: set):
    logger.info("Проверяю Telegram-каналы...")
    for channel_username in TG_CHANNELS:
        try:
            entity = await tg_client.get_entity(channel_username)
            history = await tg_client(GetHistoryRequest(
                peer=entity, limit=20,
                offset_date=None, offset_id=0,
                max_id=0, min_id=0,
                add_offset=0, hash=0,
            ))
            for msg in history.messages:
                msg_id = f"{channel_username}_{msg.id}"
                if msg_id in sent_tg_ids:
                    continue
                text = msg.message or ""
                if len(text) < 50:
                    sent_tg_ids.add(msg_id)
                    continue
                if is_relevant(text):
                    try:
                        link = f"https://t.me/{channel_username}/{msg.id}"
                        post = build_post(
                            title=text[:100],
                            body=text[100:600],
                            link=link,
                            source=f"@{channel_username}",
                        )
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=post,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                        logger.info(f"✅ TG: @{channel_username}/{msg.id}")
                        await asyncio.sleep(5)
                    except TelegramError as e:
                        logger.error(f"Ошибка публикации TG: {e}")
                sent_tg_ids.add(msg_id)
 
        except Exception as e:
            logger.warning(f"Не удалось прочитать @{channel_username}: {e}")
 
    save_json_set(SENT_TG_IDS_FILE, sent_tg_ids)
 
 
# ── Главный цикл ───────────────────────────────────────────────────────
async def main():
    logger.info("Запускаю бота...")
 
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"Бот: @{me.username}")
 
    sent_links  = load_json_set(SENT_LINKS_FILE)
    sent_tg_ids = load_json_set(SENT_TG_IDS_FILE)
    logger.info(f"Загружено: {len(sent_links)} ссылок, {len(sent_tg_ids)} TG-сообщений")
 
    tg_client = TelegramClient(TG_SESSION_FILE, TG_API_ID, TG_API_HASH)
    await tg_client.start()
    logger.info("Telethon подключён")
 
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
        await check_telegram_channels(tg_client, bot, sent_tg_ids)
        logger.info(f"Следующая проверка через {CHECK_INTERVAL // 60} минут")
        await asyncio.sleep(CHECK_INTERVAL)
 
 
if __name__ == "__main__":
    asyncio.run(main())
