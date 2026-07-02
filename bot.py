import sqlite3
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(level=logging.INFO)

TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
CHANNEL_ID = -1001234567890 
ADMIN_ID = 8192715650

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, views INTEGER DEFAULT 0, downloads INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO stats (id, views, downloads) VALUES (1, 0, 0)")
    conn.commit()
    conn.close()

init_db()

SERVICES = {"tiktok": True, "instagram": True}

async def check_subscription(context, user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

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
    conn = sqlite3.connect('bot_data.db')
    result = conn.cursor().execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    conn.close()
    await update.message.reply_text(f"👥 رابط الدعوة الخاص بك:\nhttps://t.me/{bot_me.username}?start={user_id}\n\n📊 نقاطك الحالية: {points}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    data = conn.cursor().execute("SELECT count(*), (SELECT views FROM stats), (SELECT downloads FROM stats) FROM users").fetchone()
    conn.close()
    keyboard = [
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc"), InlineKeyboardButton("📂 تصدير المستخدمين", callback_data="export")],
        [InlineKeyboardButton("🔄 تصفير النقاط", callback_data="reset_p"), InlineKeyboardButton(f"تيك توك: {'✅' if SERVICES['tiktok'] else '❌'}", callback_data="toggle_tt")],
        [InlineKeyboardButton(f"انستقرام: {'✅' if SERVICES['instagram'] else '❌'}", callback_data="toggle_ig")]
    ]
    await update.message.reply_text(f"🔹 لوحة التحكم:\n👥 المشتركين: {data[0]}\n👀 المشاهدات: {data[1]}\n📥 التحميلات: {data[2]}", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text: return
    user_id = update.message.from_user.id
    
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for u in users:
            try: await context.bot.send_message(chat_id=u[0], text=text)
            except: pass
        await update.message.reply_text("✅ تمت الإذاعة.")
        return
    
    if not await check_subscription(context, user_id):
        await update.message.reply_text(f"⚠️ يجب عليك الاشتراك في القناة أولاً:\n{CHANNEL_USERNAME}")
        return
        
    context.user_data['last_url'] = text
    if ('tiktok.com' in text or 'vt.tiktok.com' in text) and SERVICES['tiktok']:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو (بدون علامة)", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل كملف صوتي (MP3)", callback_data="aud")]]
        await update.message.reply_text("📥 اختر الصيغة التي تريد التحميل بها:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif 'instagram.com' in text and SERVICES['instagram']:
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو الانستقرام", callback_data="vid_ig")]]
        await update.message.reply_text("📥 تم التعرف على رابط الانستقرام:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ عذراً، الرابط غير صحيح أو الخدمة متوقفة.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل النص للإذاعة:")
        return
    if query.data == "export":
        conn = sqlite3.connect('bot_data.db')
        users = conn.cursor().execute("SELECT user_id FROM users").fetchall()
        conn.close()
        with open("users.txt", "w") as f: f.write("\n".join([str(u[0]) for u in users]))
        await query.message.reply_document(document=open("users.txt", "rb"))
        return
    if query.data == "reset_p":
        conn = sqlite3.connect('bot_data.db')
        conn.cursor().execute("UPDATE users SET points = 0")
        conn.commit()
        conn.close()
        await query.message.reply_text("✅ تم تصفير النقاط.")
        return
    if query.data.startswith("toggle_"):
        key = "tiktok" if "tt" in query.data else "instagram"
        SERVICES[key] = not SERVICES[key]
        await admin_panel(query, context)
        return

    if not await check_subscription(context, query.from_user.id): return
    
    url = context.user_data.get('last_url')
    await query.edit_message_text("⏳ جاري التحميل...")
    try:
        conn = sqlite3.connect('bot_data.db')
        conn.cursor().execute("UPDATE stats SET downloads = downloads + 1 WHERE id = 1")
        conn.commit()
        conn.close()
        headers = {'User-Agent': 'Mozilla/5.0'}
        if query.data == "vid_ig":
            resp = requests.get(f"https://tikwm.com/api/insta/dl?url={url}", headers=headers).json()
            await query.message.reply_video(video=resp.get("data", {}).get("video"), caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
        else:
            resp = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, headers=headers, timeout=20)
            data = resp.json().get("data", {})
            if query.data == "vid": await query.message.reply_video(video=data.get("hdplay") or data.get("play"), caption=f"📌 تمت الاستضافة بواسطة {CHANNEL_USERNAME}")
            elif query.data == "aud": await query.message.reply_audio(audio=data.get("music"), caption=f"🎵 {data.get('title')}\n📌 {CHANNEL_USERNAME}")
        await query.message.delete()
    except Exception:
        await query.edit_message_text("❌ فشل التحميل.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
