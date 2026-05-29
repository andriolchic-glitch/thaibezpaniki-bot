import os
import asyncio
import logging
from deep_translator import GoogleTranslator
import feedparser
from telegram import Bot
from telegram.error import TelegramError

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "8818290368:AAFrzRqmkvpKbmkF2aMDBF9hxU1mIE-ML_4")

# Username канала
CHANNEL_ID = "@thaibezpaniki"

# Интервал проверки: 3600 = каждый час
CHECK_INTERVAL = 3600

# Источники новостей
RSS_FEEDS = [
    {
        "name": "ThaiVisa / AseanNow",
        "url": "https://aseannow.com/applications/core/interface/rss/rss.php?id=1"
    },
    {
        "name": "The Thaiger",
        "url": "https://thethaiger.com/feed"
    },
    {
        "name": "Coconuts Bangkok",
        "url": "https://coconuts.co/bangkok/feed/"
    },
]

# Ключевые слова для фильтрации
KEYWORDS = [
    "visa", "entry", "stay", "passport", "russia", "russian",
    "immigration", "deportation", "TM30", "TM47", "extension",
    "border", "tourist", "permit", "overstay", "foreigner"
]

# Уже отправленные ссылки
sent_links = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

translator = GoogleTranslator(source='auto', target='ru')


def translate(text: str) -> str:
    """Переводит текст на русский язык"""
    try:
        if not text:
            return text
        return translator.translate(text[:4000])
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        return text


def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def format_message(title_ru: str, link: str, source: str, published: str = "") -> str:
    msg = f"🇹🇭 *{source}*\n\n"
    msg += f"📌 {title_ru}\n\n"
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
                    # Переводим заголовок на русский
                    title_ru = translate(title)

                    msg = format_message(title_ru, link, feed_info["name"], published)
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
                        logger.info(f"Отправлено: {title_ru}")
                    except TelegramError as e:
                        logger.error(f"Ошибка отправки: {e}")
        except Exception as e:
            logger.error(f"Ошибка чтения {feed_info['name']}: {e}")

    logger.info(f"Готово. Отправлено новостей: {new_count}")


async def send_startup_message(bot: Bot):
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ *Тай Без Паники — запущен!*\n\nБуду присылать актуальные новости для россиян в Таиланде на русском языке: визы, въезд, документы, изменения правил.",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logger.error(f"Не могу написать в канал: {e}")


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
