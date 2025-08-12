import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram import ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request
from collections import defaultdict
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import os
import uuid

# --- افزوده‌ها برای بخش پرسش ---
import re
from datetime import date
from openai import OpenAI
# -------------------------------

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

# متن دکمه‌ها
BACK_BTN = "⬅️ بازگشت"
QUESTION_BTN = "🧠 سؤال دارم"   # ← افزوده

# تابع ساخت کیبورد اصلی (سؤال + بازگشت)
def main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton(QUESTION_BTN), KeyboardButton(BACK_BTN)]], resize_keyboard=True)

fields = [
    "نوع شرکت", "نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

persian_number_fields = ["شماره ثبت", "شناسه ملی", "سرمایه", "کد پستی"]

def is_persian_number(text):
    return all('۰' <= ch <= '۹' or ch.isspace() for ch in text)

def fa_to_en_number(text):
    table = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    return text.translate(table)

def generate_word_file(text: str, filepath: str = None):
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'B Nazanin'
    font.size = Pt(14)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'B Nazanin')

    lines = text.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        p = doc.add_paragraph()
        run = p.add_run(line.strip())
        if i == 0:
            run.bold = True
        p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    if not filepath:
        filename = f"soratjalase_{uuid.uuid4().hex}.docx"
        filepath = os.path.join("/tmp", filename)

    doc.save(filepath)
    return filepath

