import sqlite3
import requests
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد سجلات النظام لتتبع الأخطاء بدقة
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

# --- 2. ميزة الترند التلقائي (تعديل جذري وشامل لضمان الاستقرار) ---
async def send_trends_auto_manual(app):
    logging.info("--- بدء فحص الترند التلقائي ---")
    try:
        response_raw = requests.get("https://www.tikwm.com/api/feed/list?region=SA&count=1", timeout=15)
        res = response_raw.json()

        # استخراج قائمة الفيديوهات بغض النظر عن هيكل الـ API
        videos = []
        if isinstance(res, dict):
            data = res.get('data', {})
            videos = data.get('videos', []) if isinstance(data, dict) else []
        elif isinstance(res, list):
            for item in res:
                if isinstance(item, dict) and 'videos' in item:
                    videos = item.get('videos', [])
                    break
        
      # استبدل سطر logging.warning("لم يتم العثور على فيديوهات في الاستجابة") بـ:
        if not videos or not isinstance(videos, list) or len(videos) == 0:
            logging.warning(f"لم يتم العثور على فيديوهات. الاستجابة كانت: {res}")
            return
        
        first_video = videos[0]
        video_file = first_video.get("play") if isinstance(first_video, dict) else None
        
        if not video_file:
            return

        # جلب قائمة المستخدمين
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        # إرسال الفيديو للمستخدمين
        for user in users:
            try:
                await app.bot.send_video(
                    chat_id=user[0], 
                    video=video_file, 
                    caption=f"🔥 فيديو ترند جديد!\n📌 {CHANNEL_USERNAME}"
                )
                await asyncio.sleep(0.5) 
            except Exception:
                continue
    except Exception as e:
        logging.error(f"خطأ في الترند: {e}")

async def trend_loop(app):
    while True:
        await asyncio.sleep(60) # فاصل زمني: 60 ثانية
        await send_trends_auto_manual(app)

# --- 3. أوامر المستخدمين (Start, Share) ---
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
    await update.message.reply_text("🎉 أهلاً بك! أرسل رابط تيك توك للتحميل بصيغة HD أو MP3 🚀")

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

# --- 4. أوامر لوحة التحكم (Admin Panel) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    keyboard = [[InlineKeyboardButton("📢 إذاعة رسالة للجميع", callback_data="admin_bc")]]
    await update.message.reply_text(f"🔹 **لوحة التحكم الخاصة بالمدير:**\n\n👥 عدد المشتركين: {count}\n👀 إجمالي المشاهدات: {views}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 5. معالجة الرسائل النصية ---
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
            except Exception: pass
        await update.message.reply_text("✅ تمت الإذاعة بنجاح.")
        return
    if 'tiktok.com' not in text:
        await update.message.reply_text("❌ عذراً، الرجاء إرسال رابط تيك توك صحيح.")
        return
    context.user_data['last_url'] = text
    keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو (بدون علامة)", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل كملف صوتي (MP3)", callback_data="aud")]]
    await update.message.reply_text("📥 اختر الصيغة التي تريد التحميل بها:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 6. معالجة الأزرار ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل النص الذي تريد إذاعته الآن:")
        return
    url = context.user_data.get('last_url')
    if not url: return await query.edit_message_text("❌ انتهت صلاحية الجلسة.")
    await query.edit_message_text("⏳ جاري جلب البيانات...")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        if query.data == "vid":
            await query.message.reply_video(video=data.get("hdplay") or data.get("play"), caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
        elif query.data == "aud":
            await query.message.reply_audio(audio=data.get("music"), caption=f"🎵 {data.get('title', 'الصوت')}\n📌 {CHANNEL_USERNAME}")
        await query.message.delete()
    except Exception:
        await query.edit_message_text("❌ حدث خطأ، تأكد من الرابط.")

# --- 7. التشغيل الآمن ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    async def run_bot():
        async with app:
            await app.initialize()
            asyncio.create_task(trend_loop(app))
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            print("🚀 البوت يعمل الآن بكامل الميزات وبشكل مستقر...")
            await asyncio.Event().wait()
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
