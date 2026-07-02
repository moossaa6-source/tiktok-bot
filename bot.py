import sqlite3
import requests
import asyncio
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد سجلات النظام
logging.basicConfig(level=logging.INFO)

TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

# --- 1. إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, views INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO stats (id, views) VALUES (1, 0)")
    conn.commit()
    conn.close()

init_db()

# --- 2. أوامر المستخدمين ---
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
    await update.message.reply_text("🎉 أهلاً بك! أرسل رابط تيك توك أو انستقرام للتحميل 🚀")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_me = await context.bot.get_me()
    bot_username = bot_me.username
    conn = sqlite3.connect('bot_data.db')
    result = conn.cursor().execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    conn.close()
    link = f"https://t.me/{bot_username}?start={user_id}"
    await update.message.reply_text(f"👥 رابط الدعوة الخاص بك:\n{link}\n\n📊 نقاطك الحالية: {points}")

# --- 3. لوحة التحكم ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    keyboard = [[InlineKeyboardButton("📢 إذاعة رسالة للجميع", callback_data="admin_bc")]]
    await update.message.reply_text(f"🔹 **لوحة التحكم الخاصة بالمدير:**\n\n👥 عدد المشتركين: {count}\n👀 إجمالي المشاهدات: {views}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 4. معالجة الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for user in users:
            try: await context.bot.send_message(chat_id=user[0], text=text)
            except: pass
        await update.message.reply_text("✅ تمت الإذاعة بنجاح.")
        return
    context.user_data['last_url'] = text
    if 'tiktok.com' in text:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو (بدون علامة)", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل كملف صوتي (MP3)", callback_data="aud")]]
        await update.message.reply_text("📥 اختر الصيغة:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif 'instagram.com' in text:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو الانستقرام", callback_data="vid_ig")]]
        await update.message.reply_text("📥 تم التعرف على رابط الانستقرام:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ رابط غير مدعوم.")

# --- 5. تحميل الملفات ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل النص للإذاعة:")
        return
    url = context.user_data.get('last_url')
    await query.edit_message_text("⏳ جاري المعالجة...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}

    if query.data == "vid_ig":
        try:
            ydl_opts = {
                'format': 'best', 
                'quiet': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_url = info.get('url')
            await query.message.reply_video(video=video_url, caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
            await query.message.delete()
        except Exception as e:
            logging.error(f"IG Error: {e}")
            await query.edit_message_text("❌ حدث خطأ، تأكد من أن الرابط عام وليس خاصاً.")
        return

    try:
        response = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, headers=headers, timeout=20)
        data = response.json().get("data", {})
        if query.data == "vid":
            video_url = data.get("hdplay") or data.get("play")
            await query.message.reply_video(video=video_url, caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
        elif query.data == "aud":
            await query.message.reply_audio(audio=data.get("music"), caption=f"🎵 {data.get('title')}\n📌 {CHANNEL_USERNAME}")
        await query.message.delete()
    except:
        await query.edit_message_text("❌ حدث خطأ في تيك توك.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    print("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