def send_topic_menu(chat_id, context):
    keyboard = [
        [InlineKeyboardButton("🏢 تغییر آدرس", callback_data='تغییر آدرس')],
        [InlineKeyboardButton("🔄 نقل و انتقال سهام", callback_data='نقل و انتقال سهام')],
        [InlineKeyboardButton("🧾 تغییر موضوع فعالیت", callback_data='تغییر موضوع فعالیت')],
        [InlineKeyboardButton("⏳ تمدید سمت اعضا", callback_data='تمدید سمت اعضا')],
        [InlineKeyboardButton("📈 افزایش سرمایه", callback_data='افزایش سرمایه')],
        [InlineKeyboardButton("📉 کاهش سرمایه", callback_data='کاهش سرمایه')],
        [InlineKeyboardButton("🏷️ تغییر نام شرکت", callback_data='تغییر نام شرکت')],
        [InlineKeyboardButton("❌ انحلال شرکت", callback_data='انحلال شرکت')],
        [InlineKeyboardButton("💰 پرداخت سرمایه تعهدی شرکت", callback_data='پرداخت سرمایه تعهدی شرکت')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id=chat_id,
        text="💬 برای چه موضوعی صورتجلسه نیاز دارید؟\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

def send_company_type_menu(chat_id, context):
    keyboard = [
        [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
        [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id=chat_id,
        text="نوع شرکت را انتخاب کنید:",
        reply_markup=reply_markup
    )

# =========================
#  اتصال امن به OpenAI
# =========================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("متغیر محیطی OPENAI_API_KEY تنظیم نشده است.")
client = OpenAI(api_key=OPENAI_API_KEY)

# کلمات کلیدی مجاز (دامنه ثبت/تغییرات شرکت و قانون تجارت ایران)
ALLOWED_KEYWORDS = [
    "ثبت شرکت","تغییر آدرس","تغییر موضوع","اساسنامه","مجمع","صورتجلسه","اداره ثبت",
    "سهامی خاص","مسئولیت محدود","قانون تجارت","سهامدار","هیئت مدیره","سرمایه","نقل و انتقال سهام",
    "آگهی تغییرات","روزنامه رسمی","شرکا","هیات رئیسه","هیئت رئیسه","مجمع فوق العاده","مجمع عمومی"
]

def is_in_domain(txt: str) -> bool:
    t = txt.strip()
    if not t:
        return False
    return any(k in t for k in ALLOWED_KEYWORDS)

def trim_to_words(s: str, n: int = 50) -> str:
    words = re.findall(r"\S+", s)
    return " ".join(words[:n])

def can_ask_today(data: dict) -> bool:
    """حداکثر 3 سؤال رایگان در روز برای هر کاربر"""
    today = str(date.today())
    ask = data.setdefault("ask_quota", {"date": today, "count": 0})
    if ask.get("date") != today:
        ask["date"] = today
        ask["count"] = 0
    return ask["count"] < 3

def inc_ask_count(data: dict):
    today = str(date.today())
    ask = data.setdefault("ask_quota", {"date": today, "count": 0})
    if ask.get("date") != today:
        ask["date"] = today
        ask["count"] = 0
    ask["count"] += 1

def ask_chatgpt(question: str) -> str:
    system_msg = (
        "تو یک دستیار ثبت شرکت هستی. فقط درباره ثبت و تغییرات شرکت و قانون تجارت ایران "
        "به‌طور خلاصه پاسخ بده. حداکثر 50 کلمه. از جزئیات غیرضروری خودداری کن."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": question}
        ],
        max_tokens=120,
        temperature=0.2
    )
    text = resp.choices[0].message.content.strip()
    return trim_to_words(text, 50)

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": 0}
    update.message.reply_text(
        "به خدمات ثبتی کوشا خوش آمدید 🙏🏼\n"
        "در کمتر از چند دقیقه، صورتجلسه رسمی و دقیق شرکت خود را آماده دریافت خواهید کرد.\n"
        "همه‌چیز طبق آخرین قوانین ثبت شرکت‌ها تنظیم می‌شود.",
        reply_markup=main_keyboard()
    )
    send_topic_menu(chat_id, context)
    # (پیام تکراری پایین حذف شد تا خطا ندهد؛ اگر لازم بود نگه دار)

def handle_back(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    data = user_data.get(chat_id, {})
    step = data.get("step", 0)
    if step <= 1:
        context.bot.send_message(chat_id=chat_id, text="به ابتدای فرم برگشتید.")
        return
    data["step"] = step - 1
    prev_field = fields[data["step"]]
    context.bot.send_message(chat_id=chat_id, text=get_label(prev_field))

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    user_data.setdefault(chat_id, {"step": 0})

    # دکمه بازگشت
    if text == BACK_BTN:
        handle_back(update, context)
        return

    if chat_id not in user_data:
        user_data[chat_id] = {"step": 0}

    data = user_data[chat_id]
    step = data.get("step", 0)

    # ===============================
    #  حالت «🧠 سؤال دارم»
    # ===============================
    if text == QUESTION_BTN:
        data["mode"] = "ask"
        context.bot.send_message(chat_id=chat_id, text="سؤال‌تان را بنویسید. (فقط درباره ثبت/تغییرات شرکت و قانون تجارت ایران)")
        return

    if data.get("mode") == "ask":
        # محدودیت روزانه
        if not can_ask_today(data):
            context.bot.send_message(chat_id=chat_id, text="سقف ۳ سؤال رایگان امروز شما تمام شده است. فردا دوباره تلاش کنید.")
            data.pop("mode", None)
            return
        # فیلتر دامنه
        if not is_in_domain(text):
            context.bot.send_message(chat_id=chat_id, text="این سرویس فقط به پرسش‌های مرتبط با ثبت و تغییرات شرکت و قانون تجارت ایران پاسخ می‌دهد.")
            data.pop("mode", None)
            return
        # پرسش از ChatGPT
        try:
            answer = ask_chatgpt(text)
        except Exception:
            context.bot.send_message(chat_id=chat_id, text="متأسفانه در حال حاضر امکان پاسخ‌گویی خودکار وجود ندارد. کمی بعد دوباره تلاش کنید.")
            data.pop("mode", None)
            return

        # افزودن پیام تماس
        answer += "\n\nدر صورت تمایل به مشاوره دقیق تر با شماره 09128687292 تماس حاصل فرمایید"
        context.bot.send_message(chat_id=chat_id, text=answer)

        # ثبت مصرف سهمیه و خروج از مود
        inc_ask_count(data)
        data.pop("mode", None)

        # یادآوری ادامه فرم
        if 1 <= step < len(fields):
            context.bot.send_message(chat_id=chat_id, text=f"✅ لطفاً {get_label(fields[step]).replace(':','')} ")
        else:
            context.bot.send_message(chat_id=chat_id, text="✅ اگر قصد تکمیل فرم دارید، از منوی بالا موضوع را انتخاب کنید.")
        return
    # ===============================

    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    if "موضوع صورتجلسه" not in data:
        context.bot.send_message(chat_id=chat_id, text="لطفاً ابتدا موضوع صورتجلسه را انتخاب کنید. برای شروع مجدد /start را ارسال کنید .")
        return

    # --- بقیه منطق اصلی ربات (بدون تغییر) ---
    common_fields = ["نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت", "آدرس جدید", "کد پستی", "وکیل"]

    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:")
            return

        if 2 <= step <= 9:
            field = common_fields[step - 1]
            if field == "تاریخ":
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).")
                    return
            if field in persian_number_fields:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.")
                    return

            data[field] = text
            data["step"] += 1

            if step == 9:
                context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):")
                return
            else:
                next_field = common_fields[step]
                context.bot.send_message(chat_id=chat_id, text=get_label(next_field))
                return

        if step == 10:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️لطفاً تعداد شرکا را فقط با عدد وارد کنید (بین ۲ تا ۷).")
                return
            count = int(text)
            if count < 2 or count > 7:
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد شرکا باید بین ۲ تا ۷ باشد. لطفاً مجدداً وارد کنید.")
                return
            data["تعداد شرکا"] = count
            data["step"] += 1
            data["current_partner"] = 1
            context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره ۱ را وارد کنید:")
            return

        if step > 10:
            current_partner = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)

            if f"شریک {current_partner}" not in data:
                data[f"شریک {current_partner}"] = text
                context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {current_partner} را به ریال وارد کنید (عدد فارسی):")
                return
            elif f"سهم الشرکه شریک {current_partner}" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️لطفاً میزان سهم الشرکه را فقط با اعداد فارسی وارد کنید.")
                    return
                data[f"سهم الشرکه شریک {current_partner}"] = text
                if current_partner < count:
                    data["current_partner"] = current_partner + 1
                    context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {current_partner + 1} را وارد کنید:")
                    return
                else:
                    send_summary(chat_id, context)
                    data["step"] = 11
                    return

        if step >= 11:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.")
            return

    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:")
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.")
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            context.bot.send_message(chat_id=chat_id, text="شناسه ملی شرکت را وارد کنید:")
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.")
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            context.bot.send_message(chat_id=chat_id, text="سرمایه شرکت به ریال را وارد کنید (اعداد فارسی):")
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.")
                return
            data["سرمایه"] = text
            data["step"] = 5
            context.bot.send_message(chat_id=chat_id, text="تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):")
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.")
                return
            data["تاریخ"] = text
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text="ساعت جلسه را وارد کنید:")
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.")
                return
            data["ساعت"] = text
            data["step"] = 7
            context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید:")
            return

        if step == 7:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.")
                return
            count = int(text)
            data["تعداد شرکا"] = count
            data["current_partner"] = 1
            data["step"] = 8
            context.bot.send_message(chat_id=chat_id, text="نام شریک شماره ۱ را وارد کنید:")
            return

        if step == 8:
            i = data["current_partner"]
            data[f"شریک {i}"] = text
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=f"سهم الشرکه شریک شماره {i} را وارد کنید (عدد فارسی):")
            return

        if step == 9:
            i = data["current_partner"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سهم الشرکه را فقط با اعداد فارسی وارد کنید.")
                return
            data[f"سهم الشرکه شریک {i}"] = text
            if i < data["تعداد شرکا"]:
                data["current_partner"] += 1
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i+1} را وارد کنید:")
            else:
                data["step"] = 10
                keyboard = [
                    [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                    [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟", reply_markup=reply_markup)
            return

        if data.get("step") == 10 and update.callback_query:
            answer = update.callback_query.data
            update.callback_query.answer()
            if answer in ["الحاق", "جایگزین"]:
                data["نوع تغییر موضوع"] = answer
                data["step"] = 11
                context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
            return

        if step == 11:
            data["موضوع جدید"] = text
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text="نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:")
            return

        if step == 12:
            data["وکیل"] = text
            send_summary(chat_id, context)
            return

    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:")
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.")
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            context.bot.send_message(chat_id=chat_id, text="شناسه ملی شرکت را وارد کنید:")
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.")
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            context.bot.send_message(chat_id=chat_id, text="سرمایه شرکت به ریال را وارد کنید (عدد فارسی):")
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.")
                return
            data["سرمایه"] = text
            data["step"] = 5
            context.bot.send_message(chat_id=chat_id, text="تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):")
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.")
                return
            data["تاریخ"] = text
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text="ساعت جلسه را وارد کنید :")
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.")
                return
            saat = int(fa_to_en_number(text))
            if saat < 8 or saat > 17:
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت جلسه باید بین ۸ تا ۱۷ باشد.")
                return
            data["ساعت"] = text
            data["step"] = 7
            context.bot.send_message(chat_id=chat_id, text="مدیر عامل (رئیس جلسه) را وارد کنید:")
            return

        if step == 7:
            data["مدیر عامل"] = text
            data["step"] = 8
            context.bot.send_message(chat_id=chat_id, text="ناظر اول جلسه را وارد کنید (از بین اعضای هیئت مدیره):")
            return

        if step == 8:
            if text == data["مدیر عامل"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر اول نمی‌تواند با مدیر عامل یکی باشد. لطفاً شخص دیگری را انتخاب کنید.")
                return
            data["نایب رییس"] = text
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text="ناظر دوم جلسه را وارد کنید (از بین اعضای هیئت مدیره):")
            return

        if step == 9:
            if text == data["مدیر عامل"] or text == data["نایب رییس"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر دوم نمی‌تواند با مدیر عامل یا ناظر اول یکی باشد. لطفاً شخص دیگری را انتخاب کنید.")
                return
            data["رییس"] = text
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text="منشی جلسه را وارد کنید:")
            return

        if step == 10:
            data["منشی"] = text
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text="تعداد فروشندگان را وارد کنید:")
            return

        if step == 11:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد فروشندگان را با عدد وارد کنید.")
                return
            count = int(text)
            if count < 1:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل یک فروشنده باید وجود داشته باشد.")
                return
            data["تعداد فروشندگان"] = count
            data["فروشنده_index"] = 1
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text="نام فروشنده شماره ۱ را وارد کنید:")
            return

        if step >= 12 and data.get("فروشنده_index", 0) <= data.get("تعداد فروشندگان", 0):
            i = data["فروشنده_index"]
            prefix = f"فروشنده {i}"

            if f"{prefix} نام" not in data:
                data[f"{prefix} نام"] = text
                context.bot.send_message(chat_id=chat_id, text=f"کد ملی {prefix} را وارد کنید:")
                return
            if f"{prefix} کد ملی" not in data:
                data[f"{prefix} کد ملی"] = text
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام منتقل‌شده توسط {prefix} را وارد کنید:")
                return
            elif f"{prefix} تعداد" not in data:
                data[f"{prefix} تعداد"] = text
                context.bot.send_message(chat_id=chat_id, text="تعداد خریداران برای این فروشنده را وارد کنید:")
                data["step"] = 13
                return

        if step == 13:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد خریداران را با عدد وارد کنید.")
                return
            count = int(text)
            if count < 1:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل یک خریدار لازم است.")
                return
            i = data["فروشنده_index"]
            data[f"تعداد خریداران {i}"] = count
            data[f"خریدار_index_{i}"] = 1
            data["step"] = 14
            context.bot.send_message(chat_id=chat_id, text=f"نام خریدار شماره ۱ از فروشنده {i} را وارد کنید:")
            return

        if step == 14:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]

            if f"خریدار {i}-{k} نام" not in data:
                data[f"خریدار {i}-{k} نام"] = text
                context.bot.send_message(chat_id=chat_id, text=f"کد ملی خریدار {k} از فروشنده {i} را وارد کنید:")
                return
            elif f"خریدار {i}-{k} کد ملی" not in data:
                data[f"خریدار {i}-{k} کد ملی"] = text
                context.bot.send_message(chat_id=chat_id, text=f"آدرس خریدار {k} از فروشنده {i} را وارد کنید:")
                return
            elif f"خریدار {i}-{k} آدرس" not in data:
                data[f"خریدار {i}-{k} آدرس"] = text
                total = data[f"تعداد خریداران {i}"]
                if k < total:
                    data[f"خریدار_index_{i}"] += 1
                    context.bot.send_message(chat_id=chat_id, text=f"نام خریدار شماره {k+1} از فروشنده {i} را وارد کنید:")
                    return
                else:
                    if i < data["تعداد فروشندگان"]:
                        data["فروشنده_index"] += 1
                        data["step"] = 12
                        context.bot.send_message(chat_id=chat_id, text=f"نام فروشنده شماره {i+1} را وارد کنید:")
                    else:
                        data["step"] = 15
                        context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران قبل از نقل و انتقال را وارد کنید:")
                    return

    if step == 15:
        if not text.isdigit():
            context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.")
            return
        count = int(text)
        data["تعداد سهامداران قبل"] = count
        data["سهامدار_قبل_index"] = 1
        data["step"] = 16
        context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار قبل شماره ۱ را وارد کنید:")
        return

    if step == 16:
        i = data["سهامدار_قبل_index"]
        prefix = f"سهامدار قبل {i}"
        if f"{prefix} نام" not in data:
            data[f"{prefix} نام"] = text
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام {prefix} را وارد کنید:")
            return
        elif f"{prefix} تعداد" not in data:
            data[f"{prefix} تعداد"] = text
            if i < data["تعداد سهامداران قبل"]:
                data["سهامدار_قبل_index"] += 1
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار قبل شماره {i+1} را وارد کنید:")
            else:
                data["step"] = 17
                context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران بعد از نقل و انتقال را وارد کنید:")
            return

    if step == 17:
        if not text.isdigit():
            context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.")
            return
        count = int(text)
        data["تعداد سهامداران بعد"] = count
        data["سهامدار_بعد_index"] = 1
        data["step"] = 18
        context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار بعد شماره ۱ را وارد کنید:")
        return

    if step == 18:
        i = data["سهامدار_بعد_index"]
        prefix = f"سهامدار بعد {i}"
        if f"{prefix} نام" not in data:
            data[f"{prefix} نام"] = text
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام {prefix} را وارد کنید:")
            return
        elif f"{prefix} تعداد" not in data:
            data[f"{prefix} تعداد"] = text
            if i < data["تعداد سهامداران بعد"]:
                data["سهامدار_بعد_index"] += 1
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار بعد شماره {i+1} را وارد کنید:")
            else:
                data["step"] = 19
                context.bot.send_message(chat_id=chat_id, text="نام وکیل (شخص ثبت‌کننده صورتجلسه) را وارد کنید:")
            return

    if step == 19:
        data["وکیل"] = text
        send_summary(chat_id, context)
        data["step"] = 20
        return

    if step >= 20:
        context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.")
        return

    if step == 1:
        data["نام شرکت"] = text
        data["step"] = 2
        next_field = fields[2]
        label = get_label(next_field)
        context.bot.send_message(chat_id=chat_id, text=label)
        return

    if step == 0:
        context.bot.send_message(chat_id=chat_id, text="لطفاً نوع شرکت را از گزینه‌های ارائه شده انتخاب کنید.")
        return

    if 2 <= step < len(fields):
        field = fields[step]
        if field == "تاریخ":
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).")
                return
        if field in persian_number_fields:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.")
                return

        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields):
            next_field = fields[data["step"]]
            label = get_label(next_field)
            context.bot.send_message(chat_id=chat_id, text=label)
        else:
            send_summary(chat_id, context)
        return

    context.bot.send_message(chat_id=chat_id, text="لطفاً منتظر بمانید...")

