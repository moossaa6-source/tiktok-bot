import sqlite3
import requests
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد السجلات (Logs) لتتبع أي خطأ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING) 

TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

# --- 1. إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    # جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0)''')
    # جدول الإحصائيات
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, views INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO stats (id, views) VALUES (1, 0)")
    conn.commit()
    conn.close()

init_db()

# --- 2. ميزة الترند التلقائي ---
async def send_trends_auto_manual(app):
    logging.info("--- بدء فحص الترند التلقائي ---")
    try:
        response = requests.get("https://www.tikwm.com/api/feed/list?region=SA&count=1", timeout=10).json()
        videos = response.get('data', {}).get('videos', [])
        
        if not videos:
            logging.info("لم يتم العثور على فيديوهات ترند.")
            return
            
        video_file = videos[0].get("play")
        title = videos[0].get("title", "فيديو ترند جديد")
        
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        for user in users:
            try: 
                await app.bot.send_video(chat_id=user[0], video=video_file, caption=f"🔥 {title}\n📌 {CHANNEL_USERNAME}")
                await asyncio.sleep(1.5)
            except Exception as e:
                logging.info(f"فشل الإرسال لـ {user[0]}: {e}")
                
    except Exception as e:
        logging.error(f"خطأ في دالة الترند: {e}")

async def trend_loop(app):
    while True:
        await asyncio.sleep(60) # توقيت الترند
        await send_trends_auto_manual(app)

# --- 3. الأوامر (Start, Share) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE stats SET views = views + 1 WHERE id = 1")
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        args = context.args
        referred_by = int(args[0]) if args and args[0].isdigit() else None
        if referred_by and referred_by != user_id:
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referred_by,))
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))
        conn.commit()
    conn.close()
    await update.message.reply_text("🎉 أهلاً بك! أرسل رابط تيك توك للتحميل 🚀")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_username = (await context.bot.get_me()).username
    conn = sqlite3.connect('bot_data.db')
    result = conn.cursor().execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    points = result[0] if result else 0
    await update.message.reply_text(f"👥 رابطك: https://t.me/{bot_username}?start={user_id}\n📊 نقاطك: {points}")

# --- 4. أوامر الأدمن ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    await update.message.reply_text(f"🔹 لوحة التحكم:\n👥 المشتركين: {count}\n👀 المشاهدات: {views}", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc")]]))

# --- 5. معالجة الرسائل والتحميل ---
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
        if query.data == "vid": await query.message.reply_video(video=data.get("hdplay"), caption=f"📌 {CHANNEL_USERNAME}")
        else: await query.message.reply_audio(audio=data.get("music"))
        await query.message.delete()
    except Exception as e: await query.edit_message_text(f"❌ خطأ: {e}")

# --- 6. التشغيل ---
async def post_init(application: Application):
    application.create_task(trend_loop(application))

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
