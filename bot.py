import sqlite3
import requests
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- إعداد السجلات (Logs) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# هذا السطر هو الحل الجذري لإخفاء رسائل 200 OK المزعجة التي تظهر في صورتك
logging.getLogger("httpx").setLevel(logging.WARNING) 

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

# --- 2. ميزة الترند التلقائي (المحدثة والمستقرة) ---
async def send_trends_auto_manual(app):
    try:
        # جلب قائمة الفيديوهات الشائعة مباشرة
        response = requests.get("https://www.tikwm.com/api/feed/list?region=SA&count=1", timeout=10).json()
        videos = response.get('data', {}).get('videos', [])
        
        if not videos:
            logging.error("لم يتم العثور على فيديوهات ترند من المصدر.")
            return
            
        # استخراج رابط الفيديو المباشر من الرد الأول
        video_file = videos[0].get("play")
        title = videos[0].get("title", "🔥 فيديو ترند جديد!")
        
        if not video_file:
            return
        
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        for user in users:
            try: 
                await app.bot.send_video(chat_id=user[0], video=video_file, caption=f"{title}\n\n📌 {CHANNEL_USERNAME}")
                await asyncio.sleep(1.5) # تفادي حظر تليجرام للإرسال السريع
            except Exception as e:
                pass # تجاهل المستخدمين الذين قاموا بحظر البوت
                
    except Exception as e:
        logging.error(f"خطأ في ميزة الترند: {e}")

async def trend_loop(app):
    # حلقة لا نهائية تعمل بأمان في الخلفية
    while True:
        await asyncio.sleep(60) # انتظر دقيقة واحدة بين كل فحص (للتجربة)
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
        # نظام الإحالة (دعوة الأصدقاء)
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
    if update.message.from_user.id != ADMIN_ID: 
        return
        
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    
    keyboard = [[InlineKeyboardButton("📢 إذاعة رسالة للجميع", callback_data="admin_bc")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔹 **لوحة التحكم الخاصة بالمدير:**\n\n👥 عدد المشتركين: {count}\n👀 إجمالي المشاهدات: {views}", 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- 5. معالجة الرسائل النصية (الروابط والإذاعة) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    # التحقق مما إذا كان المدير يقوم بإرسال نص الإذاعة
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        success_count = 0
        for user in users:
            try: 
                await context.bot.send_message(chat_id=user[0], text=text)
                success_count += 1
                await asyncio.sleep(0.05) # تأخير آمن لمنع حظر السبام
            except Exception:
                pass
        await update.message.reply_text(f"✅ تمت الإذاعة بنجاح لـ {success_count} مستخدم.")
        return
        
    # التحقق من رابط تيك توك
    if 'tiktok.com' not in text:
        await update.message.reply_text("❌ عذراً، الرجاء إرسال رابط تيك توك صحيح.")
        return
        
    # حفظ الرابط في الجلسة وعرض خيارات التحميل
    context.user_data['last_url'] = text
    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو (بدون علامة)", callback_data="vid")], 
        [InlineKeyboardButton("🎵 تحميل كملف صوتي (MP3)", callback_data="aud")]
    ]
    await update.message.reply_text("📥 اختر الصيغة التي تريد التحميل بها:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 6. معالجة الأزرار (Callbacks) ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # زر الإذاعة الخاص بالأدمن
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل النص الذي تريد إذاعته الآن:")
        return
        
    # أزرار التحميل
    url = context.user_data.get('last_url')
    if not url: 
        return await query.edit_message_text("❌ انتهت صلاحية الجلسة. أرسل الرابط مرة أخرى.")
        
    await query.edit_message_text("⏳ جاري جلب البيانات ومعالجة الطلب...")
    
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        
        if query.data == "vid":
            video_url = data.get("hdplay") or data.get("play")
            await query.message.reply_video(video=video_url, caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
        elif query.data == "aud":
            audio_url = data.get("music")
            title = data.get("title", "الصوت")
            await query.message.reply_audio(audio=audio_url, caption=f"🎵 {title}\n📌 {CHANNEL_USERNAME}")
            
        await query.message.delete()
    except Exception as e:
        logging.error(f"Download Error: {e}")
        await query.edit_message_text("❌ حدث خطأ أثناء جلب الفيديو. تأكد من أن الرابط صحيح أو أن الفيديو ليس خاصاً.")

# --- 7. التشغيل الآمن ---
async def post_init(application: Application):
    # تشغيل حلقة الترند بشكل آمن بعد أن يبدأ البوت
    application.create_task(trend_loop(application))

def main():
    # بناء التطبيق مع تفريغ التحديثات القديمة لتفادي خطأ (Conflict)
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    # تسجيل الأزرار والنصوص
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    
    print("🚀 البوت يعمل الآن بكامل الميزات وبشكل مستقر...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
