import sqlite3
import requests
import re
import os
import asyncio
import yt_dlp
from datetime import datetime, timedelta  # إضافة هذه المكتبة ضروري
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# الإعدادات
TOKEN = os.environ.get("TOKEN")
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trends (id INTEGER PRIMARY KEY, url TEXT)''')
    conn.commit()
    conn.close()

init_db()

async def fetch_trends():
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True, 'playlist_items': '1,2,3'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.tiktok.com/tag/trending", download=False)
            return [entry['url'] for entry in info.get('entries', [])]
    except Exception as e:
        print(f"خطأ في جلب الترند: {e}")
        return []

async def send_daily_trends(app: Application):
    trends = await fetch_trends()
    if not trends: return
    conn = sqlite3.connect('bot_data.db')
    users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
    conn.close()
    msg = "🔥 ترند تيك توك اليوم:\n" + "\n".join(trends)
    for user in users:
        try:
            await app.bot.send_message(chat_id=user[0], text=msg)
            await asyncio.sleep(0.1)
        except: continue

async def post_init(application: Application):
    scheduler = AsyncIOScheduler()
    # تصحيح التوقيت هنا باستخدام datetime
    run_time = datetime.now() + timedelta(seconds=10)
    scheduler.add_job(send_daily_trends, 'date', run_date=run_time, args=[application])
    scheduler.add_job(send_daily_trends, 'cron', hour=9, minute=0, args=[application])
    scheduler.start()

# --- باقي الكود كما هو (start, share, handle_message, button_click, main) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        referred_by = int(args[0]) if args and args[0].isdigit() else None
        if referred_by: cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referred_by,))
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, update.message.from_user.username, referred_by))
        conn.commit()
    conn.close()
    await update.message.reply_text("🎉 أهلاً بك! أرسل رابط تيك توك للتحميل 🚀")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_username = (await context.bot.get_me()).username
    conn = sqlite3.connect('bot_data.db')
    result = conn.cursor().execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    conn.close()
    await update.message.reply_text(f"👥 رابطك: https://t.me/{bot_username}?start={user_id}\n📊 نقاطك: {points}")

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
    if not re.search(r'tiktok\.com', text):
        await update.message.reply_text("❌ عذراً، أرسل رابط تيك توك صحيحاً.")
        return
    context.user_data['last_tiktok_url'] = text
    keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو HD", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data="aud")]]
    await update.message.reply_text("🎬 اختر الصيغة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل نص الإذاعة للأعضاء:")
        return
    url = context.user_data.get('last_tiktok_url')
    if not url: return await query.edit_message_text("❌ انتهت الجلسة.")
    await query.edit_message_text("⏳ جاري المعالجة...")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        if query.data == "vid":
            await query.message.reply_video(video=data.get("hdplay") or data.get("play"), caption=f"📌 تابعنا: {CHANNEL_USERNAME}")
        else:
            await query.message.reply_audio(audio=data.get("music"), caption=f"📌 تابعنا: {CHANNEL_USERNAME}")
        await query.message.delete()
    except: await query.edit_message_text("❌ فشل التحميل.")

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", lambda u, c: u.message.reply_text("📊", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc")]]))))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
