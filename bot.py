"""
Telegram Blood Donation Bot - Complete Single File
Author: Blood Donation System
Requires: python-telegram-bot v20+, psycopg2-binary

requirements.txt:
    python-telegram-bot==20.7
    psycopg2-binary==2.9.9
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
from telegram.constants import ParseMode

# ============== CONFIGURATION ==============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8776916298:AAHZ90E6d1wjmKWRi2jpxMJBqV_5pBKuLbY")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 8377692677
ADMIN_IDS = [8377692677]
OWNER_NAME = "MD MASUM"
OWNER_PHONE = "+8801345452458"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Conversation states
NAME, PHONE, ADDRESS, BLOOD_GROUP, LAST_DONATION = range(5)
UPDATE_DATE = 5

# ============== DATABASE CONNECTION ==============
def get_db_connection():
    """Create and return a PostgreSQL database connection using DATABASE_URL."""
    if not DATABASE_URL:
        print("=" * 60)
        print("FATAL ERROR: DATABASE_URL is not set!")
        print("Fix: Go to Railway → your project → PostgreSQL plugin")
        print("Then link it to your bot service under Variables.")
        print("=" * 60)
        raise EnvironmentError("DATABASE_URL environment variable is not set.")
    # Railway may prefix the URL with 'postgres://' but psycopg2 needs 'postgresql://'
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    return conn

# ============== DATABASE SETUP ==============
def init_db():
    """Initialize the PostgreSQL database and create tables if they don't exist."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS donors (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            name TEXT,
            blood_group TEXT,
            phone TEXT,
            address TEXT,
            status TEXT DEFAULT 'pending',
            registered_at TEXT,
            last_donation_date TEXT
        )
    ''')
    # Optional: create emergency_requests table if needed in future
    c.execute('''
        CREATE TABLE IF NOT EXISTS emergency_requests (
            id SERIAL PRIMARY KEY,
            requester_name TEXT,
            blood_group TEXT,
            location TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    c.close()
    conn.close()

def add_donor(user_id, name, blood_group, phone, address, last_donation_date):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO donors
           (user_id, name, blood_group, phone, address, last_donation_date, status, registered_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (user_id, name, blood_group, phone, address, last_donation_date,
         'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    c.close()
    conn.close()

def get_donor(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT name, blood_group, phone, address, last_donation_date, status FROM donors WHERE user_id = %s',
            (user_id,)
        )
        result = c.fetchone()
        c.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Database error in get_donor: {e}")
        return None

def get_all_donors():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT id, user_id, name, blood_group, phone, address, last_donation_date, status FROM donors'
        )
        result = c.fetchall()
        c.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Database error in get_all_donors: {e}")
        return []

def get_pending_donors():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT id, user_id, name, blood_group, phone, address, last_donation_date FROM donors WHERE status = %s',
            ('pending',)
        )
        result = c.fetchall()
        c.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Database error in get_pending_donors: {e}")
        return []

def approve_donor(donor_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE donors SET status = %s WHERE id = %s', ('approved', donor_id))
        conn.commit()
        c.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error in approve_donor: {e}")
        return False

def search_donors(blood_group):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT name, phone, address, last_donation_date FROM donors WHERE blood_group = %s AND status = %s',
            (blood_group.upper(), 'approved')
        )
        result = c.fetchall()
        c.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Database error in search_donors: {e}")
        return []

def is_eligible_to_donate(last_donation_date):
    if not last_donation_date:
        return True
    try:
        last_date = datetime.strptime(last_donation_date, '%Y-%m-%d')
        days_diff = (datetime.now() - last_date).days
        return days_diff >= 90
    except Exception:
        return True

# ============== KEYBOARDS ==============
def main_keyboard():
    keyboard = [
        ["🩸 ডোনার খুঁজুন", "🚨 জরুরি রিকোয়েস্ট"],
        ["📝 রেজিস্ট্রেশন", "ℹ️ আমার তথ্য"],
        ["📅 তারিখ আপডেট", "❓ সাহায্য"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def admin_keyboard():
    keyboard = [
        ["📢 ব্রডকাস্ট", "👥 ইউজার লিস্ট"],
        ["🩸 ইমার্জেন্সি লিস্ট", "✅ ডোনার ভেরিফাই"],
        ["❌ ডোনার ডিলিট", "🔙 মেনুতে ফিরুন"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ============== START ==============
async def start(update: Update, context):
    user_id = update.effective_user.id
    reply_markup = admin_keyboard() if is_admin(user_id) else main_keyboard()
    await update.message.reply_text(
        "🩸 *রক্তদান বটে স্বাগতম!*\n\n"
        "যে ব্যক্তি একটি প্রাণকে বাঁচায়, সে যেন সমগ্র মানবজাতিকে বাঁচাল।\n\n"
        "হযরত মুহাম্মদ (সা.) বলেছেন,\n"
        "\"মানুষের মধ্যে সেই ব্যক্তি উত্তম, যে মানুষের জন্য সবচেয়ে বেশি উপকারী।\"\n\n"
        "আমাদের বটটি জরুরি মুহূর্তে রক্তদাতা এবং রক্তগ্রহীতার মধ্যে সংযোগ স্থাপন করে।\n\n"
        "নিচের বাটন বা কমান্ড ব্যবহার করুন:\n"
        "/search - রক্তদাতা খুঁজুন\n"
        "/emergency - জরুরি রিকোয়েস্ট\n"
        "/myinfo - আপনার তথ্য দেখুন\n"
        "/update_donation_date - শেষ রক্তদানের তারিখ আপডেট করুন\n"
        "/help - সাহায্য",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# ============== SEARCH COMMAND ==============
async def search_command(update: Update, context):
    await update.message.reply_text(
        "🔍 *রক্তদাতা খুঁজুন*\n\n"
        "আপনার প্রয়োজনীয় ব্লাড গ্রুপ লিখুন (A+, A-, B+, B-, AB+, AB-, O+, O-):",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['action'] = 'search'

# ============== EMERGENCY COMMAND ==============
async def emergency_command(update: Update, context):
    await update.message.reply_text(
        "🚨 *জরুরি রক্তের আবেদন*\n\n"
        "আপনার প্রয়োজনীয় ব্লাড গ্রুপ লিখুন (A+, A-, B+, B-, AB+, AB-, O+, O-):",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['action'] = 'emergency'

# ============== MYINFO COMMAND ==============
async def myinfo_command(update: Update, context):
    donor = get_donor(update.effective_user.id)
    if donor:
        name, blood, phone, address, last_donation, status = donor
        status_emoji = "✅ অনুমোদিত" if status == "approved" else "⏳ পেন্ডিং"
        last_donation_text = last_donation if last_donation else "কখনো না"
        await update.message.reply_text(
            f"*আপনার তথ্য*\n\n"
            f"👤 নাম: {name}\n"
            f"🩸 ব্লাড গ্রুপ: {blood}\n"
            f"📞 ফোন: {phone}\n"
            f"📍 ঠিকানা: {address}\n"
            f"📅 শেষ রক্তদানের তারিখ: {last_donation_text}\n"
            f"⭐ স্ট্যাটাস: {status_emoji}",
            reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ আপনি এখনও রক্তদাতা হিসেবে নিবন্ধিত নন।\n\n"
            "'রেজিস্ট্রেশন' বাটনে ক্লিক করুন অথবা /register লিখুন।",
            reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
        )

# ============== HELP COMMAND ==============
async def help_command(update: Update, context):
    await update.message.reply_text(
        f"*সাহায্য ও সহায়তা*\n\n"
        f"👨 মালিক: {OWNER_NAME}\n"
        f"📞 ফোন: {OWNER_PHONE}\n\n"
        f"*বটের কমান্ডসমূহ:*\n"
        f"/start - প্রধান মেনু দেখুন\n"
        f"/search - রক্তদাতা খুঁজুন\n"
        f"/emergency - জরুরি রিকোয়েস্ট পাঠান\n"
        f"/myinfo - আপনার তথ্য দেখুন\n"
        f"/register - রক্তদাতা হিসেবে নিবন্ধন করুন\n"
        f"/update_donation_date - শেষ রক্তদানের তারিখ আপডেট করুন\n"
        f"/admin - অ্যাডমিন প্যানেল (শুধু অ্যাডমিন)\n"
        f"/help - এই সাহায্য দেখুন\n\n"
        f"*বৈশিষ্ট্যসমূহ:*\n"
        f"• রক্তদাতা হিসেবে নিবন্ধন করুন\n"
        f"• ব্লাড গ্রুপ অনুযায়ী দাতা খুঁজুন\n"
        f"• জরুরি রক্তের আবেদন করুন\n"
        f"• অ্যাডমিন অনুমোদন ব্যবস্থা\n\n"
        f"রক্তদান করুন, জীবন বাঁচান! 🩸",
        reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# ============== ADMIN COMMANDS ==============
async def admin_command(update: Update, context):
    if update.effective_user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📋 পেন্ডিং ডোনার", callback_data='pending')],
            [InlineKeyboardButton("📊 পরিসংখ্যান", callback_data='stats')]
        ]
        await update.message.reply_text(
            "*অ্যাডমিন কমান্ড*\n\nএকটি অপশন নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। আপনি অ্যাডমিন নন।")

async def broadcast_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। শুধু অ্যাডমিন।")
        return
    if not context.args:
        await update.message.reply_text(
            "📢 *ব্রডকাস্ট ব্যবহার:*\n/broadcast আপনার বার্তা\n\nউদাহরণ:\n/broadcast আগামীকাল রক্তদান ক্যাম্প অনুষ্ঠিত হবে!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    message_text = ' '.join(context.args)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT user_id FROM donors')
    users = c.fetchall()
    c.close()
    conn.close()
    if not users:
        await update.message.reply_text("ডাটাবেসে কোনো ইউজার পাওয়া যায়নি।")
        return
    sent_count = 0
    fail_count = 0
    for user in users:
        try:
            await context.bot.send_message(
                user[0],
                f"📢 *ব্রডকাস্ট বার্তা*\n\n{message_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent_count += 1
        except Exception:
            fail_count += 1
    await update.message.reply_text(
        f"✅ ব্রডকাস্ট সম্পন্ন!\n\n📨 পাঠানো হয়েছে: {sent_count}\n❌ ব্যর্থ: {fail_count}"
    )

async def users_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। শুধু অ্যাডমিন।")
        return
    donors = get_all_donors()
    if not donors:
        await update.message.reply_text("কোনো নিবন্ধিত ইউজার নেই।")
        return
    total = len(donors)
    approved = len([d for d in donors if d[7] == 'approved'])
    pending = total - approved
    result = f"👥 *ইউজার লিস্ট*\n\n"
    result += f"মোট: {total} | ✅ অনুমোদিত: {approved} | ⏳ পেন্ডিং: {pending}\n\n"
    for d in donors[:10]:
        status_icon = "✅" if d[7] == 'approved' else "⏳"
        last_donation_text = d[6] if d[6] else "কখনো না"
        result += f"{status_icon} *আইডি:{d[0]}* | {d[2]} - {d[3]}\n"
        result += f"   📞 {d[4]} | 📍 {d[5]}\n"
        result += f"   📅 শেষ দান: {last_donation_text}\n\n"
    if total > 10:
        result += f"\n_মোট {total} জনের মধ্যে ১০ জন দেখানো হচ্ছে।_"
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

async def emergency_list_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। শুধু অ্যাডমিন।")
        return
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT id, requester_name, blood_group, location, created_at FROM emergency_requests ORDER BY id DESC LIMIT 20'
        )
        requests = c.fetchall()
        c.close()
        conn.close()
    except Exception as e:
        await update.message.reply_text("কোনো জরুরি রিকোয়েস্ট পাওয়া যায়নি।")
        return
    if not requests:
        await update.message.reply_text("কোনো জরুরি রিকোয়েস্ট পাওয়া যায়নি।")
        return
    result = f"🩸 *জরুরি রিকোয়েস্টের ইতিহাস*\n\n"
    for r in requests:
        result += f"🆔 #{r[0]}\n👤 {r[1]}\n🩸 {r[2]} | 📍 {r[3]}\n⏰ {r[4]}\n\n"
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

async def verify_donor_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। শুধু অ্যাডমিন।")
        return
    if not context.args:
        await update.message.reply_text(
            "✅ *ডোনার ভেরিফাই ব্যবহার:*\n/verify_donor <ডোনার আইডি>\n\nউদাহরণ: /verify_donor 1",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        donor_id = int(context.args[0])
    except (ValueError, IndexError):
        await update.message.reply_text("❌ ভুল ডোনার আইডি। সঠিক নম্বর দিন।")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, user_id, name, status FROM donors WHERE id = %s', (donor_id,))
    donor = c.fetchone()
    if not donor:
        await update.message.reply_text(f"❌ আইডি {donor_id} সম্পন্ন কোনো ডোনার পাওয়া যায়নি।")
        c.close()
        conn.close()
        return
    donor_id_db, donor_user_id, donor_name, current_status = donor
    if current_status == 'approved':
        await update.message.reply_text(f"ℹ️ ডোনার *{donor_name}* ইতিমধ্যে ভেরিফাইড।", parse_mode=ParseMode.MARKDOWN)
        c.close()
        conn.close()
        return
    c.execute('UPDATE donors SET status = %s WHERE id = %s', ('approved', donor_id_db))
    conn.commit()
    c.close()
    conn.close()
    await update.message.reply_text(f"✅ ডোনার *{donor_name}* সফলভাবে ভেরিফাইড হয়েছে!", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(
            donor_user_id,
            f"🎉 *অভিনন্দন {donor_name}!*\n\nআপনার রক্তদাতা নিবন্ধন অনুমোদিত হয়েছে।\nজীবন বাঁচাতে সাহায্য করার জন্য ধন্যবাদ! 🩸",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

async def remove_donor_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ অ্যাক্সেস অস্বীকৃত। শুধু অ্যাডমিন।")
        return
    if not context.args:
        await update.message.reply_text(
            "❌ *ডোনার ডিলিট ব্যবহার:*\n/remove_donor <ডোনার আইডি>\n\nউদাহরণ: /remove_donor 1",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        donor_id = int(context.args[0])
    except (ValueError, IndexError):
        await update.message.reply_text("❌ ভুল ডোনার আইডি। সঠিক নম্বর দিন।")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, user_id, name FROM donors WHERE id = %s', (donor_id,))
    donor = c.fetchone()
    if not donor:
        await update.message.reply_text(f"❌ আইডি {donor_id} সম্পন্ন কোনো ডোনার পাওয়া যায়নি।")
        c.close()
        conn.close()
        return
    donor_id_db, donor_user_id, donor_name = donor
    c.execute('DELETE FROM donors WHERE id = %s', (donor_id_db,))
    conn.commit()
    c.close()
    conn.close()
    await update.message.reply_text(f"🗑️ ডোনার *{donor_name}* সরানো হয়েছে!", parse_mode=ParseMode.MARKDOWN)
    try:
        await context.bot.send_message(
            donor_user_id,
            f"❌ *আপনার রক্তদাতা নিবন্ধন অ্যাডমিন দ্বারা সরানো হয়েছে।*\n\n"
            f"👨 মালিক: {OWNER_NAME}\n📞 যোগাযোগ: {OWNER_PHONE}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

# ============== UPDATE DONATION DATE CONVERSATION ==============
async def update_donation_start(update: Update, context):
    """Entry point: /update_donation_date command OR '📅 তারিখ আপডেট' button"""
    user_id = update.effective_user.id
    donor = get_donor(user_id)
    if not donor:
        await update.message.reply_text(
            "❌ আপনি একজন নিবন্ধিত রক্তদাতা নন।\n\nপ্রথমে /register দিয়ে নিবন্ধন করুন।",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "📅 আপনার শেষ রক্তদানের তারিখ লিখুন (YYYY-MM-DD ফরম্যাটে):\n\nউদাহরণ: 2026-04-21\n\nবাতিল করতে /cancel লিখুন।"
    )
    return UPDATE_DATE

async def update_donation_receive(update: Update, context):
    """Receive and save the donation date"""
    date_text = update.message.text.strip()
    try:
        donation_date = datetime.strptime(date_text, '%Y-%m-%d')
        if donation_date > datetime.now():
            await update.message.reply_text(
                "❌ ভবিষ্যতের তারিখ দেওয়া যাবে না। সঠিক তারিখ দিন (YYYY-MM-DD):\nউদাহরণ: 2026-04-21"
            )
            return UPDATE_DATE
    except ValueError:
        await update.message.reply_text(
            "❌ ভুল ফরম্যাট। তারিখ দিন YYYY-MM-DD ফরম্যাটে:\nউদাহরণ: 2026-04-21"
        )
        return UPDATE_DATE

    user_id = update.effective_user.id
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE donors SET last_donation_date = %s WHERE user_id = %s', (date_text, user_id))
    conn.commit()
    c.close()
    conn.close()

    next_date = (donation_date + timedelta(days=90)).strftime('%Y-%m-%d')
    reply_markup = admin_keyboard() if is_admin(user_id) else main_keyboard()
    await update.message.reply_text(
        f"✅ আপনার রক্তদানের তারিখ আপডেট করা হয়েছে: {date_text}\n\n"
        f"📅 আপনার পরবর্তী উপযুক্ত তারিখ: {next_date}\n\n"
        f"রক্তদান করে মানুষ বাঁচাতে সাহায্য করুন! 🩸",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def update_donation_cancel(update: Update, context):
    """Cancel update donation date"""
    reply_markup = admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
    await update.message.reply_text("❌ তারিখ আপডেট বাতিল করা হয়েছে।", reply_markup=reply_markup)
    return ConversationHandler.END

# ============== REGISTRATION CONVERSATION ==============
async def register_start(update: Update, context):
    await update.message.reply_text(
        "📝 *রক্তদাতা নিবন্ধন*\n\nধাপ ১/৫: অনুগ্রহ করে আপনার পূর্ণ নাম লিখুন:",
        parse_mode=ParseMode.MARKDOWN
    )
    return NAME

async def register_name(update: Update, context):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        "📞 *ধাপ ২/৫: ফোন নম্বর*\n\nআপনার ফোন নম্বর লিখুন (কান্ট্রি কোড সহ):\nউদাহরণ: +8801XXXXXXXXX",
        parse_mode=ParseMode.MARKDOWN
    )
    return PHONE

async def register_phone(update: Update, context):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text(
        "📍 *ধাপ ৩/৫: ঠিকানা*\n\nআপনার ঠিকানা লিখুন (শহর/এলাকা/গ্রাম):",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADDRESS

async def register_address(update: Update, context):
    context.user_data['address'] = update.message.text
    await update.message.reply_text(
        "🩸 *ধাপ ৪/৫: ব্লাড গ্রুপ*\n\nআপনার ব্লাড গ্রুপ লিখুন:\nA+, A-, B+, B-, AB+, AB-, O+, O-",
        parse_mode=ParseMode.MARKDOWN
    )
    return BLOOD_GROUP

async def register_blood(update: Update, context):
    blood = update.message.text.upper()
    valid_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    if blood not in valid_groups:
        await update.message.reply_text(
            "❌ ভুল ব্লাড গ্রুপ।\n\nসঠিক ব্লাড গ্রুপ লিখুন:\nA+, A-, B+, B-, AB+, AB-, O+, O-"
        )
        return BLOOD_GROUP
    context.user_data['blood_group'] = blood
    await update.message.reply_text(
        "📅 *ধাপ ৫/৫: শেষ রক্তদানের তারিখ*\n\n"
        "শেষ কবে রক্ত দিয়েছেন? (তারিখ দিন: YYYY-MM-DD)\n\nউদাহরণ: 2024-01-15\n\n"
        "যদি কখনো রক্ত না দিয়ে থাকেন, তাহলে 'না' লিখুন।",
        parse_mode=ParseMode.MARKDOWN
    )
    return LAST_DONATION

async def register_last_donation(update: Update, context):
    last_donation = update.message.text.strip()
    if last_donation.lower() in ('না', 'na'):
        last_donation = None
    else:
        try:
            datetime.strptime(last_donation, '%Y-%m-%d')
        except ValueError:
            await update.message.reply_text(
                "❌ ভুল তারিখ ফরম্যাট।\n\nসঠিক ফরম্যাট: YYYY-MM-DD\nউদাহরণ: 2024-01-15\n\n"
                "অথবা 'না' লিখুন যদি কখনো রক্ত না দিয়ে থাকেন।"
            )
            return LAST_DONATION

    user_id = update.effective_user.id
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    address = context.user_data.get('address')
    blood = context.user_data.get('blood_group')

    if not all([name, phone, address, blood]):
        await update.message.reply_text("❌ নিবন্ধন তথ্য অনুপস্থিত। দয়া করে /register দিয়ে আবার শুরু করুন।")
        context.user_data.clear()
        return ConversationHandler.END

    existing = get_donor(user_id)
    if existing:
        await update.message.reply_text(
            "❌ আপনি ইতিমধ্যে রক্তদাতা হিসেবে নিবন্ধিত।\nআপনার তথ্য দেখতে /myinfo লিখুন।"
        )
        context.user_data.clear()
        return ConversationHandler.END

    add_donor(user_id, name, blood, phone, address, last_donation)
    last_donation_text = last_donation if last_donation else "কখনো না"
    reply_markup = admin_keyboard() if is_admin(user_id) else main_keyboard()

    await update.message.reply_text(
        f"✅ *নিবন্ধন সফল!*\n\n"
        f"নাম: {name}\nফোন: {phone}\nঠিকানা: {address}\nব্লাড গ্রুপ: {blood}\n"
        f"📅 শেষ রক্তদানের তারিখ: {last_donation_text}\n\n"
        f"আপনার নিবন্ধন অ্যাডমিন অনুমোদনের অপেক্ষায় রয়েছে।\nজীবন বাঁচাতে সাহায্য করার জন্য ধন্যবাদ! 🩸",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

    await context.bot.send_message(
        ADMIN_ID,
        f"📝 *নতুন রক্তদাতা নিবন্ধন*\n\n"
        f"নাম: {name}\nব্লাড: {blood}\nফোন: {phone}\nঠিকানা: {address}\n"
        f"শেষ দান: {last_donation_text}\nইউজার আইডি: {user_id}",
        parse_mode=ParseMode.MARKDOWN
    )
    keyboard = [[InlineKeyboardButton("📋 পেন্ডিং ডোনার দেখুন", callback_data='pending')]]
    await context.bot.send_message(
        ADMIN_ID,
        "নিচের বাটন ব্যবহার করে পেন্ডিং ডোনার অনুমোদন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()
    return ConversationHandler.END

async def register_cancel(update: Update, context):
    await update.message.reply_text(
        "❌ নিবন্ধন বাতিল করা হয়েছে।",
        reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# ============== MENU BUTTON HANDLER ==============
async def menu_button_handler(update: Update, context):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🩸 ডোনার খুঁজুন":
        await search_command(update, context)
    elif text == "🚨 জরুরি রিকোয়েস্ট":
        await emergency_command(update, context)
    elif text == "ℹ️ আমার তথ্য":
        await myinfo_command(update, context)
    elif text == "❓ সাহায্য":
        await help_command(update, context)
    elif text == "🔙 মেনুতে ফিরুন" and is_admin(user_id):
        await start(update, context)
    elif text == "📢 ব্রডকাস্ট" and is_admin(user_id):
        await broadcast_command(update, context)
    elif text == "👥 ইউজার লিস্ট" and is_admin(user_id):
        await users_command(update, context)
    elif text == "🩸 ইমার্জেন্সি লিস্ট" and is_admin(user_id):
        await emergency_list_command(update, context)
    elif text == "✅ ডোনার ভেরিফাই" and is_admin(user_id):
        await verify_donor_command(update, context)
    elif text == "❌ ডোনার ডিলিট" and is_admin(user_id):
        await remove_donor_command(update, context)
    else:
        await handle_text(update, context)

# ============== TEXT HANDLER ==============
async def handle_text(update: Update, context):
    text = update.message.text
    action = context.user_data.get('action')
    if action not in ['search', 'emergency']:
        return

    blood = text.upper()
    valid_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    if blood not in valid_groups:
        await update.message.reply_text(
            "❌ ভুল ব্লাড গ্রুপ।\n\nসঠিক ব্লাড গ্রুপ: A+, A-, B+, B-, AB+, AB-, O+, O-",
            reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
        )
        context.user_data['action'] = None
        return

    if action == 'search':
        donors = search_donors(blood)
        if not donors:
            await update.message.reply_text(
                f"❌ এই রক্তের কোনো দাতা পাওয়া যায়নি\n\nব্লাড গ্রুপ: {blood}\n\n"
                f"পরামর্শ:\n• অন্য ব্লাড গ্রুপ ট্রাই করুন\n• পরে আবার চেষ্টা করুন\n• জরুরি রিকোয়েস্ট ব্যবহার করুন",
                reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
            )
        else:
            result = f"🩸 {blood} ব্লাড গ্রুপের রক্তদাতা:\n\n"
            for name, phone, address, last_donation in donors:
                eligible = is_eligible_to_donate(last_donation)
                status_text = "✅ রক্ত দেওয়ার জন্য উপযুক্ত" if eligible else "❌ সম্প্রতি রক্ত দিয়েছেন (৯০ দিনের মধ্যে)"
                last_donation_text = last_donation if last_donation else "কখনো না"
                result += f"👤 *নাম:* {name}\n📞 *ফোন:* {phone}\n📍 *ঠিকানা:* {address}\n"
                result += f"📅 শেষ দান: {last_donation_text}\n⭐ {status_text}\n" + "─" * 20 + "\n"
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        context.user_data['action'] = None

    elif action == 'emergency':
        donors = search_donors(blood)
        if not donors:
            await update.message.reply_text(
                f"🚨 {blood} ব্লাড গ্রুপের কোনো সক্রিয় রক্তদাতা পাওয়া যায়নি।\n\n"
                f"অ্যাডমিনকে জানানো হয়েছে। আমরা শীঘ্রই যোগাযোগ করব।",
                reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard()
            )
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 *জরুরি রিকোয়েস্ট ব্যর্থ*\n\nব্লাড গ্রুপ: {blood}\n"
                f"আবেদনকারী: {update.effective_user.full_name}\nইউজার আইডি: {update.effective_user.id}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            notified = 0
            for name, phone, address, last_donation in donors:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('SELECT user_id FROM donors WHERE name = %s AND phone = %s', (name, phone))
                result = c.fetchone()
                c.close()
                conn.close()
                if result:
                    try:
                        await context.bot.send_message(
                            result[0],
                            f"🚨 *জরুরি রক্তের প্রয়োজন!*\n\nব্লাড গ্রুপ: {blood}\n"
                            f"আবেদনকারী: {update.effective_user.full_name}\n\n"
                            f"যদি আপনি সাহায্য করতে পারেন তাহলে এখনই যোগাযোগ করুন!",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notified += 1
                    except Exception:
                        pass
            await update.message.reply_text(
                f"🚨 *জরুরি রিকোয়েস্ট পাঠানো হয়েছে!*\n\nব্লাড গ্রুপ: {blood}\n"
                f"নোটিফাই করা হয়েছে: {notified} জন দাতাকে\n\nদাতারা শীঘ্রই আপনার সাথে যোগাযোগ করবেন।",
                parse_mode=ParseMode.MARKDOWN
            )
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 *জরুরি রিকোয়েস্ট পাঠানো হয়েছে*\n\nব্লাড গ্রুপ: {blood}\n"
                f"আবেদনকারী: {update.effective_user.full_name}\nনোটিফাই: {notified} জন দাতা",
                parse_mode=ParseMode.MARKDOWN
            )
        context.user_data['action'] = None

# ============== CALLBACK BUTTON HANDLER ==============
async def callback_button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'pending':
        if update.effective_user.id == ADMIN_ID:
            pending = get_pending_donors()
            if not pending:
                await query.edit_message_text("✅ কোনো পেন্ডিং ডোনার নেই।")
                return
            for donor in pending:
                donor_id, user_id, name, blood, phone, address, last_donation = donor
                keyboard = [[InlineKeyboardButton("✅ অনুমোদন", callback_data=f'approve_{donor_id}')]]
                last_donation_text = last_donation if last_donation else "কখনো না"
                await query.message.reply_text(
                    f"*পেন্ডিং ডোনার*\n\nনাম: {name}\nব্লাড: {blood}\nফোন: {phone}\n"
                    f"ঠিকানা: {address}\nশেষ দান: {last_donation_text}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            await query.delete_message()
        else:
            await query.edit_message_text("⛔ অ্যাক্সেস অস্বীকৃত।")

    elif query.data.startswith('approve_'):
        if update.effective_user.id == ADMIN_ID:
            donor_id = int(query.data.split('_')[1])
            approve_donor(donor_id)
            await query.edit_message_text("✅ ডোনার সফলভাবে অনুমোদিত হয়েছে!")
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT user_id, name FROM donors WHERE id = %s', (donor_id,))
            result = c.fetchone()
            c.close()
            conn.close()
            if result:
                user_id, name = result
                try:
                    await context.bot.send_message(
                        user_id,
                        f"🎉 *অভিনন্দন {name}!*\n\nআপনার রক্তদাতা নিবন্ধন অনুমোদিত হয়েছে।\n"
                        f"জীবন বাঁচাতে সাহায্য করার জন্য ধন্যবাদ! 🩸",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
        else:
            await query.edit_message_text("⛔ অ্যাক্সেস অস্বীকৃত।")

    elif query.data == 'stats':
        if update.effective_user.id == ADMIN_ID:
            donors = get_all_donors()
            total = len(donors)
            approved = len([d for d in donors if d[7] == 'approved'])
            pending = total - approved
            blood_stats = {}
            for d in donors:
                if d[7] == 'approved':
                    bg = d[3]
                    blood_stats[bg] = blood_stats.get(bg, 0) + 1
            stats_text = (
                f"*পরিসংখ্যান*\n\nমোট ডোনার: {total}\nঅনুমোদিত: {approved}\nপেন্ডিং: {pending}\n\n"
                f"*ব্লাড গ্রুপ ভিত্তিক বিতরণ:*\n"
            )
            for bg, count in sorted(blood_stats.items()):
                stats_text += f"{bg}: {count} জন\n"
            await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("⛔ অ্যাক্সেস অস্বীকৃত।")

    elif query.data == 'back':
        await query.edit_message_text(
            "🩸 *ব্লাড ডোনেশন বট*\n\nমূল মেনু:",
            reply_markup=admin_keyboard() if is_admin(update.effective_user.id) else main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )

# ============== MAIN FUNCTION ==============
def main():
    # Startup environment check
    print("=" * 50)
    print("Blood Donation Bot starting...")
    if not DATABASE_URL:
        print("FATAL: DATABASE_URL is not set.")
        print("  Go to Railway -> your project -> Add PostgreSQL plugin")
        print("  Then check the Variables tab in your bot service.")
        raise SystemExit(1)
    if not BOT_TOKEN:
        print("FATAL: BOT_TOKEN is not set.")
        raise SystemExit(1)
    print(f"BOT_TOKEN found: {BOT_TOKEN[:15]}...")
    print("DATABASE_URL found")
    print(f"Admin ID: {ADMIN_ID}")
    print("=" * 50)

    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Registration ConversationHandler ---
    reg_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("register", register_start),
            MessageHandler(filters.Regex("^📝 রেজিস্ট্রেশন$"), register_start),
        ],
        states={
            NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            PHONE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone)],
            ADDRESS:       [MessageHandler(filters.TEXT & ~filters.COMMAND, register_address)],
            BLOOD_GROUP:   [MessageHandler(filters.TEXT & ~filters.COMMAND, register_blood)],
            LAST_DONATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_last_donation)],
        },
        fallbacks=[
            CommandHandler("cancel", register_cancel),
            MessageHandler(filters.Regex("^❓ সাহায্য$"), register_cancel),
        ],
        allow_reentry=True,
    )

    # --- Update Donation Date ConversationHandler ---
    update_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("update_donation_date", update_donation_start),
            MessageHandler(filters.Regex("^📅 তারিখ আপডেট$"), update_donation_start),
        ],
        states={
            UPDATE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_donation_receive)],
        },
        fallbacks=[
            CommandHandler("cancel", update_donation_cancel),
        ],
        allow_reentry=True,
    )

    # Register ConversationHandlers FIRST so they take priority
    application.add_handler(reg_conv_handler)
    application.add_handler(update_conv_handler)

    # Standard command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("emergency", emergency_command))
    application.add_handler(CommandHandler("myinfo", myinfo_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("emergency_list", emergency_list_command))
    application.add_handler(CommandHandler("verify_donor", verify_donor_command))
    application.add_handler(CommandHandler("remove_donor", remove_donor_command))

    # Menu button handler — excludes '📝 রেজিস্ট্রেশন' and '📅 তারিখ আপডেট'
    # because those are entry_points of their respective ConversationHandlers
    application.add_handler(MessageHandler(
        filters.Regex(
            "^(🩸 ডোনার খুঁজুন|🚨 জরুরি রিকোয়েস্ট|ℹ️ আমার তথ্য|❓ সাহায্য"
            "|🔙 মেনুতে ফিরুন|📢 ব্রডকাস্ট|👥 ইউজার লিস্ট"
            "|🩸 ইমার্জেন্সি লিস্ট|✅ ডোনার ভেরিফাই|❌ ডোনার ডিলিট)$"
        ),
        menu_button_handler
    ))

    application.add_handler(CallbackQueryHandler(callback_button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("=" * 50)
    print("🩸 Blood Donation Bot is running...")
    print(f"Bot Token: {BOT_TOKEN[:15]}...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Database: PostgreSQL via DATABASE_URL")
    print("=" * 50)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
