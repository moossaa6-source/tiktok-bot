import sqlite3
import requests
import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# التوكن الجديد
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

def get_latest_trend_url():
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.tiktok.com/tag/foryou", download=False)
            return info['entries'][0]['url']
    except: return None

async def send_trends_auto(context: ContextTypes.DEFAULT_TYPE):
    trend_url = get_latest_trend_url()
    if not trend_url: return
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": trend_url, "hd": 1}, timeout=15).json().get("data", {})
        video_file = data.get("hdplay") or data.get("play")
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for user in users:
            try: 
                await context.bot.send_video(chat_id=user[0], video=video_file, caption="🔥 فيديو ترند جديد!")
                await asyncio.sleep(1)
            except: pass
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.job_queue.get_jobs_by_name('trend_job'):
        context.job_queue.run_repeating(send_trends_auto, interval=1800, first=10, name='trend_job')
    
    user_id = update.message.from_user.id
    args = context.args
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE stats SET views = views + 1 WHERE id = 1")
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

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    await update.message.reply_text(f"🔹 لوحة التحكم:\n👥 المشتركين: {count}\n👀 المشاهدات: {views}", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc")]]))

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
    if 'tiktok.com' not in text:
        await update.message.reply_text("❌ أرسل رابط تيك توك.")
        return
    context.user_data['last_url'] = text
    keyboard = [[InlineKeyboardButton("🎬 فيديو HD", callback_data="vid")], [InlineKeyboardButton("🎵 صوت MP3", callback_data="aud")]]
    await update.message.reply_text("🎬 اختر الصيغة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل نص الإذاعة:")
        return
    url = context.user_data.get('last_url')
    if not url: return await query.edit_message_text("❌ انتهت الجلسة.")
    await query.edit_message_text("⏳ جاري المعالجة...")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        if query.data == "vid":
            await query.message.reply_video(video=data.get("hdplay"), caption=f"📌 {CHANNEL_USERNAME}")
        else:
            await query.message.reply_audio(audio=data.get("music"))
        await query.message.delete()
    except: await query.edit_message_text("❌ فشل التحميل.")

def main():
    # استخدام Webhook لمنع التعارض (Conflict)
    url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    
    if url:
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            url_path=TOKEN,
            webhook_url=f"https://{url}/{TOKEN}"
        )
    else:
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
