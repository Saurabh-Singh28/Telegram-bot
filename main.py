import os
import pytz
import asyncio
import openai
import aiohttp
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatMemberStatus
from telegram.helpers import mention_html
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ====== CONFIG ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

IST = pytz.timezone("Asia/Kolkata")
CHAT_LOG = "chat_ids.txt"
SEEN_USERS_FILE = "seen_users.txt"
ADMIN_IDS = ["5239347550"]

app_web = Flask('')

@app_web.route('/')
def home():
    return "✅ Bot is alive!"

def run():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

async def ping_self():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://saurabh-singh.alwaysdata.net/")
        except Exception as e:
            print(f"Ping failed: {e}")
        await asyncio.sleep(60)

def save_chat_id(chat_id, chat_name="Unknown"):
    entry = f"{chat_id}|{chat_name}"
    if not os.path.exists(CHAT_LOG):
        with open(CHAT_LOG, 'w') as f:
            f.write(f"{entry}\n")
    else:
        with open(CHAT_LOG, 'r+') as f:
            lines = f.read().splitlines()
            ids = [line.split('|')[0] for line in lines]
            if str(chat_id) not in ids:
                f.write(f"{entry}\n")

def save_seen_user(user_id, user_name):
    entry = f"{user_id}|{user_name}"
    if not os.path.exists(SEEN_USERS_FILE):
        with open(SEEN_USERS_FILE, 'w') as f:
            f.write(f"{entry}\n")
    else:
        with open(SEEN_USERS_FILE, 'r+') as f:
            lines = f.read().splitlines()
            ids = [line.split('|')[0] for line in lines]
            if str(user_id) not in ids:
                f.write(f"{entry}\n")

async def get_chatgpt_reply(user_message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "✅ AI failed to respond. Please check API key or try again later."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    name = chat.title or chat.first_name or chat.username or "Unknown"
    save_chat_id(chat.id, name)
    save_seen_user(user.id, user.full_name)
    buttons = [[KeyboardButton("/start"), KeyboardButton("/help")], [KeyboardButton("/contact"), KeyboardButton("/about")]]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("✅ Hello Dear! I am Alive.", reply_markup=markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Commands:\n/start - Start the bot\n/help - Help info\n/contact - Contact us\n/mention - Mention all (Group Admins only)"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📩 Contact us at: @Mr_Wizard_1")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat = update.effective_chat
    user = update.effective_user
    chat_name = chat.title or user.full_name or user.username or "Unknown"
    save_chat_id(chat.id, chat_name)
    save_seen_user(user.id, user.full_name)

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("✅ This command is for admins only.")
        return

    user_message = " ".join(context.args)
    if not user_message:
        await update.message.reply_text("🧠 Usage:\n`/ask What is AI?`", parse_mode="Markdown")
        return

    reply = await get_chatgpt_reply(user_message)
    await update.message.reply_text(reply)

    with open("ask_log.txt", "a", encoding="utf-8") as log:
        log.write(f"----- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -----\n")
        log.write(f"User: {user.full_name} ({user.id})\n")
        log.write(f"Chat: {chat_name} ({chat.id})\n")
        log.write(f"Asked: {user_message}\n")
        log.write(f"Reply: {reply}\n\n")

last_mention_time = {}
MENTION_COOLDOWN = 60

async def mention_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ This command can only be used in groups.")
        return

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text("❌ Only admins can use this command.")
        return

    now = datetime.now().timestamp()
    if chat.id in last_mention_time and (now - last_mention_time[chat.id]) < MENTION_COOLDOWN:
        await update.message.reply_text("⏳ Please wait before mentioning again.")
        return
    last_mention_time[chat.id] = now

    try:
        mentions = []
        if os.path.exists(SEEN_USERS_FILE):
            with open(SEEN_USERS_FILE) as f:
                for line in f:
                    uid, uname = line.strip().split('|', 1)
                    mentions.append(mention_html(uid, uname))
        if mentions:
            batch_size = 20
            for i in range(0, len(mentions), batch_size):
                await update.message.reply_html("🔔 " + " ".join(mentions[i:i + batch_size]))
        else:
            await update.message.reply_text("❌ No users seen yet.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed: {e}")

async def reply_anything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return

def schedule_broadcasts(app):
    scheduler = BackgroundScheduler(timezone=IST)
    now = datetime.now(IST)
    scheduler.add_job(lambda: asyncio.run(send_broadcast(app, "✅ Bot is running!")),
                      CronTrigger(minute=(now.minute + 1) % 60, hour=now.hour))
    scheduler.add_job(lambda: asyncio.run(send_broadcast(app, "🌙 Good night from your bot!")),
                      CronTrigger(hour=22, minute=0))
    scheduler.start()

async def send_broadcast(app, message_text):
    if os.path.exists(CHAT_LOG):
        with open(CHAT_LOG) as f:
            for line in f:
                cid, name = line.strip().split('|', 1) if '|' in line else (line.strip(), "Unknown")
                try:
                    await app.bot.send_message(chat_id=int(cid), text=message_text)
                except Exception as e:
                    print(f"Failed for {cid}: {e}")

async def on_startup(app):
    asyncio.create_task(ping_self())

if __name__ == '__main__':
    print("✅ Bot is starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("mention", mention_all))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_anything))
    schedule_broadcasts(app)
    keep_alive()
    app.run_polling()
