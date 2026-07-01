import sqlite3
import requests
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING) 

TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, views INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO stats (id, views) VALUES (1, 0)")
    conn.commit()
    conn.close()

init_db()

# --- الترند التلقائي ---
async def send_trends_auto_manual(app):
    logging.info("--- بدء فحص الترند ---")
    try:
        response = requests.get("https://www.tikwm.com/api/feed/list?region=SA&count=1", timeout=10).json()
        videos = response.get('data', {}).get('videos', [])
        if not videos: return
        video_file = videos[0].get("play")
        
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        for user in users:
            try: 
                await app.bot.send_video(chat_id=user[0], video=video_file, caption=f"🔥 فيديو ترند!\n📌 {CHANNEL_USERNAME}")
                await asyncio.sleep(2)
            except: pass
    except Exception as e: logging.error(f"خطأ ترند: {e}")

async def trend_loop(app):
    while True:
        await asyncio.sleep(60)
        await send_trends_auto_manual(app)

# --- الدوال الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, update.message.from_user.username))
        conn.commit()
    conn.close()
    await update.message.reply_text("🎉 أهلاً بك!")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_username = (await context.bot.get_me()).username
    await update.message.reply_text(f"👥 رابطك: https://t.me/{bot_username}?start={user_id}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text("🔹 لوحة التحكم:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc")]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if update.message.from_user.id == ADMIN_ID and context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        users = sqlite3.connect('bot_data.db').cursor().execute("SELECT user_id FROM users").fetchall()
        for user in users:
            try: await context.bot.send_message(chat_id=user[0], text=text)
            except: pass
        await update.message.reply_text("✅ تمت الإذاعة.")
        return
    if 'tiktok.com' not in text: return
    context.user_data['last_url'] = text
    await update.message.reply_text("🎬 اختر:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("فيديو", callback_data="vid")]]))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل النص:")
        return
    url = context.user_data.get('last_url')
    data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
    await query.message.reply_video(video=data.get("hdplay"), caption=CHANNEL_USERNAME)
    await query.message.delete()

async def post_init(application: Application):
    application.create_task(trend_loop(application))

def main():
    # الحل: استخدام token مباشر وبناء التطبيق مرة واحدة
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    
    # أهم خطوة لتفادي الـ Conflict هي drop_pending_updates=True
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
