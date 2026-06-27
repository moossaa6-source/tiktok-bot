import os
import threading
import logging
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests

# إعدادات
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = 8192715650

# خادم الويب لـ Render
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "Bot is running!"
def run_web(): app_web.run(host='0.0.0.0', port=10000)

# بيانات في الذاكرة (مؤقتة لـ Render)
users = {} 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in users:
        users[user_id] = {'points': 0}
        args = context.args
        if args and args[0].isdigit():
            referrer = int(args[0])
            if referrer in users:
                users[referrer]['points'] += 1
    await update.message.reply_text("أهلاً بك! أرسل رابط تيك توك للتحميل.")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_name = (await context.bot.get_me()).username
    points = users.get(user_id, {}).get('points', 0)
    await update.message.reply_text(f"رابط دعوتك: https://t.me/{bot_name}?start={user_id}\nعدد دعواتك: {points}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "tiktok.com" not in url: return
    
    await update.message.reply_text("جاري التحميل...")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url}).json()
        if data.get("code") == 0:
            await update.message.reply_video(video=data["data"]["play"])
        else:
            await update.message.reply_text("فشل التحميل.")
    except Exception:
        await update.message.reply_text("خطأ في الاتصال.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id == ADMIN_ID:
        await update.message.reply_text(f"عدد المستخدمين المسجلين: {len(users)}")

if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("share", share))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    application.run_polling()