def get_label(field):
    labels = {
        "نوع شرکت": "نوع شرکت را انتخاب کنید:",
        "نام شرکت": "نام شرکت را وارد کنید:",
        "شماره ثبت": "شماره ثبت شرکت را وارد کنید:",
        "شناسه ملی": "شناسه ملی شرکت را وارد کنید:",
        "سرمایه": "سرمایه اولیه شرکت را به ریال وارد کنید:",
        "تاریخ": "تاریخ صورتجلسه را وارد کنید (بهتر است تاریخ روز باشد چون برای ثبت صورتجلسات در اداره فقط یک ماه فرصت دارید):",
        "ساعت": "ساعت برگزاری جلسه را وارد کنید:",
        "مدیر عامل": "مدیر عامل را وارد کنید (مثلا: آقای ... خانم ...):",
        "نایب رییس": "نایب رئیس جلسه را وارد کنید:",
        "رییس": "رئیس جلسه را وارد کنید:",
        "منشی": "منشی جلسه را وارد کنید:",
        "آدرس جدید": "آدرس جدید شرکت را وارد کنید:",
        "کد پستی": "کد پستی آدرس جدید را وارد کنید:",
        "وکیل": "وکیل را وارد کنید (منظور شخصی هست که از طرف شما برای ثبت صورتجلسات و امضا دفاتر ثبتی انتخاب میشود):"
    }
    return labels.get(field, f"{field} را وارد کنید:")

