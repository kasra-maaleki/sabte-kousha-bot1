import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from flask import Flask, request
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import os
import uuid

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}
transfer_sessions = {}

fields = [
    "نوع شرکت", "نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

persian_number_fields = ["شماره ثبت", "شناسه ملی", "سرمایه", "کد پستی"]
(
    ASK_TRANSFER_FIELD,          # دریافت اطلاعات شرکت مرحله‌ای
    ASK_SELLER_NAME,
    ASK_SELLER_NID,
    ASK_SELLER_SHARES,
    ASK_SELLER_TOTAL,
    ASK_BUYER_NAME,
    ASK_BUYER_NID,
    ASK_BUYER_ADDRESS,
    ASK_MORE_SELLERS,
    ASK_BEFORE_COUNT,
    ASK_BEFORE_NAME,
    ASK_BEFORE_SHARES,
    ASK_AFTER_COUNT,
    ASK_AFTER_NAME,
    ASK_AFTER_SHARES,
) = range(100, 115)

def is_persian_number(text):
    return all('۰' <= ch <= '۹' or ch.isspace() for ch in text)

def show_back_button(chat_id, context):
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="BACK")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=chat_id, text="اگر نیاز دارید به مرحله قبل بازگردید:", reply_markup=reply_markup)

def start_transfer_process(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    transfer_sessions[chat_id] = {'step': 0}
    context.bot.send_message(chat_id=chat_id, text="🔹 نام شرکت را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_TRANSFER_FIELD

def ask_transfer_field(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    answers = session.setdefault('fields', [])
    fields = [
        "نام شرکت", "نوع شرکت", "شماره ثبت", "شناسه ملی", "سرمایه ثبت شده (ریال)",
        "تاریخ جلسه", "ساعت جلسه", "مدیر عامل", "نایب رییس", "رییس جلسه", "منشی", "وکیل"
    ]
    answers.append(update.message.text.strip())
    if len(answers) < len(fields):
        context.bot.send_message(chat_id=chat_id, text=f"🔹 {fields[len(answers, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )]} را وارد نمایید:")
        return ASK_TRANSFER_FIELD
    else:
        session.update(dict(zip(fields, answers)))
        session['sellers'] = []
        context.bot.send_message(chat_id=chat_id, text="🔸 نام فروشنده شماره ۱ را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return ASK_SELLER_NAME

def ask_seller_name(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller'] = {'seller': update.message.text.strip()}
    context.bot.send_message(chat_id=chat_id, text="🔹 کد ملی فروشنده را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_SELLER_NID

def ask_seller_nid(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['seller_national_id'] = update.message.text.strip()
    context.bot.send_message(chat_id=chat_id, text="🔹 تعداد سهام واگذار شده را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_SELLER_SHARES

def ask_seller_shares(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['shares'] = int(update.message.text.strip())
    context.bot.send_message(chat_id=chat_id, text="🔹 مجموع سهام این فروشنده قبل از انتقال:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_SELLER_TOTAL

def ask_seller_total(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['total_shares'] = int(update.message.text.strip())
    context.bot.send_message(chat_id=chat_id, text="🔹 نام خریدار را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_BUYER_NAME

def ask_buyer_name(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['buyer'] = update.message.text.strip()
    context.bot.send_message(chat_id=chat_id, text="🔹 کد ملی خریدار را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_BUYER_NID

def ask_buyer_nid(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['buyer_national_id'] = update.message.text.strip()
    context.bot.send_message(chat_id=chat_id, text="🔹 آدرس خریدار را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_BUYER_ADDRESS

def ask_buyer_address(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_seller']['buyer_address'] = update.message.text.strip()
    session.setdefault('sellers', []).append(session['current_seller'])
    del session['current_seller']
    context.bot.send_message(chat_id=chat_id, text="آیا فروشنده دیگری وجود دارد؟ (بله / خیر, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )")
    return ASK_MORE_SELLERS

def ask_more_sellers(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if text == "بله":
        context.bot.send_message(chat_id=chat_id, text="🔸 نام فروشنده بعدی را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return ASK_SELLER_NAME
    elif text == "خیر":
        context.bot.send_message(chat_id=chat_id, text="🔸 چند سهامدار قبل از نقل و انتقال وجود دارد؟ (عدد وارد کنید, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )")
        return ASK_BEFORE_COUNT
    else:
        context.bot.send_message(chat_id=chat_id, text="❗ لطفاً فقط یکی از گزینه‌های «بله» یا «خیر» را وارد نمایید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return ASK_MORE_SELLERS

def ask_before_count(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    count = update.message.text.strip()

    if not count.isdigit():
        context.bot.send_message(chat_id=chat_id, text="❗ لطفاً فقط عدد وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return ASK_BEFORE_COUNT

    session['before_count'] = int(count)
    session['before_index'] = 1
    session['before_shareholders'] = []
    context.bot.send_message(chat_id=chat_id, text="🔹 نام سهامدار شماره 1 (قبل از نقل و انتقال, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ) را وارد نمایید:")
    return ASK_BEFORE_NAME

def ask_before_name(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_before'] = {'name': update.message.text.strip()}
    context.bot.send_message(chat_id=chat_id, text="🔹 تعداد سهام این سهامدار را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_BEFORE_SHARES

def ask_before_shares(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]

    session['current_before']['shares'] = update.message.text.strip()
    session['before_shareholders'].append(session['current_before'])
    del session['current_before']
    session['before_index'] += 1

    if session['before_index'] <= session['before_count']:
        context.bot.send_message(chat_id=chat_id, text=f"🔹 نام سهامدار شماره {session['before_index']} (قبل از نقل و انتقال, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ) را وارد نمایید:")
        return ASK_BEFORE_NAME
    else:
        context.bot.send_message(chat_id=chat_id, text="🔸 چند سهامدار بعد از نقل و انتقال وجود دارد؟ (عدد وارد کنید, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )")
        return ASK_AFTER_COUNT

def ask_after_count(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    count = update.message.text.strip()

    if not count.isdigit():
        context.bot.send_message(chat_id=chat_id, text="❗ لطفاً فقط عدد وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return ASK_AFTER_COUNT

    session['after_count'] = int(count)
    session['after_index'] = 1
    session['after_shareholders'] = []
    context.bot.send_message(chat_id=chat_id, text="🔹 نام سهامدار شماره 1 (بعد از نقل و انتقال, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ) را وارد نمایید:")
    return ASK_AFTER_NAME

def ask_after_name(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]
    session['current_after'] = {'name': update.message.text.strip()}
    context.bot.send_message(chat_id=chat_id, text="🔹 تعداد سهام این سهامدار را وارد نمایید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    return ASK_AFTER_SHARES

def ask_after_shares(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    session = transfer_sessions[chat_id]

    session['current_after']['shares'] = update.message.text.strip()
    session['after_shareholders'].append(session['current_after'])
    del session['current_after']
    session['after_index'] += 1

    if session['after_index'] <= session['after_count']:
        context.bot.send_message(chat_id=chat_id, text=f"🔹 نام سهامدار شماره {session['after_index']} (بعد از نقل و انتقال, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ) را وارد نمایید:")
        return ASK_AFTER_NAME
    else:
        return generate_transfer_summary(update, context)

def handle_back(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = user_data.get(chat_id)

    if not data or "step" not in data or data["step"] <= 1:
        query.answer("در حال حاضر امکان بازگشت وجود ندارد.")
        return

    step = data["step"]

    # حذف مقدار فیلد مربوط به این مرحله
    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step <= len(common_fields):
            prev_field = common_fields[step - 2]
            data.pop(prev_field, None)
        elif step == 11:  # تعداد شرکا
            data.pop("تعداد شرکا", None)
        elif step > 11:
            current = data.get("current_partner", 1)
            if f"سهم الشرکه شریک {current}" in data:
                data.pop(f"سهم الشرکه شریک {current}")
            elif f"شریک {current}" in data:
                data.pop(f"شریک {current}")
                data["current_partner"] = max(1, current - 1)

    # بازگشت یک مرحله
    data["step"] = max(1, step - 1)
    query.answer("مرحله قبل نمایش داده شد.")
    query.message.delete()

    # بازپرسیدن سوال قبلی
    ask_current_question(chat_id, context)

def ask_current_question(chat_id, context):
    data = user_data[chat_id]
    step = data["step"]

    if step == 1:
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    elif 2 <= step <= 9:
        field = common_fields[step - 1]
        context.bot.send_message(chat_id=chat_id, text=get_label(field, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ))
    elif step == 10:
        context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
    elif step > 10:
        current_partner = data.get("current_partner", 1)
        if f"شریک {current_partner}" not in data:
            context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {current_partner} را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        else:
            context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {current_partner} را وارد کنید (عدد فارسی, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")

def generate_word_file(text: str, filepath: str = None):
    doc = Document()

    # تنظیم فونت B Nazanin اگر نصب باشد
    style = doc.styles['Normal']
    font = style.font
    font.name = 'B Nazanin'
    font.size = Pt(14)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'B Nazanin')

    # راست‌چین کردن و بولد کردن فقط خط اول
    lines = text.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        p = doc.add_paragraph()
        run = p.add_run(line.strip())
        if i == 0:
            run.bold = True
        p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    # مسیر ذخیره‌سازی فایل
    if not filepath:
        filename = f"soratjalase_{uuid.uuid4().hex}.docx"
        filepath = os.path.join("/tmp", filename)

    doc.save(filepath)
    return filepath
    
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": 0}
    update.message.reply_text(
        "به خدمات ثبتی کوشا خوش آمدید 🙏🏼\n"
        "در کمتر از چند دقیقه، صورتجلسه رسمی و دقیق شرکت خود را آماده دریافت خواهید کرد.\n"
        "همه‌چیز طبق آخرین قوانین ثبت شرکت‌ها تنظیم می‌شود."
    )
    keyboard = [
        [InlineKeyboardButton("🏢 تغییر آدرس", callback_data='تغییر آدرس')],
        [InlineKeyboardButton("🔄 نقل و انتقال سهام", callback_data='نقل و انتقال سهام')],
        [InlineKeyboardButton("🧾 تغییر موضوع فعالیت", callback_data='تغییر موضوع فعالیت')],
        [InlineKeyboardButton("➕ الحاق به موضوع فعالیت", callback_data='الحاق به موضوع فعالیت')],
        [InlineKeyboardButton("⏳ تمدید سمت اعضا", callback_data='تمدید سمت اعضا')],
        [InlineKeyboardButton("📈 افزایش سرمایه", callback_data='افزایش سرمایه')],
        [InlineKeyboardButton("📉 کاهش سرمایه", callback_data='کاهش سرمایه')],
        [InlineKeyboardButton("🏷️ تغییر نام شرکت", callback_data='تغییر نام شرکت')],
        [InlineKeyboardButton("❌ انحلال شرکت", callback_data='انحلال شرکت')],
        [InlineKeyboardButton("💰 پرداخت سرمایه تعهدی شرکت", callback_data='پرداخت سرمایه تعهدی شرکت')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("💬 برای چه موضوعی صورتجلسه نیاز دارید؟\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if chat_id not in user_data:
        user_data[chat_id] = {"step": 0}

    data = user_data[chat_id]
    step = data.get("step", 0)

    if "موضوع صورتجلسه" not in data:
        context.bot.send_message(chat_id=chat_id, text="لطفاً ابتدا موضوع صورتجلسه را انتخاب کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return

    # تعریف فیلدهای پایه برای تغییر آدرس مسئولیت محدود
    common_fields = ["نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت", "آدرس جدید", "کد پستی", "وکیل"]

    # حالت تغییر آدرس + مسئولیت محدود
    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if 2 <= step <= 9:
            field = common_fields[step - 1]

            if field == "تاریخ":
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ).")
                    return

            if field in persian_number_fields:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                    return

            data[field] = text
            data["step"] += 1

            if step == 9:
                context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
                return
            else:
                next_field = common_fields[step]
                context.bot.send_message(chat_id=chat_id, text=get_label(next_field, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ))
                return

        if step == 10:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️لطفاً تعداد شرکا را فقط با عدد وارد کنید (بین ۲ تا ۷, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ).")
                return
            count = int(text)
            if count < 2 or count > 7:
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد شرکا باید بین ۲ تا ۷ باشد. لطفاً مجدداً وارد کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                return
            data["تعداد شرکا"] = count
            data["step"] += 1
            data["current_partner"] = 1
            context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره ۱ را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step > 10:
            current_partner = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)

            if f"شریک {current_partner}" not in data:
                data[f"شریک {current_partner}"] = text
                context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {current_partner} را به ریال وارد کنید (عدد فارسی, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
                return
            elif f"سهم الشرکه شریک {current_partner}" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️لطفاً میزان سهم الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                    return
                data[f"سهم الشرکه شریک {current_partner}"] = text
                if current_partner < count:
                    data["current_partner"] = current_partner + 1
                    context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {current_partner + 1} را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                    return
                else:
                    send_summary(chat_id, context)
                    return
        return

        # حالت نقل و انتقال سهام + سهامی خاص
    if data.get("موضوع صورتجلسه") == "نقل و انتقال سهام" and data.get("نوع شرکت") == "سهامی خاص":
        if step == 1:
            transfer_sessions[chat_id] = {}
            transfer_sessions[chat_id]["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 2:
            transfer_sessions[chat_id]["شماره ثبت"] = text
            data["step"] = 3
            context.bot.send_message(chat_id=chat_id, text="شناسه ملی شرکت را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 3:
            transfer_sessions[chat_id]["شناسه ملی"] = text
            data["step"] = 4
            context.bot.send_message(chat_id=chat_id, text="سرمایه ثبت شده شرکت را وارد کنید (عدد فارسی, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                return
            transfer_sessions[chat_id]["سرمایه ثبت شده (ریال)"] = text
            data["step"] = 5
            context.bot.send_message(chat_id=chat_id, text="تاریخ جلسه را وارد کنید (مثلاً ۱۴۰۴/۰۴/۰۷, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
            return

        if step == 5:
            if text.count("/") != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️تاریخ را با فرمت صحیح وارد کنید (۱۴۰۴/۰۴/۰۷, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ).")
                return
            transfer_sessions[chat_id]["تاریخ جلسه"] = text
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text="ساعت جلسه را وارد کنید (مثلاً ۱۰:۰۰, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ):")
            return

        if step == 6:
            transfer_sessions[chat_id]["ساعت جلسه"] = text
            data["step"] = 7
            context.bot.send_message(chat_id=chat_id, text="نام مدیر عامل را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 7:
            transfer_sessions[chat_id]["مدیر عامل"] = text
            data["step"] = 8
            context.bot.send_message(chat_id=chat_id, text="نام نایب رئیس جلسه را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 8:
            transfer_sessions[chat_id]["نایب رییس"] = text
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text="نام رئیس جلسه را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 9:
            transfer_sessions[chat_id]["رییس جلسه"] = text
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text="نام منشی جلسه را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 10:
            transfer_sessions[chat_id]["منشی"] = text
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text="نام وکیل برای ثبت در اداره ثبت شرکت‌ها را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
            return

        if step == 11:
            transfer_sessions[chat_id]["وکیل"] = text
            # بقیه مراحل مربوط به فروشندگان در فایل جداگانه هندل می‌شوند
            return ask_seller_name(update, context)
	
    # منطق قبلی برای سایر موارد و صورتجلسات

    if step == 1:
        data["نام شرکت"] = text
        data["step"] = 2
        next_field = fields[2]
        label = get_label(next_field)
        context.bot.send_message(chat_id=chat_id, text=label, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return

    if step == 0:
        context.bot.send_message(chat_id=chat_id, text="لطفاً نوع شرکت را از گزینه‌های ارائه شده انتخاب کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return

    if 2 <= step < len(fields):
        field = fields[step]

        if field == "تاریخ":
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) ).")
                return

        if field in persian_number_fields:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
                return

        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields):
            next_field = fields[data["step"]]
            label = get_label(next_field)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        else:
            send_summary(chat_id, context)
        return

    context.bot.send_message(chat_id=chat_id, text="لطفاً منتظر بمانید...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )

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

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()

    if "موضوع صورتجلسه" not in user_data.get(chat_id, {}):
        user_data[chat_id]["موضوع صورتجلسه"] = query.data
        user_data[chat_id]["step"] = 0
        keyboard = [
            [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
            [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id, text=f"موضوع صورتجلسه انتخاب شد: {query.data}\n\nنوع شرکت را انتخاب کنید:", reply_markup=reply_markup)
        return

    if user_data[chat_id].get("step") == 0:
        user_data[chat_id]["نوع شرکت"] = query.data

        # اگر موضوع نقل و انتقال سهام و نوع شرکت سهامی خاص بود، مسیر خاص خودش اجرا بشه
        if user_data[chat_id]["موضوع صورتجلسه"] == "نقل و انتقال سهام" and query.data == "سهامی خاص":
    return start_transfer_process(update, context)
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        return


def generate_transfer_summary(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    data = transfer_sessions[chat_id]

    # اطلاعات ثابت اولیه
    fields = ["نام شرکت", "نوع شرکت", "شماره ثبت", "شناسه ملی", "سرمایه ثبت شده (ریال)",
              "تاریخ جلسه", "ساعت جلسه", "مدیر عامل", "نایب رییس", "رییس جلسه", "منشی", "وکیل"]
    session = {k: data[k] for k in fields}
    sellers = data['sellers']
    before = data['before_shareholders']
    after = data['after_shareholders']

    # تولید خط‌های واگذاری
    transfer_texts = []
    if len(sellers) == 2 and sellers[0]['seller'] == sellers[1]['seller']:
        s1, s2 = sellers
        transfer_texts.append(
            f"    {s1['seller']} به شماره ملی {s1['seller_national_id']} تعداد {s1['shares']} سهم از کل سهام خود را به {s1['buyer']} به شماره ملی {s1['buyer_national_id']} به آدرس {s1['buyer_address']} واگذار و تعداد {s2['shares']} سهم از کل سهام خود را به {s2['buyer']} به شماره ملی {s2['buyer_national_id']} به آدرس {s2['buyer_address']} واگذار کرد"
        )
    else:
        for s in sellers:
            if s['shares'] == s['total_shares']:
                transfer_texts.append(
                    f"    {s['seller']} به شماره ملی {s['seller_national_id']} تعداد {s['shares']} سهم از کل سهام خود به {s['buyer']} به شماره ملی {s['buyer_national_id']} به آدرس {s['buyer_address']} واگذار کرد و از شرکت خارج شد و دیگر هیچ گونه حق و سمتی ندارد."
                )
            else:
                transfer_texts.append(
                    f"    {s['seller']} به شماره ملی {s['seller_national_id']} تعداد {s['shares']} سهم از کل سهام خود به {s['buyer']} به شماره ملی {s['buyer_national_id']} به آدرس {s['buyer_address']} واگذار کرد."
                )

    seller_signs = "\n\n".join([f"{s['seller']}                          {s['buyer']}" for s in sellers])

    # جدول سهامداران قبل
    before_table = "\n".join([
        f"{i+1}\n\t{sh['name']}\t{sh['shares']}\t" for i, sh in enumerate(before)
    ])

    # جدول بعد از نقل و انتقال
    after_table = "\n".join([
        f"{i+1}\n\t{sh['name']}\t{sh['shares']}\t" for i, sh in enumerate(after)
    ])

    text = f"""نقل و انتقال سهام شرکت سهامی خاص
متن : صورتجلسه مجمع عمومی فوق العاده شرکت {session['نام شرکت']} ){session['نوع شرکت']}(
شماره ثبت شرکت :     {session['شماره ثبت']}
شناسه ملی :      {session['شناسه ملی']}
سرمایه ثبت شده : {session['سرمایه ثبت شده (ریال)']} ریال
صورتجلسه مجمع عمومی فوق العاده شرکت {session['نام شرکت']} ){session['نوع شرکت']} (ثبت شده به شماره {session['شماره ثبت']} در تاریخ  {session['تاریخ جلسه']} ساعت {session['ساعت جلسه']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.
الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 
ـ  {session['مدیر عامل']}                                   به سمت رئیس جلسه 
ـ  {session['نایب رییس']}                                  به سمت ناظر 1 جلسه 
ـ  {session['رییس جلسه']}                                        به سمت ناظر 2 جلسه 
ـ  {session['منشی']}                         به سمت منشی جلسه انتخاب شدند

ب: دستور جلسه اتخاذ تصمیم در خصوص نقل و انتقال سهام، مجمع موافقت و تصویب نمود که:
{chr(10).join(transfer_texts)}

مجمع به {session['وکیل']} احدی از سهامداران شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید. 

امضاء اعضاء هیات رئیسه: 
رئیس جلسه :  {session['مدیر عامل']}                                   ناظر1 جلسه : {session['نایب رییس']}                               


ناظر2جلسه : {session['رییس جلسه']}                                       منشی جلسه: {session['منشی']}


فروشندگان : {sellers[0]['seller']}                          خریداران: {sellers[0]['buyer']}                          

                                                                               
	                   	                 {sellers[1]['seller'] if len(sellers)>1 else ''}                               {sellers[1]['buyer'] if len(sellers)>1 else ''}                

صورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {session['تاریخ جلسه']}
{session['نام شرکت']} قبل از نقل و انتقال سهام

ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران
{before_table}

صورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {session['تاریخ جلسه']}
{session['نام شرکت']} بعد از نقل و انتقال سهام

ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران
{after_table}



صورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {session['تاریخ جلسه']}
{session['نام شرکت']}
ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران
{before_table}
"""

    # ساخت فایل Word
    path = generate_word_file(text)
    context.bot.send_message(chat_id=chat_id, text="✅ صورتجلسه آماده شد. فایل Word زیر را دریافت کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
    context.bot.send_document(chat_id=chat_id, document=open(path, 'rb'))

    return ConversationHandler.END

def send_summary(chat_id, context):
    data = user_data[chat_id]
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        update = Update(update_id=None, message=type('msg', (object,), {'chat_id': chat_id})())  # شبیه‌سازی update
        generate_transfer_summary(update, context)
        return
	
    if موضوع == "تغییر آدرس" and نوع_شرکت == "مسئولیت محدود":
        # صورتجلسه مسئولیت محدود با لیست شرکا
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

به آقای {data['وکیل']} احدی از شرکاء وکالت داده می شود تا ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و امضاء ذیل دفتر ثبت اقدام نماید.

امضاء شرکا : 

"""
        # فاصله بین اسامی امضاءها به سبک نمونه
        signers = ""
        for i in range(1, count + 1):
            signers += f"{data.get(f'شریک {i}', '')}     "
        text += signers
        context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )
        
        # ✅ ساخت فایل Word و ارسال
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
    
        os.remove(file_path)  # ← حذف فایل پس از ارسال (اختیاری)
    
    elif موضوع == "تغییر آدرس" and نوع_شرکت == "سهامی خاص":
        # فقط در این حالت صورتجلسه سهامی خاص را بفرست
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
        context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )

        # ✅ ساخت فایل Word و ارسال
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
    
        os.remove(file_path)  # ← حذف فایل پس از ارسال (اختیاری)

    else:
        # در سایر موارد فعلاً چیزی ارسال نشود
        context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات با موفقیت دریافت شد.\nدر حال حاضر صورتجلسه‌ای برای این ترکیب تعریف نشده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 برگشت', callback_data='BACK')]]) )

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

from telegram.ext import ConversationHandler

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text & ~Filters.command, start_transfer_process)],
    states={
        ASK_TRANSFER_FIELD: [MessageHandler(Filters.text & ~Filters.command, ask_transfer_field)],
        ASK_SELLER_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_seller_name)],
        ASK_SELLER_NID: [MessageHandler(Filters.text & ~Filters.command, ask_seller_nid)],
        ASK_SELLER_SHARES: [MessageHandler(Filters.text & ~Filters.command, ask_seller_shares)],
        ASK_SELLER_TOTAL: [MessageHandler(Filters.text & ~Filters.command, ask_seller_total)],
        ASK_BUYER_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_buyer_name)],
        ASK_BUYER_NID: [MessageHandler(Filters.text & ~Filters.command, ask_buyer_nid)],
        ASK_BUYER_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, ask_buyer_address)],
        ASK_MORE_SELLERS: [MessageHandler(Filters.text & ~Filters.command, ask_more_sellers)],
        ASK_BEFORE_COUNT: [MessageHandler(Filters.text & ~Filters.command, ask_before_count)],
        ASK_BEFORE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_before_name)],
        ASK_BEFORE_SHARES: [MessageHandler(Filters.text & ~Filters.command, ask_before_shares)],
        ASK_AFTER_COUNT: [MessageHandler(Filters.text & ~Filters.command, ask_after_count)],
        ASK_AFTER_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_after_name)],
        ASK_AFTER_SHARES: [MessageHandler(Filters.text & ~Filters.command, ask_after_shares)],
    },
    fallbacks=[CallbackQueryHandler(handle_back, pattern='^BACK$')]
)

dispatcher.add_handler(conv_handler)
