import os
import asyncio
import logging
from deep_translator import GoogleTranslator
import feedparser
from telegram import Bot
from telegram.error import TelegramError

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = "@thaibezpaniki"
CHECK_INTERVAL = 3600

RSS_FEEDS = [
    {"name": "ThaiVisa / AseanNow", "url": "https://aseannow.com/applications/core/interface/rss/rss.php?id=1"},
    {"name": "The Thaiger", "url": "https://thethaiger.com/feed"},
    {"name": "Coconuts Bangkok", "url": "https://coconuts.co/bangkok/feed/"},
]

# Новость публикуется ТОЛЬКО если есть хотя бы одно из этих слов
REQUIRED_KEYWORDS = [
    # Визы и въезд
    "visa", "tourist visa", "visa exemption", "visa on arrival",
    "visa extension", "visa run", "border run",
    # Иммиграция и документы
    "immigration", "TM30", "TM47", "90 day report", "90-day report",
    "overstay", "deportation", "blacklist",
    "work permit", "residence permit", "retirement visa",
    "non-immigrant", "long stay",
    # Паспорт и въезд
    "passport", "entry ban", "entry requirement",
    "foreigner", "expat", "foreign national",
    # Изменения правил
    "new rule", "new regulation", "policy change",
    "immigration rule", "immigration law", "immigration policy",
    "crackdown", "enforcement",
]

# Если есть хоть одно из этих слов — новость НЕ публикуется
BANNED_KEYWORDS = [
    "fight", "attack", "murder", "kill", "dead", "death", "accident",
    "crash", "fire", "flood", "earthquake", "storm",
    "drug", "arrest", "prison", "jail", "crime",
    "sex", "prostitut", "gambling", "casino",
    "sport", "football", "soccer", "golf", "tennis",
    "concert", "festival", "music", "movie", "film",
    "food", "recipe", "restaurant", "hotel", "resort", "beach",
    "stock", "market", "economy", "baht", "inflation",
    "election", "politic", "government", "minister",
    "farm", "agriculture", "animal", "bird", "fish",
    "weather", "rain", "heat", "temperature",
    "tourist attraction", "sightseeing",
]

sent_links = set()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
translator = GoogleTranslator(source='auto', target='ru')


def translate(text):
    try:
        if not text:
            return text
        return translator.translate(text[:4000])
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        return text


def is_relevant(title, summary=""):
    text = (title + " " + summary).lower()
    # Сначала проверяем запрещённые слова
    if any(bad.lower() in text for bad in BANNED_KEYWORDS):
        return False
    # Потом проверяем обязательные слова
    return any(kw.lower() in text for kw in REQUIRED_KEYWORDS)


def format_message(title_ru, link, source, published=""):
    msg = f"🇹🇭 *{source}*\n\n📌 {title_ru}\n\n"
    if published:
        msg += f"🕐 {published}\n"
    msg += f"🔗 [Читать полностью]({link})"
    return msg


async def fetch_and_send(bot):
    logger.info("Проверяю новости...")
    new_count = 0
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")
                if link in sent_links:
                    continue
                if is_relevant(title, summary):
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
                        await asyncio.sleep(3)
                        logger.info(f"Отправлено: {title_ru}")
                    except TelegramError as e:
                        logger.error(f"Ошибка отправки: {e}")
                else:
                    sent_links.add(link)
                    logger.info(f"Пропущено: {title}")
        except Exception as e:
            logger.error(f"Ошибка чтения {feed_info['name']}: {e}")
    logger.info(f"Готово. Отправлено: {new_count}")


async def main():
    token = os.environ.get("BOT_TOKEN", "")
    logger.info(f"Токен найден: {bool(token)}, длина: {len(token)}")
    bot = Bot(token=token)
    me = await bot.get_me()
    logger.info(f"Бот запущен: @{me.username}")
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ *Тай Без Паники — фильтр обновлён!*\n\nТеперь публикую только новости про миграционную политику и оформление документов для иностранцев. 🇹🇭",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logger.error(f"Не могу написать в канал: {e}")
    while True:
        await fetch_and_send(bot)
        logger.info(f"Следующая проверка через {CHECK_INTERVAL // 60} минут")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