def handle_back(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    data = user_data.setdefault(chat_id, {"step": 0})
    step = data.get("step", 0)
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    if not موضوع:
        context.bot.send_message(chat_id=chat_id, text="به منوی موضوعات برگشتید.")
        send_topic_menu(chat_id, context)
        return

    if step == 1:
        data.pop("نوع شرکت", None)
        data["step"] = 0
        context.bot.send_message(chat_id=chat_id, text="به انتخاب نوع شرکت برگشتید.")
        send_company_type_menu(chat_id, context)
        return

    if موضوع == "تغییر آدرس" and نوع_شرکت == "مسئولیت محدود":
        common_fields = ["نام شرکت","شماره ثبت","شناسه ملی","سرمایه","تاریخ","ساعت","آدرس جدید","کد پستی","وکیل"]

        if 2 <= step <= 10:
            prev_step = step - 1
            if prev_step == 1:
                data.pop("نام شرکت", None)
                data["step"] = 1
                context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
                return
            key = common_fields[prev_step - 1]
            data.pop(key, None)
            data["step"] = prev_step
            context.bot.send_message(chat_id=chat_id, text=get_label(key))
            return

        if step > 10:
            i = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)
            if f"شریک {i}" not in data:
                if i == 1:
                    data.pop("تعداد شرکا", None)
                    data["step"] = 10
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):")
                    return
                else:
                    prev_i = i - 1
                    data["current_partner"] = prev_i
                    data.pop(f"سهم الشرکه شریک {prev_i}", None)
                    data["step"] = 10 + prev_i
                    context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {prev_i} را به ریال وارد کنید (عدد فارسی):")
                    return

            if f"سهم الشرکه شریک {i}" not in data:
                data.pop(f"شریک {i}", None)
                data["step"] = 10 + i
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

            context.bot.send_message(chat_id=chat_id, text="برای شروع مجدد /start را ارسال کنید.")
            return

    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "مسئولیت محدود":
        if 2 <= step <= 7:
            prev_step = step - 1
            order = ["نام شرکت","شماره ثبت","شناسه ملی","سرمایه","تاریخ","ساعت"]
            key = order[prev_step - 1] if prev_step - 1 < len(order) else None
            if prev_step == 1:
                data.pop("نام شرکت", None)
                data["step"] = 1
                context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
                return
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                context.bot.send_message(chat_id=chat_id, text=get_label(key))
                return

        if step in (8, 9):
            i = data.get("current_partner", 1)
            if step == 8:
                if i == 1:
                    data.pop("تعداد شرکا", None)
                    data["step"] = 7
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید:")
                    return
                else:
                    prev_i = i - 1
                    data["current_partner"] = prev_i
                    data.pop(f"سهم الشرکه شریک {prev_i}", None)
                    data["step"] = 9
                    context.bot.send_message(chat_id=chat_id, text=f"سهم الشرکه شریک شماره {prev_i} را وارد کنید (عدد فارسی):")
                    return
            else:
                data.pop(f"شریک {i}", None)
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

        if step == 10:
            i = data.get("تعداد شرکا", 1)
            data["current_partner"] = i
            data.pop(f"سهم الشرکه شریک {i}", None)
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=f"سهم الشرکه شریک شماره {i} را وارد کنید (عدد فارسی):")
            return

        if step == 11:
            data.pop("نوع تغییر موضوع", None)
            data["step"] = 10
            keyboard = [
                [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
            ]
            context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if step == 12:
            data.pop("موضوع جدید", None)
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
            return

    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        linear_map = {
            1: "نام شرکت", 2: "شماره ثبت", 3: "شناسه ملی", 4: "سرمایه",
            5: "تاریخ", 6: "ساعت", 7: "مدیر عامل", 8: "نایب رییس",
            9: "رییس", 10: "منشی", 11: "تعداد فروشندگان"
        }

        if 2 <= step <= 11:
            prev_step = step - 1
            key = linear_map.get(prev_step)
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                context.bot.send_message(chat_id=chat_id, text=get_label(key))
                return

        if step == 12:
            i = data.get("فروشنده_index", 1)
            prefix = f"فروشنده {i}"
            if f"{prefix} نام" not in data:
                if i == 1:
                    data.pop("تعداد فروشندگان", None)
                    data["step"] = 11
                    context.bot.send_message(chat_id=chat_id, text="تعداد فروشندگان را وارد کنید:")
                    return
                else:
                    prev_i = i - 1
                    total_k = data.get(f"تعداد خریداران {prev_i}", 1)
                    data["فروشنده_index"] = prev_i
                    data[f"خریدار_index_{prev_i}"] = total_k
                    data.pop(f"خریدار {prev_i}-{total_k} آدرس", None)
                    data["step"] = 14
                    context.bot.send_message(chat_id=chat_id, text=f"آدرس خریدار {total_k} از فروشنده {prev_i} را وارد کنید:")
                    return
            if f"{prefix} کد ملی" not in data:
                data.pop(f"{prefix} نام", None)
                data["step"] = 12
                context.bot.send_message(chat_id=chat_id, text=f"نام فروشنده شماره {i} را وارد کنید:")
                return
            if f"{prefix} تعداد" not in data:
                data.pop(f"{prefix} کد ملی", None)
                data["step"] = 12
                context.bot.send_message(chat_id=chat_id, text=f"کد ملی فروشنده شماره {i} را وارد کنید:")
                return

        if step == 13:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} تعداد", None)
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام منتقل‌شده توسط فروشنده {i} را وارد کنید:")
            return

        if step == 14:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            if f"خریدار {i}-{k} نام" not in data:
                data.pop(f"تعداد خریداران {i}", None)
                data["step"] = 13
                context.bot.send_message(chat_id=chat_id, text=f"تعداد خریداران برای فروشنده {i} را وارد کنید:")
                return
            if f"خریدار {i}-{k} کد ملی" not in data:
                data.pop(f"خریدار {i}-{k} نام", None)
                data["step"] = 14
                context.bot.send_message(chat_id=chat_id, text=f"نام خریدار شماره {k} از فروشنده {i} را وارد کنید:")
                return
            if f"خریدار {i}-{k} آدرس" not in data:
                data.pop(f"خریدار {i}-{k} کد ملی", None)
                data["step"] = 14
                context.bot.send_message(chat_id=chat_id, text=f"کد ملی خریدار {k} از فروشنده {i} را وارد کنید:")
                return

    if step == 15:
        i = data.get("فروشنده_index", 1)
        total_k = data.get(f"تعداد خریداران {i}", None)
        if total_k:
            data[f"خریدار_index_{i}"] = total_k
            data.pop(f"خریدار {i}-{total_k} آدرس", None)
            data["step"] = 14
            context.bot.send_message(chat_id=chat_id, text=f"آدرس خریدار {total_k} از فروشنده {i} را وارد کنید:")
            return
        data["step"] = 13
        context.bot.send_message(chat_id=chat_id, text=f"تعداد خریداران برای فروشنده {i} را وارد کنید:")
        return

    if step == 16:
        i = data.get("سهامدار_قبل_index", 1)
        prefix = f"سهامدار قبل {i}"
        if f"{prefix} نام" not in data:
            data.pop("تعداد سهامداران قبل", None)
            data["step"] = 15
            context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران قبل از نقل و انتقال را وارد کنید:")
            return
        if f"{prefix} تعداد" not in data:
            data.pop(f"{prefix} نام", None)
            data["step"] = 16
            context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار قبل شماره {i} را وارد کنید:")
            return

    if step == 17:
        i = data.get("سهامدار_قبل_index", 1)
        if i > 1:
            prev_i = i - 1
            data["سهامدار_قبل_index"] = prev_i
            data.pop(f"سهامدار قبل {prev_i} تعداد", None)
            data["step"] = 16
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار قبل شماره {prev_i} را وارد کنید:")
            return
        else:
            data.pop("سهامدار قبل 1 نام", None)
            data["step"] = 16
            context.bot.send_message(chat_id=chat_id, text="نام سهامدار قبل شماره ۱ را وارد کنید:")
            return

    if step == 18:
        i = data.get("سهامدار_بعد_index", 1)
        prefix = f"سهامدار بعد {i}"
        if f"{prefix} نام" not in data:
            data.pop("تعداد سهامداران بعد", None)
            data["step"] = 17
            context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران بعد از نقل و انتقال را وارد کنید:")
            return
        if f"{prefix} تعداد" not in data:
            data.pop(f"{prefix} نام", None)
            data["step"] = 18
            context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار بعد شماره {i} را وارد کنید:")
            return

    if step == 19:
        i = data.get("سهامدار_بعد_index", 1)
        if i > 1:
            prev_i = i - 1
            data["سهامدار_بعد_index"] = prev_i
            data.pop(f"سهامدار بعد {prev_i} تعداد", None)
            data["step"] = 18
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار بعد شماره {prev_i} را وارد کنید:")
            return
        else:
            data.pop("سهامدار بعد 1 نام", None)
            data["step"] = 18
            context.bot.send_message(chat_id=chat_id, text="نام سهامدار بعد شماره ۱ را وارد کنید:")
            return

    if step == 0:
        data.pop("موضوع صورتجلسه", None)
        data.pop("نوع شرکت", None)
        context.bot.send_message(chat_id=chat_id, text="به انتخاب موضوع برگشتید.")
        send_topic_menu(chat_id, context)
        return

    if step >= 2:
        prev_step = step - 1
        key = fields[prev_step]
        data.pop(key, None)
        data["step"] = prev_step
        context.bot.send_message(chat_id=chat_id, text=get_label(key))
        return

    context.bot.send_message(chat_id=chat_id, text="یک مرحله به عقب برگشتید.")

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()
    user_data.setdefault(chat_id, {})
    data = user_data[chat_id]

    if "موضوع صورتجلسه" not in user_data.get(chat_id, {}):
        user_data[chat_id]["موضوع صورتجلسه"] = query.data
        user_data[chat_id]["step"] = 0
        send_company_type_menu(chat_id, context)
        context.bot.send_message(chat_id=chat_id, text=f"موضوع صورتجلسه انتخاب شد: {query.data}\n\nنوع شرکت را انتخاب کنید:")
        return

    if user_data[chat_id].get("step") == 0:
        user_data[chat_id]["نوع شرکت"] = query.data
        user_data[chat_id]["step"] = 1
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
        return

    if data.get("موضوع صورتجلسه") == "تغییر موضوع فعالیت" and data.get("step") == 10:
        انتخاب = query.data
        query.answer()
        if انتخاب == "الحاق":
            data["نوع تغییر موضوع"] = "الحاق"
        elif انتخاب == "جایگزین":
            data["نوع تغییر موضوع"] = "جایگزین"
        else:
            context.bot.send_message(chat_id=chat_id, text="❗️انتخاب نامعتبر بود.")
            return
        data["step"] = 11
        context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
        return

