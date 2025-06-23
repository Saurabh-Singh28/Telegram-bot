from flask import Flask
from threading import Thread
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import asyncio
from openai import OpenAI

# ====== CONFIG ======
BOT_TOKEN = os.environ['BOT_TOKEN']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

IST = pytz.timezone("Asia/Kolkata")
CHAT_LOG = "chat_ids.txt"
ADMIN_IDS = ["5239347550"]  # 🔒 Replace with your Telegram ID (string)

# ====== Replit Keep-Alive ======
app_web = Flask('')


@app_web.route('/')
def home():
    return "Hey There I'm alive"


def run():
    app_web.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# ====== Save Chat ID ======
def save_chat_id(chat_id, chat_name="Unknown"):
    entry = f"{chat_id}|{chat_name}"
    if not os.path.exists(CHAT_LOG):
        with open(CHAT_LOG, 'w') as f:
            f.write(f"{entry}\n")
    else:
        with open(CHAT_LOG, 'r+') as f:
            existing_entries = f.read().splitlines()
            existing_ids = [line.split('|')[0] for line in existing_entries]
            if str(chat_id) not in existing_ids:
                f.write(f"{entry}\n")


# ====== OpenAI Response ======
async def get_chatgpt_reply(user_message):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "system",
                "content": "You are a helpful assistant for a Telegram bot."
            }, {
                "role": "user",
                "content": user_message
            }],
            max_tokens=150)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "❌ AI failed to respond. Please check API key or try again later."


# ====== Telegram Commands ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_name = chat.title or chat.first_name or chat.username or "Unknown"
    save_chat_id(chat.id, chat_name)

    await update.message.reply_text("👋 Hello Dear! I am Alive.")
    await update.message.reply_text("🤖 Tell me how can I help you?")
    buttons = [["Start", "Help"], ["Contact", "About"]]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("👇 Choose an option:", reply_markup=markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_name = chat.title or chat.first_name or chat.username or "Unknown"
    save_chat_id(chat.id, chat_name)
    await update.message.reply_text(
        "📋 Command List:\n/start - Start the bot\n/help - Get help\n/contact - Contact info\n/ask - Talk to AI"
    )


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_name = chat.title or chat.first_name or chat.username or "Unknown"
    save_chat_id(chat.id, chat_name)
    await update.message.reply_text("📞 Contact us at: @Mr_Wizard_1")


# ====== Secret Admin Command: /polkhol ======
async def polkhol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "❌ This command is for bot admins only.")
        return

    if os.path.exists(CHAT_LOG):
        with open(CHAT_LOG, 'r') as f:
            entries = f.read().splitlines()
            if entries:
                message = "📋 *All Users/Groups/Channels:*\n\n"
                for i, entry in enumerate(entries, 1):
                    if '|' in entry:
                        chat_id, chat_name = entry.split('|', 1)
                    else:
                        chat_id, chat_name = entry, "Unknown"
                    message += f"{i}. *{chat_name.strip()}*\n   ID: `{chat_id.strip()}`\n\n"
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "📋 No users found in the database.")
    else:
        await update.message.reply_text("📋 No chat_ids.txt file found.")


# ====== AI Command: /ask ======
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    chat_name = chat.title or user.full_name or user.username or "Unknown"
    save_chat_id(chat.id, chat_name)

    user_message = " ".join(context.args)
    if not user_message:
        await update.message.reply_text(
            "💬 Please type your question like:\n`/ask What can you do?`",
            parse_mode='Markdown')
        return

    reply = await get_chatgpt_reply(user_message)
    await update.message.reply_text(reply)

    # Log the interaction
    with open("ask_log.txt", "a", encoding="utf-8") as log:
        log.write(
            f"----- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -----\n")
        log.write(f"Chat: {chat_name} ({chat.id})\n")
        log.write(
            f"User: {user.full_name or user.username or 'Unknown'} ({user.id})\n"
        )
        log.write(f"Asked: {user_message}\n")
        log.write(f"AI Reply: {reply}\n\n")


# ====== Catch Non-Command Texts ======
async def reply_anything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return  # Bot ignores normal text messages


# ====== Scheduled Broadcasts ======
async def send_broadcast_message(app, message_text):
    if os.path.exists(CHAT_LOG):
        with open(CHAT_LOG, 'r') as f:
            entries = f.read().splitlines()
            for entry in entries:
                try:
                    if '|' in entry:
                        chat_id, chat_name = entry.split('|', 1)
                    else:
                        chat_id, chat_name = entry, "Unknown"

                    await app.bot.send_message(chat_id=int(chat_id),
                                               text=message_text)
                    print(f"✅ Sent to {chat_name} ({chat_id})")
                except Exception as e:
                    print(f"❌ Failed to send to {chat_name} ({chat_id}): {e}")
    else:
        print("⚠️ No chat_ids.txt file found.")


def schedule_broadcasts(app):
    scheduler = BackgroundScheduler(timezone=IST)

    now = datetime.now(IST)
    scheduler.add_job(lambda: asyncio.run(
        send_broadcast_message(app, "🚀 Test message sent 1 min after startup")
    ),
                      trigger=CronTrigger(minute=(now.minute + 1) % 60,
                                          hour=now.hour),
                      id="test_message")

    scheduler.add_job(lambda: asyncio.run(
        send_broadcast_message(app,
                               "🌙 Good evening! This is your 10 PM message.")),
                      trigger=CronTrigger(hour=22, minute=0),
                      id="daily_10pm")

    scheduler.start()
    print("✅ Scheduler started.")


# ====== Run Bot ======
if __name__ == '__main__':
    print("✅ Bot is starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("polkhol", polkhol))  # admin-only
    app.add_handler(CommandHandler("ask", ask_command))  # AI command
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND,
                       reply_anything))  # ignores random messages

    schedule_broadcasts(app)
    keep_alive()
    app.run_polling()
