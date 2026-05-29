import os
import asyncio
import logging
from datetime import datetime
import feedparser
from telegram import Bot
from telegram.error import TelegramError

# ✅ Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "8818290368:AAE7XlyGmhZ_NuYrzFLyf8Jh7iY-mba8Xtw")

# ✅ Username канала (без @)
CHANNEL_ID = "@thaibezpaniki"

# ✅ Интервал проверки: 3600 = каждый час
CHECK_INTERVAL = 3600

# --- Источники новостей ---
RSS_FEEDS = [
    {
        "name": "ThaiVisa / AseanNow",
        "url": "https://aseannow.com/applications/core/interface/rss/rss.php?id=1"
    },
    {
        "name": "Кокосы.ру — Таиланд",
        "url": "https://coconuts.co/bangkok/feed/"
    },
    {
        "name": "The Thaiger",
        "url": "https://thethaiger.com/feed"
    },
]

# Ключевые слова для фильтрации
KEYWORDS = [
    "виза", "visa", "въезд", "entry", "пребывание", "stay",
    "паспорт", "passport", "россия", "russia", "russian",
    "immigration", "иммиграция", "депортация", "deportation",
    "TM30", "TM47", "продление", "extension", "border", "граница",
    "tourist", "туристический", "разрешение", "permit", "overstay"
]

# Уже отправленные ссылки (не дублируем)
sent_links = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def format_message(title: str, link: str, source: str, published: str = "") -> str:
    msg = f"🇹🇭 *{source}*\n\n"
    msg += f"📌 {title}\n\n"
    if published:
        msg += f"🕐 {published}\n"
    msg += f"🔗 [Читать полностью]({link})"
    return msg


async def fetch_and_send(bot: Bot):
    logger.info("Проверяю новости...")
    new_count = 0

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:5]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                if link in sent_links:
                    continue

                if is_relevant(title, summary):
                    msg = format_message(title, link, feed_info["name"], published)
                    try:
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=msg,
                            parse_mode="Markdown",
                            disable_web_page_preview=False
                        )
                        sent_links.add(link)
                        new_count += 1
                        await asyncio.sleep(2)
                        logger.info(f"Отправлено: {title}")
                    except TelegramError as e:
                        logger.error(f"Ошибка отправки: {e}")
        except Exception as e:
            logger.error(f"Ошибка чтения {feed_info['name']}: {e}")

    logger.info(f"Готово. Отправлено новостей: {new_count}")


async def send_startup_message(bot: Bot):
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ *Thailert запущен!*\n\nБуду присылать актуальные новости для россиян в Таиланде: визы, въезд, документы, изменения правил.",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logger.error(f"Не могу написать в канал: {e}\nДобавь бота в канал как администратора!")


async def main():
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"Бот запущен: @{me.username}")
    await send_startup_message(bot)

    while True:
        await fetch_and_send(bot)
        logger.info(f"Следующая проверка через {CHECK_INTERVAL // 60} минут")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
