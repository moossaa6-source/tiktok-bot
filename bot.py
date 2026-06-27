import sqlite3
import requests
import re
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعدادات الأمان
TOKEN = os.environ.get("TOKEN")
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

# خادم مصغر لضمان عمل البوت على Render
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "Bot is running!"
def run_web(): app_web.run(host='0.0.0.0', port=10000)

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, referred_by INTEGER, points INTEGER DEFAULT 0, is_premium INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "No_Username"
    args = context.args
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        referred_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
        if referred_by: cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referred_by,))
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))
        conn.commit()
    conn.close()
    await update.message.reply_text(f"🎉 أهلاً بك يا {update.message.from_user.first_name}!\nالبوت جاهز. أرسل رابط تيك توك للتحميل! 🚀")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_username = (await context.bot.get_me()).username
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    points = result[0] if result else 0
    conn.close()
    await update.message.reply_text(f"👥 **نظام الدعوات:**\n🔗 رابطك: https://t.me/{bot_username}?start={user_id}\n📊 دعواتك: {points}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not re.search(r'tiktok\.com', url):
        await update.message.reply_text("❌ يرجى إرسال رابط تيك توك صحيح.")
        return
    context.user_data['last_tiktok_url'] = url
    keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو HD", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data="aud")]]
    await update.message.reply_text("🎬 اختر الصيغة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get('last_tiktok_url')
    if not url: return await query.edit_message_text("❌ انتهت صلاحية الطلب.")
    
    await query.edit_message_text("⏳ جاري المعالجة...")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        bot_username = (await context.bot.get_me()).username
        caption = f"✨ تم التحميل بواسطة @{bot_username}\n📌 تابعنا: {CHANNEL_USERNAME}"
        share_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📤 شارك البوت مع صديق", switch_inline_query=f"جرب أسرع بوت تحميل تيك توك: @{bot_username}")]])
        
        if query.data == "vid":
            await query.message.reply_video(video=data.get("hdplay") or data.get("play"), caption=caption, reply_markup=share_keyboard)
        else:
            await query.message.reply_audio(audio=data.get("music"), caption=caption, reply_markup=share_keyboard)
        await query.message.delete()
    except Exception:
        await query.edit_message_text("❌ فشل التحميل.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    await update.message.reply_text(f"📊 عدد المستخدمين: {count}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="admin_bc")]]))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل نص الإذاعة الآن:")

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        users = sqlite3.connect('bot_data.db').cursor().execute("SELECT user_id FROM users").fetchall()
        for user in users:
            try: await context.bot.send_message(chat_id=user[0], text=update.message.text)
            except: pass
        await update.message.reply_text("✅ تمت الإذاعة.")

def main():
    threading.Thread(target=run_web).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_click, pattern="^(vid|aud)$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, send_broadcast), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message), group=2)
    app.run_polling()

if __name__ == "__main__":
    main()
