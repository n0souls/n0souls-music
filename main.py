import json
import os
import asyncio
import pylast
import logging
from telethon import TelegramClient, events, errors
import pathlib

class Config:
    API_ID = 24542743
    API_HASH = 'a659ecfb25eec88922a8a03bfbbf3ef0'
    PHONE = '+79302376227'
    LASTFM_USERNAME = "n0souls"
    LASTFM_PASSWORD = "Gleblolkek4eburek!" 
    LASTFM_API_KEY = "04f0c215694b366506fc62a68484b4de"
    LASTFM_API_SECRET = "ac2b7baef1d15cb35424ebf2b3c740fa"

BASE_DIR = pathlib.Path(__file__).parent.resolve()
TRACK_MESSAGES_FILE = str(BASE_DIR / 'track_messages.json')

logging.basicConfig(
    filename=str(BASE_DIR / 'bot_errors.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client = TelegramClient(str(BASE_DIR / 'telegram_session'), Config.API_ID, Config.API_HASH)

def load_track_messages():
    if not os.path.exists(TRACK_MESSAGES_FILE):
        return []
    try:
        with open(TRACK_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки сообщений: {e}")
        return []

def save_track_messages(messages):
    try:
        with open(TRACK_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщений: {e}")

def add_track_message(chat_id, message_id):
    messages = load_track_messages()
    for m in messages:
        if m['chat_id'] == chat_id and m['message_id'] == message_id:
            return
    messages.append({
        "chat_id": chat_id,
        "message_id": message_id,
        "last_track": ""
    })
    save_track_messages(messages)

def remove_track_message(chat_id, message_id):
    messages = load_track_messages()
    messages = [m for m in messages if not (m['chat_id'] == chat_id and m['message_id'] == message_id)]
    save_track_messages(messages)

def get_current_track():
    try:
        network = pylast.LastFMNetwork(
            api_key=Config.LASTFM_API_KEY,
            api_secret=Config.LASTFM_API_SECRET,
            username=Config.LASTFM_USERNAME,
            password_hash=pylast.md5(Config.LASTFM_PASSWORD),
        )
        user = network.get_user(Config.LASTFM_USERNAME)
        track = user.get_now_playing()
        return f"{track.artist.name} – {track.title}" if track else None
    except Exception as e:
        logger.error(f"Last.fm error: {e}")
        return None

@client.on(events.NewMessage(pattern=r'!nowplayed(?:\s+(https://t\.me/c/(\d+)/(\d+)))?'))
async def nowplayed_handler(event):
    if event.pattern_match.group(1):
        _, chat_id, message_id = event.pattern_match.groups()
        chat_id = int(f"-100{chat_id}")
        message_id = int(message_id)
    else:
        chat_id = event.chat_id
        message_id = event.message.id
    
    current_track = get_current_track()
    success = await retry_edit_message(chat_id, message_id, current_track)
    
    if success:
        add_track_message(chat_id, message_id)
    elif current_track:
        await event.respond("⚠️ Не удалось обновить сообщение")

async def retry_edit_message(chat_id, message_id, new_text):
    def escape_md(text):
        escape_chars = r'\_*[]()~`>#+-=|{}.!'
        return ''.join('\\' + c if c in escape_chars else c for c in text)

    for attempt in range(3):
        try:
            entity = await client.get_entity(chat_id)
            message = await client.get_messages(entity, ids=message_id)

            if new_text is None and " – " in message.text:
                return True

            if new_text:
                escaped_track = escape_md(new_text)
                formatted_text = f"[♫♫] **Сейчас играет:** `{escaped_track}`"
            else:
                formatted_text = "[♫♫] **Сейчас ничего не играет**"

            await client.edit_message(entity, message_id, formatted_text, parse_mode='md')
            return True

        except errors.MessageNotModifiedError:
            return True
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {type(e)} {e}")
            await asyncio.sleep(10)
    return False

@client.on(events.NewMessage(pattern=r'!help'))
async def help_command(event):
    help_text = """
🎵 **Доступные команды:**

`!nowplayed [ссылка]`  
_Отслеживание текущего трека_

`!help`  
_Показать эту справку_
    """
    await event.respond(help_text)

async def periodic_update():
    while True:
        messages = load_track_messages()
        updated = False
        
        for m in messages[:]:
            current_track = get_current_track()
            previous_track = m['last_track']
            
            if current_track != previous_track:
                success = await retry_edit_message(m['chat_id'], m['message_id'], current_track)
                if success:
                    m['last_track'] = current_track if current_track else previous_track
                    updated = True
                    
        if updated:
            save_track_messages(messages)
        await asyncio.sleep(15)

async def main():
    if not os.path.exists(TRACK_MESSAGES_FILE):
        with open(TRACK_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

    await client.connect()
    
    if not await client.is_user_authorized():
        await client.start(Config.PHONE)
        logger.info("✅ Авторизация успешна")
    else:
        logger.info("🔄 Используем существующую сессию")
    
    await client.get_dialogs()
    asyncio.create_task(periodic_update())
    
    logger.info("🤖 Бот запущен")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
