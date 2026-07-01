import sqlite3
import requests
import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# التوكن والإعدادات
TOKEN = "8895284125:AAEKiyC1Jlj-6vBpyz0-PLylDudh6S3o1w4"
CHANNEL_USERNAME = '@MyDesign_Channels'
ADMIN_ID = 8192715650

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    # جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY, 
                        username TEXT, 
                        referred_by INTEGER, 
                        points INTEGER DEFAULT 0)''')
    # جدول الإحصائيات
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, views INTEGER DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO stats (id, views) VALUES (1, 0)")
    conn.commit()
    conn.close()

init_db()

# دالة البداية ونظام الإحالة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    args = context.args
    
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # زيادة المشاهدات
    cursor.execute("UPDATE stats SET views = views + 1 WHERE id = 1")
    
    # التحقق من وجود المستخدم
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        referred_by = int(args[0]) if args and args[0].isdigit() else None
        if referred_by:
            # إضافة نقطة للمُحيل
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referred_by,))
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))
        conn.commit()
    conn.close()
    
    await update.message.reply_text("🎉 أهلاً بك في بوت تحميل تيك توك!\nأرسل رابط الفيديو للبدء 🚀")

# ميزة مشاركة الرابط
async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot_username = (await context.bot.get_me()).username
    conn = sqlite3.connect('bot_data.db')
    result = conn.cursor().execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    conn.close()
    await update.message.reply_text(f"👥 رابط الدعوة الخاص بك:\nhttps://t.me/{bot_username}?start={user_id}\n\n📊 نقاطك الحالية: {points}")

# لوحة تحكم الأدمن
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_data.db')
    count = conn.cursor().execute("SELECT count(*) FROM users").fetchone()[0]
    views = conn.cursor().execute("SELECT views FROM stats WHERE id = 1").fetchone()[0]
    conn.close()
    await update.message.reply_text(f"🔹 لوحة التحكم:\n👥 عدد المشتركين: {count}\n👀 إجمالي المشاهدات: {views}", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة للكل", callback_data="admin_bc")]]))

# معالجة الروابط
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # معالجة الإذاعة
    if update.message.from_user.id == ADMIN_ID and context.user_data.get('waiting_for_bc'):
        context.user_data['waiting_for_bc'] = False
        users = sqlite3.connect('bot_data.db').cursor().execute("SELECT user_id FROM users").fetchall()
        for user in users:
            try: await context.bot.send_message(chat_id=user[0], text=text)
            except: pass
        await update.message.reply_text("✅ تمت الإذاعة بنجاح.")
        return
        
    if 'tiktok.com' not in text:
        await update.message.reply_text("❌ يرجى إرسال رابط تيك توك صحيح.")
        return
        
    context.user_data['last_url'] = text
    keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو HD", callback_data="vid")], [InlineKeyboardButton("🎵 تحميل صوت MP3", callback_data="aud")]]
    await update.message.reply_text("🎬 اختر الصيغة المناسبة:", reply_markup=InlineKeyboardMarkup(keyboard))

# تنفيذ الأزرار
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "admin_bc":
        context.user_data['waiting_for_bc'] = True
        await query.message.reply_text("📥 أرسل نص الإذاعة الآن:")
        return
        
    url = context.user_data.get('last_url')
    if not url: return await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مرة أخرى.")
    
    await query.edit_message_text("⏳ جاري المعالجة... يرجى الانتظار.")
    try:
        data = requests.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=15).json().get("data", {})
        if query.data == "vid":
            await query.message.reply_video(video=data.get("hdplay"), caption=f"📌 {CHANNEL_USERNAME}")
        else:
            await query.message.reply_audio(audio=data.get("music"))
        await query.message.delete()
    except Exception as e:
        await query.edit_message_text(f"❌ فشل التحميل، حاول لاحقاً.\nالخطأ: {str(e)}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    
    print("البوت يعمل الآن بكامل الميزات...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