def send_summary(chat_id, context):
    data = user_data[chat_id]
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    if موضوع == "تغییر آدرس" and نوع_شرکت == "مسئولیت محدود":
        partners_lines = ""
        count = data.get("تعداد شرکا", 0)
        for i in range(1, count + 1):
            name = data.get(f"شریک {i}", "")
            share = data.get(f"سهم الشرکه شریک {i}", "")
            partners_lines += f"{name}                                              {share} ریال\n"
        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']}
شماره ثبت شرکت : {data['شماره ثبت']}
شناسه ملی : {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']} ثبت شده به شماره {data['شماره ثبت']} در تاریخ {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و نسبت به تغییر محل شرکت اتخاذ تصمیم شد. 

اسامی شرکا                                                     میزان سهم الشرکه
{partners_lines}
محل شرکت از آدرس قبلی به آدرس {data['آدرس جدید']} به کدپستی {data['کد پستی']} انتقال یافت.

به {data['وکیل']} احدی از شرکاء وکالت داده می شود تا ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و امضاء ذیل دفتر ثبت اقدام نماید.

امضاء شرکا : 

"""
        signers = ""
        for i in range(1, count + 1):
            signers += f"{data.get(f'شریک {i}', '')}     "
        text += signers
        context.bot.send_message(chat_id=chat_id, text=text)

        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
        os.remove(file_path)
        return

    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت})  
    شماره ثبت شرکت :     {data['شماره ثبت']}
    شناسه ملی :      {data['شناسه ملی']}
    سرمایه ثبت شده : {data['سرمایه']} ریال

    صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.

    الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 
    ـ  {data['مدیر عامل']}                                   به سمت رئیس جلسه 
    ـ  {data['نایب رییس']}                                  به سمت ناظر 1 جلسه 
    ـ  {data['رییس']}                                        به سمت ناظر 2 جلسه 
    ـ  {data['منشی']}                         به سمت منشی جلسه انتخاب شدند

    ب: دستور جلسه اتخاذ تصمیم در خصوص نقل و انتقال سهام، مجمع موافقت و تصویب نمود که:"""

        def fa_to_en_number(text):
            table = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
            return text.translate(table)

        from collections import defaultdict
        foroshandeha_tajmi = defaultdict(list)

        for i in range(1, data["تعداد فروشندگان"] + 1):
            nam = data[f'فروشنده {i} نام']
            kodmeli = data[f'فروشنده {i} کد ملی']
            tedad = data[f'فروشنده {i} تعداد']
            for j in range(1, data.get(f"تعداد خریداران {i}", 0) + 1):
                foroshandeha_tajmi[nam].append({
                    "کد ملی": kodmeli,
                    "تعداد": tedad,
                    "خریدار": data.get(f'خریدار {i}-{j} نام', ''),
                    "کد ملی خریدار": data.get(f'خریدار {i}-{j} کد ملی', ''),
                    "آدرس خریدار": data.get(f'خریدار {i}-{j} آدرس', '')
                })

        for nam_forooshande, vaghzari_ha in foroshandeha_tajmi.items():
            kod_meli_forooshande = vaghzari_ha[0]["کد ملی"]
            matn = f"\n    {nam_forooshande} به شماره ملی {kod_meli_forooshande} "

            jomalat = []
            majmoo_montaghel = 0
            for item in vaghzari_ha:
                tedad = int(fa_to_en_number(item["تعداد"]))
                majmoo_montaghel += tedad
                jomalat.append(
                    f"تعداد {item['تعداد']} سهم به {item['خریدار']} به شماره ملی {item['کد ملی خریدار']} به آدرس {item['آدرس خریدار']}"
                )

            matn += " و همچنین ".join(jomalat)
            matn += " واگذار کرد"

            majmoo_saham_qabl = 0
            for j in range(1, data["تعداد سهامداران قبل"] + 1):
                if data[f"سهامدار قبل {j} نام"] == nam_forooshande:
                    majmoo_saham_qabl = int(fa_to_en_number(data[f"سهامدار قبل {j} تعداد"]))
                    break

            if majmoo_montaghel == majmoo_saham_qabl:
                matn += " و از شرکت خارج شد و دیگر هیچ گونه حق و سمتی ندارد."

            text += matn

        text += f"""

    مجمع به {data['وکیل']} احدی از سهامداران شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید. 

    امضاء اعضاء هیات رئیسه: 
    رئیس جلسه :  {data['مدیر عامل']}                                   ناظر1 جلسه : {data['نایب رییس']}                                
    ناظر2جلسه : {data['رییس']}                                       منشی جلسه: {data['منشی']}


    فروشندگان :"""
        for nam_forooshande in foroshandeha_tajmi:
            text += f" {nam_forooshande}     "

        text += "\nخریداران :"
        for vaghzari_ha in foroshandeha_tajmi.values():
            for item in vaghzari_ha:
                text += f" {item['خریدار']}     "

        text += f"\n\nصورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}\n{data['نام شرکت']} قبل از نقل و انتقال سهام\n"
        text += "ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران\n"
        for i in range(1, data["تعداد سهامداران قبل"] + 1):
            text += f"{i}\t{data[f'سهامدار قبل {i} نام']}\t{data[f'سهامدار قبل {i} تعداد']}\t\n"

        text += f"\nصورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}\n{data['نام شرکت']} بعد از نقل و انتقال سهام\n"
        text += "ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران\n"
        for i in range(1, data["تعداد سهامداران بعد"] + 1):
            text += f"{i}\t{data[f'سهامدار بعد {i} نام']}\t{data[f'سهامدار بعد {i} تعداد']}\t\n"

        context.bot.send_message(chat_id=chat_id, text=text)

        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه نقل و انتقال.docx")
        os.remove(file_path)
        return

    if موضوع == "تغییر آدرس" and نوع_شرکت == "سهامی خاص":
        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']}
شماره ثبت شرکت : {data['شماره ثبت']}
شناسه ملی : {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']} ثبت شده به شماره {data['شماره ثبت']} در تاریخ {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.

الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 
ـ  {data['مدیر عامل']} به سمت رئیس جلسه 
ـ  {data['نایب رییس']} به سمت ناظر 1 جلسه 
ـ  {data['رییس']} به سمت ناظر 2 جلسه 
ـ  {data['منشی']} به سمت منشی جلسه انتخاب شدند

ب: دستور جلسه اتخاذ تصمیم در خصوص تغییر محل شرکت، مجمع موافقت و تصویب نمود که:
محل شرکت از آدرس قبلی به آدرس جدید {data['آدرس جدید']} کد پستی {data['کد پستی']} انتقال یافت.

مجمع به {data['وکیل']} احدی از سهامداران شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.

امضاء اعضاء هیات رئیسه: 
رئیس جلسه : {data['مدیر عامل']}     ناظر1 جلسه : {data['نایب رییس']}     
ناظر2 جلسه : {data['رییس']}         منشی جلسه: {data['منشی']}"""
        context.bot.send_message(chat_id=chat_id, text=text)

        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
        os.remove(file_path)
        return

    if موضوع == "تغییر موضوع فعالیت" و نوع_شرکت == "مسئولیت محدود":
        count = data.get("تعداد شرکا", 0)
        partners_lines = ""
        for i in range(1, count + 1):
            name = data.get(f"شریک {i}", "")
            share = data.get(f"سهم الشرکه شریک {i}", "")
            partners_lines += f"{name}                                              {share} ریال\n"

        action_line = (
            "نسبت به الحاق مواردی به موضوع شرکت اتخاذ تصمیم شد."
            if data["نوع تغییر موضوع"] == "الحاق"
            else "نسبت به تغییر موضوع شرکت اتخاذ تصمیم شد."
        )
        subject_line = (
            "مواردی به شرح ذیل به موضوع شرکت الحاق شد:"
            if data["نوع تغییر موضوع"] == "الحاق"
            else "موضوع شرکت به شرح ذیل تغییر یافت:"
        )

        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت})
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و {action_line}

اسامی شرکا                                                        میزان سهم الشرکه
{partners_lines}
{subject_line}
{data['موضوع جدید']} 
و ماده مربوطه اساسنامه به شرح فوق اصلاح می گردد. 
به {data['وکیل']} از شرکاء شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکت ها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.

امضاء شرکاء: 
"""

        for i in range(1, count + 1):
            text += f"{data.get(f'شریک {i}', '')}     "
        context.bot.send_message(chat_id=chat_id, text=text)

        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه تغییر موضوع فعالیت.docx")
        os.remove(file_path)
        return

    context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات با موفقیت دریافت شد.\nدر حال حاضر صورتجلسه‌ای برای این ترکیب تعریف نشده است.")

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(button_handler))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
