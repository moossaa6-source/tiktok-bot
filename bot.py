import sqlite3
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from playwright.async_api import async_playwright

# إعداد السجلات
logging.basicConfig(level=logging.INFO)

TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
CHANNEL_ID = -1001234567890 # ضع معرف القناة هنا (يجب أن يبدأ بـ -100)
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

# دالة التحقق من الاشتراك
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['left', 'kicked']:
            await update.message.reply_text(f"⚠️ يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:\n{CHANNEL_USERNAME}")
            return False
        return True
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (نفس كود الـ start السابق...)
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك قبل المعالجة
    if not await check_subscription(update, context): return
    
    text = update.message.text
    context.user_data['last_url'] = text
    if 'tiktok.com' in text:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو (بدون علامة)", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل كملف صوتي (MP3)", callback_data="aud")]]
        await update.message.reply_text("📥 اختر الصيغة التي تريد التحميل بها:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif 'instagram.com' in text:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو الانستقرام", callback_data="vid_ig")]]
        await update.message.reply_text("📥 تم التعرف على رابط الانستقرام:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # التحقق من الاشتراك
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
    if member.status in ['left', 'kicked']:
        await query.edit_message_text(f"⚠️ اشترك في القناة أولاً:\n{CHANNEL_USERNAME}")
        return

    url = context.user_data.get('last_url')
    await query.edit_message_text("⏳ جاري التحميل، يرجى الانتظار...")
    
    try:
        if query.data == "vid_ig":
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url)
                video_element = await page.wait_for_selector("video")
                video_url = await video_element.get_attribute("src")
                await browser.close()
                await query.message.reply_video(video=video_url, caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
        else:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, headers=headers, timeout=20)
            data = resp.json().get("data", {})
            if query.data == "vid": await query.message.reply_video(video=data.get("hdplay") or data.get("play"), caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
            elif query.data == "aud": await query.message.reply_audio(audio=data.get("music"), caption=f"🎵 {data.get('title')}\n📌 {CHANNEL_USERNAME}")
        
        await query.message.delete()
    except Exception as e:
        await query.edit_message_text("❌ فشل التحميل، الرابط قد يكون خاصاً أو مقيداً.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", lambda u, c: None)) # اختصار
    app.add_handler(CommandHandler("admin", lambda u, c: None)) # اختصار
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
