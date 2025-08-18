
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram import ChatAction
from flask import Flask, request
from collections import defaultdict
# from docx import Document  # moved to lazy import
# from docx.shared import Pt  # moved to lazy import
# from docx.oxml.ns import qn  # moved to lazy import
# from docx.enum.text import WD_PARAGRAPH_ALIGNMENT  # moved to lazy import
import os
import uuid
from groq import Groq
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

# متن دکمه بازگشت
BACK_BTN = "⬅️ بازگشت"

GROQ_MODEL_QUALITY = "llama-3.3-70b-versatile" # کیفیت بالاتر
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def ask_groq(user_text: str, system_prompt: str = None, max_tokens: int = 1024) -> str:
    if system_prompt is None:
        system_prompt = (
            "You are an assistant answering in Persian (Farsi). "
            "متخصص قانون تجارت ایران و ثبت شرکت‌ها هستی. جواب‌ها کوتاه و کاربردی باشند."
        )

    resp = groq_client.chat.completions.create(
        model=GROQ_MODEL,  # همیشه 70B
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


# تابع ساخت کیبورد اصلی که فقط دکمه بازگشت داره
def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(AI_ASK_TEXT), KeyboardButton(BACK_BTN)]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
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

def is_valid_persian_national_id(s: str) -> bool:
    """بررسی کند که ورودی دقیقاً ۱۰ رقم فارسی باشد"""
    if not s or len(s) != 10:
        return False
    return all('۰' <= ch <= '۹' for ch in s)

def is_valid_persian_date(s: str) -> bool:
    # الگوی YYYY/MM/DD با اعداد فارسی
    return bool(re.fullmatch(r"[۰-۹]{4}/[۰-۹]{2}/[۰-۹]{2}", s or ""))

def has_min_digits_fa(s: str, n: int = 10) -> bool:
    # تبدیل به انگلیسی و شمارش رقم‌ها
    en = fa_to_en_number(s or "")
    digits = "".join(ch for ch in en if ch.isdigit())
    return len(digits) >= n

def generate_word_file(text: str, filepath: str = None):
    _lazy_import_docx()
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
def send_topic_menu(chat_id, context):
    """منوی انتخاب «موضوع صورتجلسه» را نشان می‌دهد."""
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
    """پس از انتخاب موضوع، منوی «نوع شرکت» را نشان می‌دهد."""
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

def get_label(field, **kwargs):
    labels = {
        "نوع شرکت": "نوع شرکت را انتخاب کنید:",
        "نام شرکت": "نام شرکت را وارد کنید:",
        "شماره ثبت": "شماره ثبت شرکت را وارد کنید (اعداد فارسی):",
        "شناسه ملی": "شناسه ملی شرکت را وارد کنید (اعداد فارسی):",
        "سرمایه": "سرمایه ثبت‌شده شرکت را به ریال وارد کنید (اعداد فارسی):",
        "تاریخ": "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):",
        "ساعت": "ساعت جلسه را وارد کنید (اعداد فارسی):",
        "مدیر عامل": "مدیر عامل (رئیس جلسه) را وارد کنید:",
        "نایب رییس": "ناظر 1 جلسه را وارد کنید (از بین هیئت مدیره):",
        "رییس": "ناظر 2 جلسه را وارد کنید (از بین هیئت مدیره):",
        "منشی": "منشی جلسه را وارد کنید:",
        "آدرس جدید": "آدرس جدید شرکت را وارد کنید:",
        "کد پستی": "کد پستی آدرس جدید را وارد کنید (اعداد فارسی):",
        "وکیل": "نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:",
        "شماره دفترخانه": "شماره دفترخانه فروشنده {i} را وارد کنید (مثلاً: 22 تهران):",
        "نام جدید شرکت": "نام جدید شرکت را وارد کنید:",

        # برچسب‌های مخصوص انحلال
        "علت انحلال": "علت انحلال را وارد کنید (مثلاً: مشکلات اقتصادی):",
        "نام مدیر تصفیه": "نام مدیر تصفیه را وارد کنید:",
        "کد ملی مدیر تصفیه": "کد ملی مدیر تصفیه را وارد کنید (اعداد فارسی):",
        "مدت مدیر تصفیه": "مدت مدیر تصفیه (سال) را وارد کنید (اعداد فارسی):",
        "آدرس مدیر تصفیه": "آدرس مدیر تصفیه و محل تصفیه را وارد کنید:",
        "تعداد سهامداران حاضر": "تعداد سهامداران حاضر را وارد کنید (عدد):",

        # برای مسیرهای دیگر که استفاده داری
        "تعداد شرکا": "تعداد شرکا را وارد کنید (بین ۲ تا ۷):",

        # 🔔 اطلاعیه ماده ۱۰۳
        "اطلاعیه_ماده103": (
            "یادآوری مهم — ماده ۱۰۳ قانون تجارت ⚖️\n"
            "نقل‌وانتقال سهم‌الشرکه در شرکت با مسئولیت محدود، از عقود تشریفاتی است و باید به موجب «سند رسمی» در دفترخانه انجام شود. 🏛️📄\n\n"
            "برای تکمیل این صورتجلسه، لازم است ابتدا {سند} را در یکی از دفاتر اسناد رسمی تنظیم کرده باشید؛ "
            "زیرا درج مشخصات آن در متن صورتجلسه الزامی است. ✍️🧾"
        ),
    }

    msg = labels.get(field, f"{field} را وارد کنید:")
    try:
        return msg.format(**kwargs)  # برای کلیدهایی که جای‌نگهدار دارند مثل {سند}، {i}، {k}
    except Exception:
        return msg

def cmd_ai(update, context):
    chat_id = update.effective_chat.id
    args_text = (update.message.text or "").split(" ", 1)
    query = args_text[1].strip() if len(args_text) > 1 else ""

    if not query:
        update.message.reply_text("سؤال را بعد از /ai بنویسید.")
        return

    try:
        answer = ask_groq(query, max_tokens=900)  # بدون انتخاب مدل
        for i in range(0, len(answer), 3500):
            update.message.reply_text(answer[i:i+3500])
    except Exception as e:
        update.message.reply_text("❌ خطا در دریافت پاسخ از Groq.")
        print("GROQ ERROR:", e)


def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = (update.message.text or "").strip()
    user_data.setdefault(chat_id, {"step": 0})

    # --- گارد حالت AI (ابتدای تابع و با تورفتگی درست) ---
    if context.user_data.get("ai_mode"):
        return  # وقتی در AI هستیم، هندلر مراحل پاسخ را نگیرد

    # اگر کاربر دکمه بازگشت زد
    if text == BACK_BTN:
        handle_back(update, context)
        return

    # setdefault بالا کافی‌ست؛ این بلاک تکراری را لازم نیست نگه داری
    # if chat_id not in user_data:
    #     user_data[chat_id] = {"step": 0}

    data = user_data[chat_id]
    step = data.get("step", 0)

    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    if "موضوع صورتجلسه" not in data:
        context.bot.send_message(
            chat_id=chat_id,
            text="لطفاً ابتدا موضوع صورتجلسه را انتخاب کنید. برای شروع مجدد /start را ارسال کنید .",
            reply_markup=main_keyboard()
        )
        return

    # تعریف فیلدهای پایه برای تغییر آدرس مسئولیت محدود (در صورت نیاز)
    common_fields = ["نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت", "آدرس جدید", "کد پستی", "وکیل"]

    # -------------------------------
    # تغییر نام شرکت - سهامی خاص
    # گام‌ها: 1 نام شرکت، 2 ثبت، 3 شناسه، 4 سرمایه، 5 تاریخ، 6 ساعت،
    # 7 مدیر عامل، 8 نایب رییس، 9 رییس، 10 منشی،
    # 11 نام جدید شرکت، 12 وکیل → خروجی
    # -------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "سهامی خاص":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = get_label("شماره ثبت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = get_label("شناسه ملی")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = get_label("سرمایه")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = get_label("تاریخ")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if 'is_valid_persian_date' in globals():
                if not is_valid_persian_date(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. نمونه: ۱۴۰۴/۰۵/۱۵", reply_markup=main_keyboard())
                    return
            else:
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                    return
            data["تاریخ"] = text
            data["step"] = 6
            label = get_label("ساعت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = get_label("مدیر عامل")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            data["مدیر عامل"] = text
            data["step"] = 8
            label = get_label("نایب رییس")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            data["نایب رییس"] = text
            data["step"] = 9
            label = get_label("رییس")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            data["رییس"] = text
            data["step"] = 10
            label = get_label("منشی")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            data["منشی"] = text
            data["step"] = 11
            label = get_label("نام جدید شرکت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            data["نام جدید شرکت"] = text
            data["step"] = 12
            label = get_label("وکیل")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            data["وکیل"] = text
            send_summary(chat_id, context)
            data["step"] = 13
            return

        if step >= 13:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات ثبت شد. برای شروع مجدد /start را ارسال کنید.")
            return
    
    # تعریف فیلدهای پایه برای تغییر آدرس مسئولیت محدود
    common_fields = ["نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت", "آدرس جدید", "کد پستی", "وکیل"]

    # -------------------------------
    # تغییر آدرس - مسئولیت محدود
    # -------------------------------
    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if 2 <= step <= 9:
            field = common_fields[step - 1]

            if field == "تاریخ":
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).", reply_markup=main_keyboard())
                    return

            if field in persian_number_fields:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                    return

            data[field] = text
            data["step"] += 1

            if step == 9:
                label = "تعداد شرکا را وارد کنید (بین ۲ تا ۷):"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            else:
                next_field = common_fields[step]
                label = get_label(next_field)
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return

        if step == 10:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️لطفاً تعداد شرکا را فقط با عدد وارد کنید (بین ۲ تا ۷).", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 2 or count > 7:
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد شرکا باید بین ۲ تا ۷ باشد. لطفاً مجدداً وارد کنید.", reply_markup=main_keyboard())
                return
            data["تعداد شرکا"] = count
            data["step"] += 1
            data["current_partner"] = 1
            label = "نام شریک شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step > 10:
            current_partner = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)

            if f"شریک {current_partner}" not in data:
                data[f"شریک {current_partner}"] = text
                label = f"میزان سهم الشرکه شریک شماره {current_partner} را به ریال وارد کنید (عدد فارسی):"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"سهم الشرکه شریک {current_partner}" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️لطفاً میزان سهم الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                    return
                data[f"سهم الشرکه شریک {current_partner}"] = text
                if current_partner < count:
                    data["current_partner"] = current_partner + 1
                    label = f"نام شریک شماره {current_partner + 1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                else:
                    send_summary(chat_id, context)
                    data["step"] = 11
                    return

        if step >= 11:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.", reply_markup=main_keyboard())
            return

    # -------------------------------
    # تغییر نام شرکت - مسئولیت محدود
    # -------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = get_label("شماره ثبت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = get_label("شناسه ملی")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = get_label("سرمایه")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = get_label("تاریخ")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if 'is_valid_persian_date' in globals():
                if not is_valid_persian_date(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. نمونه: ۱۴۰۴/۰۵/۱۵", reply_markup=main_keyboard())
                    return
            else:
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                    return
            data["تاریخ"] = text
            data["step"] = 6
            label = get_label("ساعت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = get_label("نام جدید شرکت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            data["نام جدید شرکت"] = text
            data["step"] = 8
            label = get_label("تعداد شرکا")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 2:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل دو شریک لازم است.", reply_markup=main_keyboard())
                return
            data["تعداد شرکا"] = count
            data["current_partner"] = 1
            data["step"] = 9
            label = get_label("نام شریک", i=1)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            i = data["current_partner"]
            data[f"شریک {i}"] = text
            data["step"] = 10
            label = get_label("سهم الشرکه شریک", i=i)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            i = data["current_partner"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سهم‌الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data[f"سهم الشرکه شریک {i}"] = text
            if i < data["تعداد شرکا"]:
                data["current_partner"] = i + 1
                data["step"] = 9
                label = get_label("نام شریک", i=i+1)
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            else:
                data["step"] = 11
                label = get_label("وکیل")
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            data["وکیل"] = text
            send_summary(chat_id, context)
            data["step"] = 12
            return

        if step >= 12:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات ثبت شد. برای شروع مجدد /start را ارسال کنید.", reply_markup=main_keyboard())
            return

    # ✅ تغییر موضوع فعالیت - مسئولیت محدود
    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه شرکت به ریال را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = "ساعت جلسه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "تعداد شرکا را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            data["تعداد شرکا"] = count
            data["current_partner"] = 1
            data["step"] = 8
            label = "نام شریک شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            i = data["current_partner"]
            data[f"شریک {i}"] = text
            data["step"] = 9
            label = f"سهم الشرکه شریک شماره {i} را وارد کنید (عدد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            i = data["current_partner"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سهم الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data[f"سهم الشرکه شریک {i}"] = text
            if i < data["تعداد شرکا"]:
                data["current_partner"] += 1
                data["step"] = 8
                label = f"نام شریک شماره {i+1} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            else:
                data["step"] = 10
                # مرحله بعدی با دکمه‌های اینلاین است؛ این را در last_question ذخیره نکن تا در بازگشت از AI مشکلی نباشد.
                keyboard = [
                    [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                    [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
                ]
                context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # در CallbackHandler مربوط به این مرحله، نیازی به remember_last_question نیست (ورودی از طریق دکمه است)
        if data.get("step") == 10 and update.callback_query:
            answer = update.callback_query.data
            update.callback_query.answer()
            if answer in ["الحاق", "جایگزین"]:
                data["نوع تغییر موضوع"] = answer
                data["step"] = 11
                label = "موضوع جدید فعالیت شرکت را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            data["موضوع جدید"] = text
            data["step"] = 12
            label = "نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            data["وکیل"] = text
            send_summary(chat_id, context)
            return

    # ✅ تغییر موضوع فعالیت – سهامی خاص
    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "سهامی خاص":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه ثبت‌شده شرکت (به ریال، اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = "ساعت جلسه را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "مدیر عامل (رئیس جلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            data["مدیر عامل"] = text
            data["step"] = 8
            label = "ناظر 1 جلسه (نایب رئیس) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            if text == data["مدیر عامل"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر 1 نمی‌تواند با مدیر عامل یکی باشد. شخص دیگری را وارد کنید.", reply_markup=main_keyboard())
                return
            data["نایب رییس"] = text
            data["step"] = 9
            label = "ناظر 2 جلسه (رییس) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            if text == data["مدیر عامل"] or text == data["نایب رییس"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر 2 نمی‌تواند با مدیر عامل یا ناظر 1 یکی باشد.", reply_markup=main_keyboard())
                return
            data["رییس"] = text
            data["step"] = 10
            label = "منشی جلسه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            data["منشی"] = text
            data["step"] = 11
            label = "تعداد سهامداران حاضر را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 1:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل یک سهامدار باید وجود داشته باشد.", reply_markup=main_keyboard())
                return
            data["تعداد سهامداران"] = count
            data["سهامدار_index"] = 1
            data["step"] = 12
            label = "نام سهامدار شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            i = data.get("سهامدار_index", 1)
            prefix = f"سهامدار {i}"
            if f"{prefix} نام" not in data:
                data[f"{prefix} نام"] = text
                label = f"تعداد سهام {prefix} را وارد کنید (اعداد فارسی):"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"{prefix} تعداد" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️تعداد سهام را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                    return
                data[f"{prefix} تعداد"] = text
                if i < data["تعداد سهامداران"]:
                    data["سهامدار_index"] = i + 1
                    label = f"نام سهامدار شماره {i+1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                else:
                    # پس از تکمیل سهامداران، انتخاب الحاق/جایگزین
                    keyboard = [
                        [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                        [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
                    ]
                    data["step"] = 13
                    context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟",
                                             reply_markup=InlineKeyboardMarkup(keyboard))
                    return

        if step == 14:
            data["موضوع جدید"] = text
            data["step"] = 15
            label = "نام وکیل (شخص ثبت‌کننده صورتجلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 15:
            data["وکیل"] = text
            send_summary(chat_id, context)
            return

    # -------------------------------
    # انحلال شرکت - مسئولیت محدود
    # -------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه ثبت‌شده شرکت (ریال، اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = "ساعت جلسه را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "تعداد شرکا را وارد کنید (عدد):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 2:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل دو شریک لازم است.", reply_markup=main_keyboard())
                return
            data["تعداد شرکا"] = count
            data["current_partner"] = 1
            data["step"] = 8
            label = "نام شریک شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            i = data["current_partner"]
            data[f"شریک {i}"] = text
            data["step"] = 9
            label = f"سهم‌الشرکه شریک شماره {i} را به ریال وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            i = data["current_partner"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سهم‌الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data[f"سهم الشرکه شریک {i}"] = text
            if i < data["تعداد شرکا"]:
                data["current_partner"] = i + 1
                data["step"] = 8
                label = f"نام شریک شماره {i+1} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            else:
                data["step"] = 10
                label = "علت انحلال را وارد کنید (مثلاً: مشکلات اقتصادی، توافق شرکا و ...):"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            data["علت انحلال"] = text
            data["step"] = 11
            label = "نام مدیر تصفیه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            data["نام مدیر تصفیه"] = text
            data["step"] = 12
            label = "کد ملی مدیر تصفیه را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            if not is_valid_persian_national_id(text):
                context.bot.send_message(chat_id=chat_id, text="❗️کد ملی باید دقیقاً ۱۰ رقم فارسی باشد.", reply_markup=main_keyboard())
                return
            data["کد ملی مدیر تصفیه"] = text
            data["step"] = 13
            label = "مدت مدیر تصفیه (سال) را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 13:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️مدت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["مدت مدیر تصفیه"] = text
            data["step"] = 14
            label = "آدرس مدیر تصفیه و محل تصفیه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 14:
            data["آدرس مدیر تصفیه"] = text
            data["step"] = 15
            label = "نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 15:
            data["وکیل"] = text
            send_summary(chat_id, context)
            data["step"] = 16
            return

        if step >= 16:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.", reply_markup=main_keyboard())
            return

    # -------------------------------
    # انحلال شرکت - سهامی خاص
    # -------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "سهامی خاص":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه ثبت‌شده (به ریال، اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً ۱۴۰۴/۰۵/۱۵):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = "ساعت جلسه را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "مدیر عامل (رئیس جلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            data["مدیر عامل"] = text
            data["step"] = 8
            label = "ناظر 1 جلسه (از بین هیئت مدیره) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            if text == data["مدیر عامل"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر 1 نمی‌تواند با مدیر عامل یکی باشد.", reply_markup=main_keyboard())
                return
            data["نایب رییس"] = text
            data["step"] = 9
            label = "ناظر 2 جلسه (از بین هیئت مدیره) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            if text == data["مدیر عامل"] or text == data["نایب رییس"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر 2 نمی‌تواند با مدیر عامل یا ناظر 1 یکی باشد.", reply_markup=main_keyboard())
                return
            data["رییس"] = text
            data["step"] = 10
            label = "منشی جلسه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            data["منشی"] = text
            data["step"] = 11
            label = "علت انحلال را وارد کنید (مثلاً: مشکلات اقتصادی ، توافق شرکا و ...):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            data["علت انحلال"] = text
            data["step"] = 12
            label = "نام مدیر تصفیه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            data["نام مدیر تصفیه"] = text
            data["step"] = 13
            label = "کد ملی مدیر تصفیه را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 13:
            if not is_valid_persian_national_id(text):
                context.bot.send_message(chat_id=chat_id, text="❗️کد ملی باید دقیقاً ۱۰ رقم فارسی باشد.", reply_markup=main_keyboard())
                return
            data["کد ملی مدیر تصفیه"] = text
            data["step"] = 14
            label = "مدت مدیر تصفیه (سال) را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 14:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️مدت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["مدت مدیر تصفیه"] = text
            data["step"] = 15
            label = "آدرس مدیر تصفیه و محل تصفیه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 15:
            data["آدرس مدیر تصفیه"] = text
            data["step"] = 16
            label = "تعداد سهامداران حاضر را وارد کنید (عدد):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 16:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            data["تعداد سهامداران حاضر"] = int(text)
            data["سهامدار_index"] = 1
            data["step"] = 17
            label = "نام سهامدار ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

       # حلقه سهامداران: نام → تعداد
        if step == 17:
            i = data["سهامدار_index"]
            if f"سهامدار {i} نام" not in data:
                data[f"سهامدار {i} نام"] = text
                label = f"تعداد سهام سهامدار {i} را وارد کنید (اعداد فارسی):"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"سهامدار {i} تعداد" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️تعداد سهام را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                    return
                data[f"سهامدار {i} تعداد"] = text
                if i < data["تعداد سهامداران حاضر"]:
                    data["سهامدار_index"] += 1
                    label = f"نام سهامدار {i+1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                else:
                    data["step"] = 18
                    label = "نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return

        if step == 18:
            data["وکیل"] = text
            send_summary(chat_id, context)
            data["step"] = 19
            return

        if step >= 19:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.", reply_markup=main_keyboard())
            return


# --- به‌روزرسانی کامل: نقل و انتقال سهم‌الشرکه - مسئولیت محدود ---

    # -------------------------------
    # نقل و انتقال سهم الشرکه - مسئولیت محدود
    # -------------------------------
    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه ثبت‌شده شرکت (ریال):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۶/۰۱):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if not is_valid_persian_date(text):
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. نمونه: ۱۴۰۴/۰۵/۱۵", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = get_label("ساعت")
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "تعداد شرکا را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        # شرکا
        if step == 7:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 2:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل دو شریک لازم است.", reply_markup=main_keyboard())
                return
            data["تعداد شرکا"] = count
            data["current_partner"] = 1
            data["step"] = 8
            label = get_label("نام شریک", i=1)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return
            
        if step == 8:
            i = data["current_partner"]
            data[f"شریک {i}"] = text
            data["step"] = 9
            label = f"سهم‌الشرکه شریک شماره {i} (ریال، اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            i = data["current_partner"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سهم‌الشرکه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data[f"سهم الشرکه شریک {i}"] = text
            if i < data["تعداد شرکا"]:
                data["current_partner"] = i + 1
                data["step"] = 8
                label = f"نام شریک شماره {i+1} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            else:
                data["step"] = 10
                label = "تعداد فروشندگان را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return

        # فروشندگان
        if step == 10:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            data["تعداد فروشندگان"] = int(text)
            data["فروشنده_index"] = 1
            data["step"] = 11
            label = "نام فروشنده شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 11:
            i = data["فروشنده_index"]
            data[f"فروشنده {i} نام"] = text
            data["step"] = 12
            label = f"کد ملی فروشنده {i} را وارد کنید (اعداد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 12:
            i = data["فروشنده_index"]
            if not is_valid_persian_national_id(text):
                context.bot.send_message(chat_id=chat_id, text="❗️کد ملی باید دقیقاً ۱۰ رقم فارسی باشد.", reply_markup=main_keyboard())
                return
            data[f"فروشنده {i} کد ملی"] = text
            data["step"] = 13
            label = get_label("سهم کل فروشنده", i=i)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 13:
            i = data["فروشنده_index"]
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️مبلغ را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data[f"فروشنده {i} سهم کل"] = text
            data["step"] = 14
            label = get_label("شماره سند صلح", i=i)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 14:
            i = data["فروشنده_index"]
            data[f"فروشنده {i} سند صلح"] = text
            data["step"] = 15
            label = f"تاریخ سند صلح فروشنده {i} را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 15:
            i = data["فروشنده_index"]
            if not is_valid_persian_date(text):
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. نمونه: ۱۴۰۴/۰۵/۱۵", reply_markup=main_keyboard())
                return
            data[f"فروشنده {i} تاریخ سند"] = text
            data["step"] = 16
            label = get_label("شماره دفترخانه", i=i)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 16:
            i = data["فروشنده_index"]
            data[f"فروشنده {i} دفترخانه"] = text
            data["step"] = 17
            label = f"تعداد خریداران فروشنده {i} را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 17:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            i = data["فروشنده_index"]
            data[f"تعداد خریداران {i}"] = int(text)
            data[f"خریدار_index_{i}"] = 1
            data["step"] = 18
            label = f"نام خریدار ۱ از فروشنده {i} را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 18:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            data[f"خریدار {i}-{k} نام"] = text
            data["step"] = 19
            label = f"نام پدر خریدار {k} از فروشنده {i}:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 19:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            data[f"خریدار {i}-{k} پدر"] = text
            data["step"] = 20
            label = f"تاریخ تولد خریدار {k} از فروشنده {i}:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 20:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            if not is_valid_persian_date(text):
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. نمونه: ۱۴۰۴/۰۵/۱۵", reply_markup=main_keyboard())
                return
            data[f"خریدار {i}-{k} تولد"] = text
            data["step"] = 21
            label = get_label("کد ملی خریدار", i=i, k=k)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 21:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            if not is_valid_persian_national_id(text):
                context.bot.send_message(chat_id=chat_id, text="❗️کد ملی باید دقیقاً ۱۰ رقم فارسی باشد.", reply_markup=main_keyboard())
                return
            data[f"خریدار {i}-{k} کد ملی"] = text
            data["step"] = 22
            label = get_label("آدرس خریدار", i=i, k=k)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 22:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            data[f"خریدار {i}-{k} آدرس"] = text
            data["step"] = 23
            label = f"میزان سهم‌الشرکه منتقل‌شده به خریدار {k} از فروشنده {i} (ریال):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 23:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
            data[f"خریدار {i}-{k} سهم منتقل"] = text
            if k < data[f"تعداد خریداران {i}"]:
                data[f"خریدار_index_{i}"] = k + 1
                data["step"] = 18
                label = f"نام خریدار {k+1} از فروشنده {i} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            else:
                if i < data["تعداد فروشندگان"]:
                    data["فروشنده_index"] = i + 1
                    data["step"] = 11
                    label = f"نام فروشنده شماره {i+1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                else:
                    data["step"] = 24
                    label = "نام وکیل (ثبت‌کننده صورتجلسه) را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return

        if step == 24:
            data["وکیل"] = text
            send_summary(chat_id, context)
            data["step"] = 25
            return

    # -------------------------------
    # نقل و انتقال سهام - سهامی خاص
    # -------------------------------
    
    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            label = "شماره ثبت شرکت را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 2:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شماره ثبت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شماره ثبت"] = text
            data["step"] = 3
            label = "شناسه ملی شرکت را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 3:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️شناسه ملی را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["شناسه ملی"] = text
            data["step"] = 4
            label = "سرمایه شرکت به ریال را وارد کنید (عدد فارسی):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 4:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️سرمایه را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            data["سرمایه"] = text
            data["step"] = 5
            label = "تاریخ صورتجلسه را وارد کنید (مثلاً: ۱۴۰۴/۰۵/۱۵):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 5:
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست.", reply_markup=main_keyboard())
                return
            data["تاریخ"] = text
            data["step"] = 6
            label = "ساعت جلسه را وارد کنید :"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 6:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return
            saat = int(fa_to_en_number(text))
            if saat < 8 or saat > 17:
                context.bot.send_message(chat_id=chat_id, text="❗️ساعت جلسه باید بین ۸ تا ۱۷ باشد.", reply_markup=main_keyboard())
                return
            data["ساعت"] = text
            data["step"] = 7
            label = "مدیر عامل (رئیس جلسه) را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 7:
            data["مدیر عامل"] = text
            data["step"] = 8
            label = "ناظر اول جلسه را وارد کنید (از بین اعضای هیئت مدیره):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 8:
            if text == data["مدیر عامل"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر اول نمی‌تواند با مدیر عامل یکی باشد. لطفاً شخص دیگری را انتخاب کنید.", reply_markup=main_keyboard())
                return
            data["نایب رییس"] = text
            data["step"] = 9
            label = "ناظر دوم جلسه را وارد کنید (از بین اعضای هیئت مدیره):"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 9:
            if text == data["مدیر عامل"] or text == data["نایب رییس"]:
                context.bot.send_message(chat_id=chat_id, text="❗️ناظر دوم نمی‌تواند با مدیر عامل یا ناظر اول یکی باشد. لطفاً شخص دیگری را انتخاب کنید.", reply_markup=main_keyboard())
                return
            data["رییس"] = text
            data["step"] = 10
            label = "منشی جلسه را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 10:
            data["منشی"] = text
            data["step"] = 11
            label = "تعداد فروشندگان را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        
        # شروع دریافت فروشندگان
        if step == 11:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد فروشندگان را با عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 1:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل یک فروشنده باید وجود داشته باشد.", reply_markup=main_keyboard())
                return
            data["تعداد فروشندگان"] = count
            data["فروشنده_index"] = 1
            data["step"] = 12
            label = "نام فروشنده شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step >= 12 and data.get("فروشنده_index", 0) <= data.get("تعداد فروشندگان", 0):
            i = data["فروشنده_index"]
            prefix = f"فروشنده {i}"

            if f"{prefix} نام" not in data:
                data[f"{prefix} نام"] = text
                label = f"کد ملی {prefix} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            if f"{prefix} کد ملی" not in data:
                data[f"{prefix} کد ملی"] = text
                label = f"تعداد سهام منتقل‌شده توسط {prefix} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"{prefix} تعداد" not in data:
                data[f"{prefix} تعداد"] = text
                label = "تعداد خریداران برای این فروشنده را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                data["step"] = 13
                return

        # مرحله تعیین تعداد خریداران برای هر فروشنده

        if step == 13:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد خریداران را با عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            if count < 1:
                context.bot.send_message(chat_id=chat_id, text="❗️حداقل یک خریدار لازم است.", reply_markup=main_keyboard())
                return
            i = data["فروشنده_index"]
            data[f"تعداد خریداران {i}"] = count
            data[f"خریدار_index_{i}"] = 1
            data["step"] = 14
            label = f"نام خریدار شماره ۱ از فروشنده {i} را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return

        if step == 14:
            i = data["فروشنده_index"]
            k = data[f"خریدار_index_{i}"]
        
            if f"خریدار {i}-{k} نام" not in data:
                data[f"خریدار {i}-{k} نام"] = text
                label = f"کد ملی خریدار {k} از فروشنده {i} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"خریدار {i}-{k} کد ملی" not in data:
                data[f"خریدار {i}-{k} کد ملی"] = text
                label = f"آدرس خریدار {k} از فروشنده {i} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"خریدار {i}-{k} آدرس" not in data:
                data[f"خریدار {i}-{k} آدرس"] = text
                total = data[f"تعداد خریداران {i}"]
                if k < total:
                    data[f"خریدار_index_{i}"] += 1
                    label = f"نام خریدار شماره {k+1} از فروشنده {i} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                else:
                    # همه خریداران ثبت شدن
                    if i < data["تعداد فروشندگان"]:
                        data["فروشنده_index"] += 1
                        data["step"] = 12  # برمی‌گردیم به مرحله نام فروشنده جدید
                        label = f"نام فروشنده شماره {i+1} را وارد کنید:"
                        remember_last_question(context, label)
                        context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    else:
                        data["step"] = 15  # مرحله بعد از خریداران (مثلاً سهامداران قبل)
                        label = "تعداد سهامداران قبل از نقل و انتقال را وارد کنید:"
                        remember_last_question(context, label)
                        context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                    return
                
            # مرحله دریافت سهامداران قبل از انتقال
        if step == 15:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            data["تعداد سهامداران قبل"] = count
            data["سهامدار_قبل_index"] = 1
            data["step"] = 16
            label = f"نام سهامدار قبل شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return
    
        if step == 16:
            i = data["سهامدار_قبل_index"]
            prefix = f"سهامدار قبل {i}"
            if f"{prefix} نام" not in data:
                data[f"{prefix} نام"] = text
                label = f"تعداد سهام {prefix} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"{prefix} تعداد" not in data:
                data[f"{prefix} تعداد"] = text
                if i < data["تعداد سهامداران قبل"]:
                    data["سهامدار_قبل_index"] += 1
                    label = f"نام سهامدار قبل شماره {i+1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                else:
                    data["step"] = 17
                    label = "تعداد سهامداران بعد از نقل و انتقال را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
    
        # مرحله دریافت سهامداران بعد از انتقال
        if step == 17:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️عدد وارد کنید.", reply_markup=main_keyboard())
                return
            count = int(text)
            data["تعداد سهامداران بعد"] = count
            data["سهامدار_بعد_index"] = 1
            data["step"] = 18
            label = f"نام سهامدار بعد شماره ۱ را وارد کنید:"
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
            return
    
        if step == 18:
            i = data["سهامدار_بعد_index"]
            prefix = f"سهامدار بعد {i}"
            if f"{prefix} نام" not in data:
                data[f"{prefix} نام"] = text
                label = f"تعداد سهام {prefix} را وارد کنید:"
                remember_last_question(context, label)
                context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
            elif f"{prefix} تعداد" not in data:
                data[f"{prefix} تعداد"] = text
                if i < data["تعداد سهامداران بعد"]:
                    data["سهامدار_بعد_index"] += 1
                    label = f"نام سهامدار بعد شماره {i+1} را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                else:
                    data["step"] = 19
                    label = "نام وکیل (شخص ثبت‌کننده صورتجلسه) را وارد کنید:"
                    remember_last_question(context, label)
                    context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
                return
    
        # مرحله آخر: دریافت وکیل
        if step == 19:
            data["وکیل"] = text
            send_summary(chat_id, context)  # ✅ ساخت و ارسال صورتجلسه
            data["step"] = 20
            return
    
        if step >= 20:
            context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است. برای شروع مجدد /start را ارسال کنید.", reply_markup=main_keyboard())
            return

 
# منطق قبلی برای سایر موارد و صورتجلسات

    if step == 1:
        data["نام شرکت"] = text
        data["step"] = 2
        next_field = fields[2]
        label = get_label(next_field)
        remember_last_question(context, label)
        context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
        return

    if step == 0:
        context.bot.send_message(chat_id=chat_id, text="لطفاً نوع شرکت را از گزینه‌های ارائه شده انتخاب کنید.", reply_markup=main_keyboard())
        return

    if 2 <= step < len(fields):
        field = fields[step]

        if field == "تاریخ":
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).", reply_markup=main_keyboard())
                return

        if field in persian_number_fields:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.", reply_markup=main_keyboard())
                return

        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields):
            next_field = fields[data["step"]]
            label = get_label(next_field)
            remember_last_question(context, label)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=main_keyboard())
        else:
            send_summary(chat_id, context)
        return

    context.bot.send_message(
        chat_id=chat_id,
        text="دستور نامعتبر یا مرحله ناشناخته است. برای بازگشت از دکمه «⬅️ بازگشت» استفاده کنید یا /start بزنید.",
        reply_markup=main_keyboard()
    )

def handle_back(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    data = user_data.setdefault(chat_id, {"step": 0})
    step = data.get("step", 0)
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

    # اگر هنوز موضوع انتخاب نشده → منوی موضوعات را دوباره نشان بده
    if not موضوع:
        context.bot.send_message(chat_id=chat_id, text="به منوی موضوعات برگشتید.")
        # همون منوی موضوعات فعلی خودت را صدا بزن (تابعش هر چی اسم گذاشتی)
        send_topic_menu(chat_id, context)
        return

    # اگر در انتخاب «نوع شرکت» هستیم یا باید به آن برگردیم
    if step == 1:  # قبل از سؤال «نام شرکت»
        data.pop("نوع شرکت", None)
        data["step"] = 0
        context.bot.send_message(chat_id=chat_id, text="به انتخاب نوع شرکت برگشتید.")
        send_company_type_menu(chat_id, context)
        return

    # --------------------------------------
    # بازگشت: تغییر نام شرکت - سهامی خاص
    # --------------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "سهامی خاص":
        # 2..6: یک قدم عقب با لیست کلیدها
        if 2 <= step <= 6:
            prev_step = step - 1
            order = ["نام شرکت","شماره ثبت","شناسه ملی","سرمایه","تاریخ","ساعت"]
            key = order[prev_step - 1] if prev_step - 1 < len(order) else None
            if prev_step == 1:
                data.pop("نام شرکت", None)
                data["step"] = 1
                context.bot.send_message(chat_id=chat_id, text=get_label("نام شرکت"))
                return
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                context.bot.send_message(chat_id=chat_id, text=get_label(key))
                return
    
        # 7..10: هیئت‌رئیسه
        if step == 7:
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text=get_label("ساعت"))
            return
        if step == 8:
            data.pop("مدیر عامل", None)
            data["step"] = 7
            context.bot.send_message(chat_id=chat_id, text=get_label("مدیر عامل"))
            return
        if step == 9:
            data.pop("نایب رییس", None)
            data["step"] = 8
            context.bot.send_message(chat_id=chat_id, text=get_label("نایب رییس"))
            return
        if step == 10:
            data.pop("رییس", None)
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=get_label("رییس"))
            return
    
        # 11..12: نام جدید ← وکیل
        if step == 11:
            data.pop("منشی", None)
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text=get_label("منشی"))
            return
        if step == 12:
            data.pop("نام جدید شرکت", None)
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text=get_label("نام جدید شرکت"))
            return
    
        # 1: برگشت به انتخاب نوع شرکت (در صورت نیاز)
        if step == 1:
            data["step"] = 0
            send_company_type_menu(update, context)
            return

    # --------------------------------------
    # بازگشت: تغییر موضوع فعالیت – سهامی خاص
    # مراحل: 1..10 خطی، 11 تعداد سهامداران، 12 حلقه سهامداران، 13 انتخاب الحاق/جایگزین (callback)، 14 موضوع جدید، 15 وکیل
    # --------------------------------------
    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "سهامی خاص":
        # بازگشت در مسیر خطی 2..10
        if 2 <= step <= 10:
            prev_step = step - 1
            linear_order = {
                1:"نام شرکت", 2:"شماره ثبت", 3:"شناسه ملی", 4:"سرمایه", 5:"تاریخ",
                6:"ساعت", 7:"مدیر عامل", 8:"نایب رییس", 9:"رییس"
            }
            key = linear_order.get(prev_step, None)
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
            # prev_step == 10 → منشی
            if prev_step == 10:
                data.pop("منشی", None)
                data["step"] = 10
                context.bot.send_message(chat_id=chat_id, text="منشی جلسه را وارد کنید:")
                return

        # 11 → بازگشت به 10 (منشی)
        if step == 11:
            data.pop("تعداد سهامداران", None)
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text="منشی جلسه را وارد کنید:")
            return

        # 12 → داخل حلقه سهامداران
        if step == 12:
            i = data.get("سهامدار_index", 1)
            # اگر منتظر نام هستیم
            if f"سهامدار {i} نام" not in data:
                if i == 1:
                    data.pop("تعداد سهامداران", None)
                    data["step"] = 11
                    context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران حاضر را وارد کنید:")
                    return
                else:
                    prev_i = i - 1
                    data["سهامدار_index"] = prev_i
                    data.pop(f"سهامدار {prev_i} تعداد", None)
                    data["step"] = 12
                    context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار {prev_i} را وارد کنید (اعداد فارسی):")
                    return
            # اگر منتظر تعداد هستیم
            if f"سهامدار {i} تعداد" not in data:
                data.pop(f"سهامدار {i} نام", None)
                data["step"] = 12
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار {i} را وارد کنید:")
                return

        # 13 (انتخاب الحاق/جایگزین) → برگرد به آخرین «تعداد سهام» در حلقه
        if step == 13:
            i = data.get("سهامدار_index", 1)
            data.pop(f"سهامدار {i} تعداد", None)
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار {i} را وارد کنید (اعداد فارسی):")
            return

        # 14 (موضوع جدید) → برگرد به دکمه الحاق/جایگزین
        if step == 14:
            data.pop("نوع تغییر موضوع", None)
            data["step"] = 13
            keyboard = [
                [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
            ]
            context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # 15 (وکیل) → برگرد به موضوع جدید
        if step == 15:
            data.pop("موضوع جدید", None)
            data["step"] = 14
            context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
            return

    # --------------------------------------
    # بازگشت: تغییر نام شرکت - مسئولیت محدود
    # --------------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "مسئولیت محدود":
        # 2..6: یک قدم عقب
        if 2 <= step <= 6:
            prev_step = step - 1
            order = ["نام شرکت","شماره ثبت","شناسه ملی","سرمایه","تاریخ","ساعت"]
            key = order[prev_step - 1] if prev_step - 1 < len(order) else None
            if prev_step == 1:
                data.pop("نام شرکت", None)
                data["step"] = 1
                context.bot.send_message(chat_id=chat_id, text=get_label("نام شرکت"))
                return
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                context.bot.send_message(chat_id=chat_id, text=get_label(key))
                return
    
        # 7 ← برگشت به 6 (ساعت)
        if step == 7:
            data.pop("نام جدید شرکت", None)
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text=get_label("ساعت"))
            return
    
        # 8 ← برگشت به 7 (نام جدید شرکت)
        if step == 8:
            data.pop("تعداد شرکا", None)
            data["step"] = 7
            context.bot.send_message(chat_id=chat_id, text=get_label("نام جدید شرکت"))
            return
    
        # حلقه شرکا (9 و 10)
        if step == 9:
            i = data.get("current_partner", 1)
            if i == 1:
                data.pop("تعداد شرکا", None)
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=get_label("تعداد شرکا"))
                return
            prev_i = i - 1
            data["current_partner"] = prev_i
            data.pop(f"سهم الشرکه شریک {prev_i}", None)
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text=get_label("سهم الشرکه شریک", i=prev_i))
            return
    
        if step == 10:
            i = data.get("current_partner", 1)
            data.pop(f"شریک {i}", None)
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=get_label("نام شریک", i=i))
            return
    
        # 11 ← برگشت به «سهم‌الشرکه شریک آخر»
        if step == 11:
            last = data.get("تعداد شرکا", 1)
            data["current_partner"] = last
            data.pop(f"سهم الشرکه شریک {last}", None)
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text=get_label("سهم الشرکه شریک", i=last))
            return
    
        # 1 ← بازگشت به انتخاب نوع شرکت (در صورت نیاز)
        if step == 1:
            data["step"] = 0
            send_company_type_menu(update, context)
            return

    # -------------------------------
    # تغییر آدرس - مسئولیت محدود
    # steps: 1=نام شرکت، 2..9 فیلدهای common، 10=تعداد شرکا، >10 حلقه شرکا (نام/سهم)
    # -------------------------------
    if موضوع == "تغییر آدرس" and نوع_شرکت == "مسئولیت محدود":
        common_fields = ["نام شرکت","شماره ثبت","شناسه ملی","سرمایه","تاریخ","ساعت","آدرس جدید","کد پستی","وکیل"]

        # برگشت داخل بخش فیلدهای common (2..10)
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

        # حلقه شرکا: >10
        if step > 10:
            i = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)

            # اگر منتظر نام شریک i هستیم (پس هنوز کلید سهم‌الشرکه‌اش ثبت نشده)
            if f"شریک {i}" not in data:
                if i == 1:
                    # برگرد به «تعداد شرکا»
                    data.pop("تعداد شرکا", None)
                    data["step"] = 10
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):")
                    return
                else:
                    # برگرد به «سهم‌الشرکه شریک قبلی»
                    prev_i = i - 1
                    data["current_partner"] = prev_i
                    data.pop(f"سهم الشرکه شریک {prev_i}", None)
                    data["step"] = 10 + prev_i  # همچنان در فاز >10
                    context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {prev_i} را به ریال وارد کنید (عدد فارسی):")
                    return

            # اگر منتظر سهم‌الشرکه شریک i هستیم
            if f"سهم الشرکه شریک {i}" not in data:
                data.pop(f"شریک {i}", None)
                data["step"] = 10 + i
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

            # اگر بعد از اتمام کار هستیم
            context.bot.send_message(chat_id=chat_id, text="برای شروع مجدد /start را ارسال کنید.")
            return

    # --------------------------------------
    # تغییر موضوع فعالیت - مسئولیت محدود
    # steps: 1..7 خطی تا «تعداد شرکا»، 8=نام شریک i، 9=سهم‌الشرکه شریک i،
    # 10=انتخاب الحاق/جایگزین (callback)، 11=موضوع جدید، 12=وکیل
    # --------------------------------------
    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "مسئولیت محدود":
        if 2 <= step <= 7:  # فیلدهای خطی تا قبل از ورود شرکا
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

        # 8/9: حلقه شرکا
        if step in (8, 9):
            i = data.get("current_partner", 1)
            if step == 8:
                # منتظر «نام شریک i»
                if i == 1:
                    data.pop("تعداد شرکا", None)
                    data["step"] = 7
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید:")
                    return
                else:
                    # برگرد به «سهم‌الشرکه شریک قبلی»
                    prev_i = i - 1
                    data["current_partner"] = prev_i
                    data.pop(f"سهم الشرکه شریک {prev_i}", None)
                    data["step"] = 9
                    context.bot.send_message(chat_id=chat_id, text=f"سهم الشرکه شریک شماره {prev_i} را وارد کنید (عدد فارسی):")
                    return
            else:  # step == 9 → منتظر «سهم‌الشرکه شریک i»
                data.pop(f"شریک {i}", None)
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

        # 10: دکمه الحاق/جایگزین
        if step == 10:
            i = data.get("تعداد شرکا", 1)
            data["current_partner"] = i
            data.pop(f"سهم الشرکه شریک {i}", None)
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=f"سهم الشرکه شریک شماره {i} را وارد کنید (عدد فارسی):")
            return

        # 11: موضوع جدید
        if step == 11:
            data.pop("نوع تغییر موضوع", None)
            data["step"] = 10
            # دوباره همان دکمه‌های الحاق/جایگزین را بفرست
            keyboard = [
                [InlineKeyboardButton("➕ اضافه می‌گردد", callback_data='الحاق')],
                [InlineKeyboardButton("🔄 جایگزین می‌گردد", callback_data='جایگزین')]
            ]
            context.bot.send_message(chat_id=chat_id, text="❓آیا موضوعات جدید به موضوع قبلی اضافه می‌شوند یا جایگزین آن؟",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # 12: وکیل
        if step == 12:
            data.pop("موضوع جدید", None)
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
            return

    # --------------------------------------
    # نقل و انتقال سهام - سهامی خاص
    # steps: 1..11 خطی
    # 12: فروشنده i (نام/کدملی/تعداد)
    # 13: تعداد خریداران برای فروشنده i
    # 14: خریدار k از فروشنده i (نام/کدملی/آدرس)
    # 15: تعداد سهامداران قبل
    # 16: حلقه سهامداران قبل (نام/تعداد)
    # 17: تعداد سهامداران بعد
    # 18: حلقه سهامداران بعد (نام/تعداد)
    # 19: وکیل
    # --------------------------------------
    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "سهامی خاص":
        linear_map = {
            1: "نام شرکت", 2: "شماره ثبت", 3: "شناسه ملی", 4: "سرمایه",
            5: "تاریخ", 6: "ساعت", 7: "مدیر عامل", 8: "نایب رییس",
            9: "رییس", 10: "منشی", 11: "تعداد فروشندگان"
        }
    
        # برگشت در مسیر خطی 2..11
        if 2 <= step <= 11:
            prev_step = step - 1
            key = linear_map.get(prev_step)
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                context.bot.send_message(chat_id=chat_id, text=get_label(key))
                return
    
        # 12: فروشنده i
        if step == 12:
            i = data.get("فروشنده_index", 1)
            prefix = f"فروشنده {i}"
    
            # اگر منتظر "نام فروشنده i" هستیم
            if f"{prefix} نام" not in data:
                if i == 1:
                    data.pop("تعداد فروشندگان", None)
                    data["step"] = 11
                    context.bot.send_message(chat_id=chat_id, text="تعداد فروشندگان را وارد کنید:")
                    return
                # برگرد به "آدرس آخرین خریدارِ فروشنده قبلی"
                prev_i = i - 1
                total_k = data.get(f"تعداد خریداران {prev_i}", 1)
                data["فروشنده_index"] = prev_i
                data[f"خریدار_index_{prev_i}"] = total_k
                data.pop(f"خریدار {prev_i}-{total_k} آدرس", None)
                data["step"] = 14
                context.bot.send_message(chat_id=chat_id, text=f"آدرس خریدار {total_k} از فروشنده {prev_i} را وارد کنید:")
                return
    
            # اگر منتظر "کدملی فروشنده i" هستیم
            if f"{prefix} کد ملی" not in data:
                data.pop(f"{prefix} نام", None)
                data["step"] = 12
                context.bot.send_message(chat_id=chat_id, text=f"نام فروشنده شماره {i} را وارد کنید:")
                return
    
            # اگر منتظر "تعداد سهام منتقل‌شده فروشنده i" هستیم
            if f"{prefix} تعداد" not in data:
                data.pop(f"{prefix} کد ملی", None)
                data["step"] = 12
                context.bot.send_message(chat_id=chat_id, text=f"کد ملی فروشنده شماره {i} را وارد کنید:")
                return
    
        # 13: تعداد خریداران برای فروشنده i
        if step == 13:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} تعداد", None)
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام منتقل‌شده توسط فروشنده {i} را وارد کنید:")
            return
    
        # 14: خریدار k از فروشنده i
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
    
        # 15: تعداد سهامداران قبل
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
    
        # 16: حلقه سهامداران قبل (نام/تعداد)
        if step == 16:
            i = data.get("سهامدار_قبل_index", 1)
            prefix = f"سهامدار قبل {i}"
    
            # اگر منتظر نام هستیم
            if f"{prefix} نام" not in data:
                if i == 1:
                    data.pop("تعداد سهامداران قبل", None)
                    data["step"] = 15
                    context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران قبل از نقل و انتقال را وارد کنید:")
                    return
                prev_i = i - 1
                data["سهامدار_قبل_index"] = prev_i
                data.pop(f"سهامدار قبل {prev_i} تعداد", None)
                data["step"] = 16
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار قبل شماره {prev_i} را وارد کنید:")
                return
    
            # اگر منتظر تعداد هستیم
            if f"{prefix} تعداد" not in data:
                data.pop(f"{prefix} نام", None)
                data["step"] = 16
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار قبل شماره {i} را وارد کنید:")
                return
    
            # حالت حفاظتی: هر دو مقدار پر است ولی کاربر «بازگشت» زده
            if i > 1:
                prev_i = i - 1
                data["سهامدار_قبل_index"] = prev_i
                data.pop(f"سهامدار قبل {prev_i} تعداد", None)
                data["step"] = 16
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار قبل شماره {prev_i} را وارد کنید:")
                return
            else:
                data.pop("سهامدار قبل 1 نام", None)
                data.pop("سهامدار قبل 1 تعداد", None)
                data["step"] = 16
                context.bot.send_message(chat_id=chat_id, text="نام سهامدار قبل شماره ۱ را وارد کنید:")
                return
    
        # 17: تعداد سهامداران بعد
        # 17: تعداد سهامداران بعد  ← با Back باید به "تعداد" آخرین سهامدارِ قبل برگردد
        if step == 17:
            maxc = data.get("تعداد سهامداران قبل", 1)
            i = data.get("سهامدار_قبل_index", maxc)
            # اگر به هر دلیلی index از max جلوتر است، روی آخرین نفر قفل کن
            if i > maxc:
                i = maxc
                data["سهامدار_قبل_index"] = i
        
            # فقط یک قدم به عقب: "تعداد" آخرین سهامدار را پاک کن و همان را دوباره بپرس
            data.pop(f"سهامدار قبل {i} تعداد", None)
            data["step"] = 16
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار قبل شماره {i} را وارد کنید:")
            return
    
        # 18: حلقه سهامداران بعد (نام/تعداد)
        if step == 18:
            i = data.get("سهامدار_بعد_index", 1)
            prefix = f"سهامدار بعد {i}"
    
            # اگر منتظر نام هستیم
            if f"{prefix} نام" not in data:
                if i == 1:
                    data.pop("تعداد سهامداران بعد", None)
                    data["step"] = 17
                    context.bot.send_message(chat_id=chat_id, text="تعداد سهامداران بعد از نقل و انتقال را وارد کنید:")
                    return
                prev_i = i - 1
                data["سهامدار_بعد_index"] = prev_i
                data.pop(f"سهامدار بعد {prev_i} تعداد", None)
                data["step"] = 18
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار بعد شماره {prev_i} را وارد کنید:")
                return
    
            # اگر منتظر تعداد هستیم
            if f"{prefix} تعداد" not in data:
                data.pop(f"{prefix} نام", None)
                data["step"] = 18
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار بعد شماره {i} را وارد کنید:")
                return
    
            # حالت حفاظتی
            if i > 1:
                prev_i = i - 1
                data["سهامدار_بعد_index"] = prev_i
                data.pop(f"سهامدار بعد {prev_i} تعداد", None)
                data["step"] = 18
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار بعد شماره {prev_i} را وارد کنید:")
                return
            else:
                data.pop("سهامدار بعد 1 نام", None)
                data.pop("سهامدار بعد 1 تعداد", None)
                data["step"] = 18
                context.bot.send_message(chat_id=chat_id, text="نام سهامدار بعد شماره ۱ را وارد کنید:")
                return
    
        # 19: وکیل
        # 19: وکیل  ← با Back باید به "تعداد" آخرین سهامدارِ بعد برگردد
        if step == 19:
            maxc = data.get("تعداد سهامداران بعد", 1)
            i = data.get("سهامدار_بعد_index", maxc)
            if i > maxc:
                i = maxc
                data["سهامدار_بعد_index"] = i
        
            data.pop(f"سهامدار بعد {i} تعداد", None)
            data["step"] = 18
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار بعد شماره {i} را وارد کنید:")
            return

    # --------------------------------------
    # بازگشت: انحلال شرکت - مسئولیت محدود
    # مراحل: 1..6 خطی، 7=تعداد شرکا، 8/9 حلقه شرکا، 10..15 فیلدهای پایانی
    # --------------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "مسئولیت محدود":
        # خطی 2..6 → یک قدم عقب
        if 2 <= step <= 6:
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

        # 7 → برگرد به 6 (ساعت)
        if step == 7:
            data.pop("تعداد شرکا", None)
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text=get_label("ساعت"))
            return

        # 8/9: حلقه شرکا (نام ← سهم)
        if step in (8, 9):
            i = data.get("current_partner", 1)
            if step == 8:
                # منتظر «نام شریک i»
                if i == 1:
                    data.pop("تعداد شرکا", None)
                    data["step"] = 7
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (عدد):")
                    return
                prev_i = i - 1
                data["current_partner"] = prev_i
                data.pop(f"سهم الشرکه شریک {prev_i}", None)
                data["step"] = 9
                context.bot.send_message(chat_id=chat_id, text=f"سهم‌الشرکه شریک شماره {prev_i} را به ریال وارد کنید (اعداد فارسی):")
                return
            else:  # step == 9 → منتظر «سهم‌الشرکه»
                data.pop(f"شریک {i}", None)
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

        # 10: علت انحلال ← برگرد به سهم‌الشرکه آخرین شریک
        if step == 10:
            i = data.get("current_partner", data.get("تعداد شرکا", 1))
            if i and i >= 1 and f"سهم الشرکه شریک {i}" in data:
                data.pop(f"سهم الشرکه شریک {i}", None)
                data["step"] = 9
                context.bot.send_message(chat_id=chat_id, text=f"سهم‌الشرکه شریک شماره {i} را به ریال وارد کنید (اعداد فارسی):")
            else:
                data.pop("تعداد شرکا", None)
                data["step"] = 7
                context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (عدد):")
            return

        # 11..15: یک قدم به عقب در مسیر پایانی
        if step == 11:
            data.pop("علت انحلال", None)
            data["step"] = 10
            context.bot.send_message(chat_id=chat_id, text="علت انحلال را وارد کنید (مثلاً: مشکلات اقتصادی، توافق شرکا و ...):")
            return

        if step == 12:
            data.pop("نام مدیر تصفیه", None)
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text="نام مدیر تصفیه را وارد کنید:")
            return

        if step == 13:
            data.pop("کد ملی مدیر تصفیه", None)
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text="کد ملی مدیر تصفیه را وارد کنید (اعداد فارسی):")
            return

        if step == 14:
            data.pop("مدت مدیر تصفیه", None)
            data["step"] = 13
            context.bot.send_message(chat_id=chat_id, text="مدت مدیر تصفیه (سال) را وارد کنید (اعداد فارسی):")
            return

        if step == 15:
            data.pop("آدرس مدیر تصفیه", None)
            data["step"] = 14
            context.bot.send_message(chat_id=chat_id, text="آدرس مدیر تصفیه و محل تصفیه را وارد کنید:")
            return

    # --------------------------------------
    # بازگشت: نقل و انتقال سهم‌الشرکه - مسئولیت محدود
    # مراحل:
    # 1..6 خطی پایه، 7=تعداد شرکا، 8/9 حلقه شرکا،
    # 10=تعداد فروشندگان، 11..16 خطی فروشنده،
    # 17=تعداد خریداران فروشنده i، 18..23 حلقه خریدار،
    # 24=وکیل
    # --------------------------------------
    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "مسئولیت محدود":
        # خطی پایه: 2..6 ← یک قدم عقب
        if step == 1:
            # برگشت به انتخاب نوع شرکت برای موضوع نقل و انتقال
            data["step"] = 0
            send_company_type_menu(update, context)  # همان تابعی که در پروژه‌ات داری
            return
            
        if 2 <= step <= 6:
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
                # از برچسب‌های آماده استفاده می‌کنیم اگر موجود باشد
                lbl = get_label(key) if key in order else f"{key} را وارد کنید:"
                context.bot.send_message(chat_id=chat_id, text=lbl)
                return

        # 7 ← برگشت به 6 (ساعت)
        if step == 7:
            data.pop("تعداد شرکا", None)
            data["step"] = 6
            context.bot.send_message(chat_id=chat_id, text=get_label("ساعت"))
            return

        # حلقه شرکا (8/9)
        if step in (8, 9):
            i = data.get("current_partner", 1)
            # اگر منتظر «نام شریک i» هستیم
            if step == 8:
                if i == 1:
                    data.pop("تعداد شرکا", None)
                    data["step"] = 7
                    context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید:")
                    return
                # برگرد به «سهم‌الشرکه شریک قبلی»
                prev_i = i - 1
                data["current_partner"] = prev_i
                data.pop(f"سهم الشرکه شریک {prev_i}", None)
                data["step"] = 9
                context.bot.send_message(chat_id=chat_id, text=f"سهم‌الشرکه شریک شماره {prev_i} را به ریال وارد کنید (اعداد فارسی):")
                return
            # اگر منتظر «سهم‌الشرکه شریک i» هستیم
            if step == 9:
                data.pop(f"شریک {i}", None)
                data["step"] = 8
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {i} را وارد کنید:")
                return

        # 10 ← برگرد به «سهم‌الشرکه شریک آخر»
        if step == 10:
            last = data.get("تعداد شرکا", 1)
            data["current_partner"] = last
            data.pop(f"سهم الشرکه شریک {last}", None)
            data["step"] = 9
            context.bot.send_message(chat_id=chat_id, text=f"سهم‌الشرکه شریک شماره {last} را به ریال وارد کنید (اعداد فارسی):")
            return

        # فروشنده (11..16) و تعداد خریداران (17)
        if step == 11:
            i = data.get("فروشنده_index", 1)
            if i == 1:
                data.pop("تعداد فروشندگان", None)
                data["step"] = 10
                context.bot.send_message(chat_id=chat_id, text="تعداد فروشندگان را وارد کنید:")
                return
            # برگشت به آخرین فیلد خریدارِ فروشنده قبلی (سهم منتقل)
            prev_i = i - 1
            total_k = data.get(f"تعداد خریداران {prev_i}", 1)
            data["فروشنده_index"] = prev_i
            data[f"خریدار_index_{prev_i}"] = total_k
            data.pop(f"خریدار {prev_i}-{total_k} سهم منتقل", None)
            data["step"] = 23
            context.bot.send_message(chat_id=chat_id, text=f"میزان سهم‌الشرکه منتقل‌شده به خریدار {total_k} از فروشنده {prev_i} (ریال):")
            return

        if step == 12:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} نام", None)
            data["step"] = 11
            context.bot.send_message(chat_id=chat_id, text=f"نام فروشنده شماره {i} را وارد کنید:")
            return

        if step == 13:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} کد ملی", None)
            data["step"] = 12
            context.bot.send_message(chat_id=chat_id, text=f"کد ملی فروشنده {i} را وارد کنید (اعداد فارسی):")
            return

        if step == 14:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} سهم کل", None)
            data["step"] = 13
            context.bot.send_message(chat_id=chat_id, text=f"کل سهم‌الشرکه فروشنده {i} (ریال):")
            return

        if step == 15:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} سند صلح", None)
            data["step"] = 14
            context.bot.send_message(chat_id=chat_id, text=f"شماره سند صلح فروشنده {i} را وارد کنید:")
            return

        if step == 16:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} تاریخ سند", None)
            data["step"] = 15
            context.bot.send_message(chat_id=chat_id, text=f"تاریخ سند صلح فروشنده {i} را وارد کنید:")
            return

        if step == 17:
            i = data.get("فروشنده_index", 1)
            data.pop(f"فروشنده {i} دفترخانه", None)
            data["step"] = 16
            context.bot.send_message(chat_id=chat_id, text=f"شماره دفترخانه فروشنده {i} را وارد کنید:")
            return

        # حلقه خریداران (18..23)
        if step == 18:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            if k == 1:
                data.pop(f"تعداد خریداران {i}", None)
                data["step"] = 17
                context.bot.send_message(chat_id=chat_id, text=f"تعداد خریداران فروشنده {i} را وارد کنید:")
                return
            # برگرد به «سهم منتقلِ» خریدار قبلی
            prev_k = k - 1
            data[f"خریدار_index_{i}"] = prev_k
            data.pop(f"خریدار {i}-{prev_k} سهم منتقل", None)
            data["step"] = 23
            context.bot.send_message(chat_id=chat_id, text=f"میزان سهم‌الشرکه منتقل‌شده به خریدار {prev_k} از فروشنده {i} (ریال):")
            return

        if step == 19:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            data.pop(f"خریدار {i}-{k} نام", None)
            data["step"] = 18
            context.bot.send_message(chat_id=chat_id, text=f"نام خریدار {k} از فروشنده {i} را وارد کنید:")
            return

        if step == 20:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            data.pop(f"خریدار {i}-{k} پدر", None)
            data["step"] = 19
            context.bot.send_message(chat_id=chat_id, text=f"نام پدر خریدار {k} از فروشنده {i}:")
            return

        if step == 21:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            data.pop(f"خریدار {i}-{k} تولد", None)
            data["step"] = 20
            context.bot.send_message(chat_id=chat_id, text=f"تاریخ تولد خریدار {k} از فروشنده {i}:")
            return

        if step == 22:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            data.pop(f"خریدار {i}-{k} کد ملی", None)
            data["step"] = 21
            context.bot.send_message(chat_id=chat_id, text=f"کد ملی خریدار {k} از فروشنده {i} (اعداد فارسی):")
            return

        if step == 23:
            i = data.get("فروشنده_index", 1)
            k = data.get(f"خریدار_index_{i}", 1)
            data.pop(f"خریدار {i}-{k} آدرس", None)
            data["step"] = 22
            context.bot.send_message(chat_id=chat_id, text=f"آدرس خریدار {k} از فروشنده {i}:")
            return

        # 24 ← برگرد به «سهم منتقلِ» آخرین خریدارِ آخرین فروشنده
        if step == 24:
            i = data.get("فروشنده_index", data.get("تعداد فروشندگان", 1))
            if i > data.get("تعداد فروشندگان", 1):
                i = data.get("تعداد فروشندگان", 1)
            total_k = data.get(f"تعداد خریداران {i}", 1)
            data[f"خریدار_index_{i}"] = total_k
            data.pop(f"خریدار {i}-{total_k} سهم منتقل", None)
            data["step"] = 23
            context.bot.send_message(chat_id=chat_id, text=f"میزان سهم‌الشرکه منتقل‌شده به خریدار {total_k} از فروشنده {i} (ریال):")
            return

    # --------------------------------------
    # بازگشت: انحلال شرکت - سهامی خاص
    # --------------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "سهامی خاص":
        # مراحل خطی تا قبل از حلقه سهامداران
        linear_map = {
            1: "نام شرکت", 2: "شماره ثبت", 3: "شناسه ملی", 4: "سرمایه",
            5: "تاریخ", 6: "ساعت", 7: "مدیر عامل", 8: "نایب رییس",
            9: "رییس", 10: "منشی", 11: "علت انحلال", 12: "نام مدیر تصفیه",
            13: "کد ملی مدیر تصفیه", 14: "مدت مدیر تصفیه", 15: "آدرس مدیر تصفیه",
            16: "تعداد سهامداران حاضر"
        }

        # برگشت در مسیر خطی: برگرد به سؤال قبلی و همان را بپرس
        if 2 <= step <= 16:
            prev_step = step - 1
            key = linear_map.get(prev_step)
            if key:
                data.pop(key, None)
                data["step"] = prev_step
                # اگر key در get_label نیست، متن سؤال را خودمان می‌دهیم
                label = get_label(key) if key in fields else {
                    "علت انحلال": "علت انحلال را وارد کنید (مثلاً: مشکلات اقتصادی):",
                    "نام مدیر تصفیه": "نام مدیر تصفیه را وارد کنید:",
                    "کد ملی مدیر تصفیه": "کد ملی مدیر تصفیه را وارد کنید (اعداد فارسی):",
                    "مدت مدیر تصفیه": "مدت مدیر تصفیه (سال) را وارد کنید (اعداد فارسی):",
                    "آدرس مدیر تصفیه": "آدرس مدیر تصفیه و محل تصفیه را وارد کنید:",
                    "تعداد سهامداران حاضر": "تعداد سهامداران حاضر را وارد کنید (عدد):",
                }.get(key, f"{key} را وارد کنید:")
                context.bot.send_message(chat_id=chat_id, text=label)
                return

        # حلقه سهامداران: step == 17  (نام ← تعداد)
        if step == 17:
            i = data.get("سهامدار_index", 1)
        
            # اگر هنوز نامِ سهامدار i ثبت نشده:
            if f"سهامدار {i} نام" not in data:
                if i == 1:
                    # فقط وقتی روی «نام سهامدار 1» هستیم به مرحله 16 برگرد
                    data.pop("تعداد سهامداران حاضر", None)
                    data["step"] = 16
                    context.bot.send_message(chat_id=chat_id, text=get_label("تعداد سهامداران حاضر"))
                else:
                    # برگرد به تعدادِ سهام سهامدار قبلی
                    prev_i = i - 1
                    data["سهامدار_index"] = prev_i
                    data.pop(f"سهامدار {prev_i} تعداد", None)
                    data["step"] = 17
                    context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار {prev_i} را وارد کنید (اعداد فارسی):")
                return
        
            # اگر نام ثبت شده ولی تعداد نه → برگرد به نام همان i
            if f"سهامدار {i} تعداد" not in data:
                data.pop(f"سهامدار {i} نام", None)
                data["step"] = 17
                context.bot.send_message(chat_id=chat_id, text=f"نام سهامدار {i} را وارد کنید:")
                return
        
            # هر دو مقدارِ i پر است → برو به سهامدار قبلی و تعدادش را بپرس
            if i > 1:
                data.pop(f"سهامدار {i} نام", None)
                data.pop(f"سهامدار {i} تعداد", None)
                data["سهامدار_index"] = i - 1
                data["step"] = 17
                context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار {i-1} را وارد کنید (اعداد فارسی):")
                return
            else:
                # i == 1 → برگرد ابتدای حلقه
                data.pop("سهامدار 1 نام", None)
                data.pop("سهامدار 1 تعداد", None)
                data["step"] = 17
                context.bot.send_message(chat_id=chat_id, text="نام سهامدار ۱ را وارد کنید:")
                return
        
        # وکیل: step == 18 → برگرد به آخرین سهامدار (تعداد)
        if step == 18:
            i = data.get("سهامدار_index", 1)
            data.pop("وکیل", None)
            data.pop(f"سهامدار {i} تعداد", None)  # 🔧 اضافه شد
            data["step"] = 17
            context.bot.send_message(chat_id=chat_id, text=f"تعداد سهام سهامدار {i} را وارد کنید (اعداد فارسی):")
            return

            
    # -------------------------------
    # حالت عمومی پیش‌فرض (مسیرهای ساده)
    # -------------------------------
    if step == 0:
        data.pop("موضوع صورتجلسه", None)
        data.pop("نوع شرکت", None)
        context.bot.send_message(chat_id=chat_id, text="به انتخاب موضوع برگشتید.")
        send_topic_menu(chat_id, context)
        return
    
    # فقط اگر step در محدوده‌ی فرم ساده است
    if 2 <= step < len(fields):
        prev_step = step - 1
        key = fields[prev_step]
        data.pop(key, None)
        data["step"] = prev_step
        context.bot.send_message(chat_id=chat_id, text=get_label(key))
        return
    
    # در غیر این‌صورت، هیچ برگشت عمومی نزن؛ مسیرهای تخصصی بالاتر کار را انجام داده‌اند
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
        return

    if user_data[chat_id].get("step") == 0:
        user_data[chat_id]["نوع شرکت"] = query.data
        # اگر موضوع = نقل و انتقال سهام است
        if user_data[chat_id]["موضوع صورتجلسه"] == "نقل و انتقال سهام":
            if query.data == "مسئولیت محدود":
                # 👇 اول اطلاعیه ماده ۱۰۳، بعد سوال نام شرکت
                context.bot.send_message(chat_id=chat_id, text=get_label("اطلاعیه_ماده103", سند="سند صلح"))

                user_data[chat_id]["step"] = 1
                context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
                return
            else:
                # سهامی خاص یا سایر انواع → بدون اطلاعیه
                user_data[chat_id]["step"] = 1
                context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
                return

        # شروع: تغییر نام شرکت - مسئولیت محدود
        if user_data[chat_id].get("موضوع صورتجلسه") == "تغییر نام شرکت" and query.data == "مسئولیت محدود":
            user_data[chat_id]["step"] = 1
            context.bot.send_message(chat_id=chat_id, text=get_label("نام شرکت"))
            return

        # شروع: تغییر نام شرکت - سهامی خاص
        if user_data[chat_id].get("موضوع صورتجلسه") == "تغییر نام شرکت" and query.data == "سهامی خاص":
            user_data[chat_id]["step"] = 1
            context.bot.send_message(chat_id=chat_id, text=get_label("نام شرکت"))
            return
    
        # سایر موضوع‌ها
        user_data[chat_id]["step"] = 1
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
        return

    if data.get("موضوع صورتجلسه") == "تغییر موضوع فعالیت" and data.get("step") in (10, 13):
        انتخاب = query.data
        query.answer()

        if انتخاب == "الحاق":
            data["نوع تغییر موضوع"] = "الحاق"
        elif انتخاب == "جایگزین":
            data["نوع تغییر موضوع"] = "جایگزین"
        else:
            context.bot.send_message(chat_id=chat_id, text="❗️انتخاب نامعتبر بود.")
            return

        # اگر قبلاً در مسئولیت محدود بود step=10 → بعدش 11
        # اگر در سهامی خاص هستیم step=13 → بعدش 14
        if data.get("step") == 10:
            data["step"] = 11
        else:
            data["step"] = 14

        context.bot.send_message(chat_id=chat_id, text="موضوع جدید فعالیت شرکت را وارد کنید:")
        return


def send_summary(chat_id, context):
    data = user_data[chat_id]
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

        # ✅ خروجی: تغییر موضوع فعالیت – سهامی خاص
    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "سهامی خاص":
        # خطوط عمل بر اساس الحاق/جایگزین
        action_line = (
            "صورتجلسه مجمع عمومی فوق العاده شرکت "
            f"{data['نام شرکت']} ){نوع_شرکت} (ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} "
            "با حضور کلیه سهامداران در محل قانونی شرکت تشکیل و نسبت به الحاق مواردی به موضوع شرکت اتخاذ تصمیم شد."
            if data.get("نوع تغییر موضوع") == "الحاق"
            else
            "صورتجلسه مجمع عمومی فوق العاده شرکت "
            f"{data['نام شرکت']} ){نوع_شرکت} (ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} "
            "با حضور کلیه سهامداران در محل قانونی شرکت تشکیل و نسبت به تغییر موضوع شرکت اتخاذ تصمیم شد."
        )

        subject_intro = (
            "ب: مواردی به شرح ذیل به موضوع شرکت الحاق شد:"
            if data.get("نوع تغییر موضوع") == "الحاق"
            else
            "ب: موضوع شرکت به شرح ذیل تغییر یافت:"
        )

        # جدول سهامداران حاضر
        rows = ""
        for i in range(1, data.get("تعداد سهامداران", 0) + 1):
            rows += f"{i}\n\t{data.get(f'سهامدار {i} نام', '')}\t{data.get(f'سهامدار {i} تعداد', '')}\t\n"

        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ){نوع_شرکت}(
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

{action_line}
الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 

ـ  {data['مدیر عامل']}                                   به سمت رئیس جلسه 
ـ  {data['نایب رییس']}                                  به سمت ناظر 1 جلسه 
ـ  {data['رییس']}                                        به سمت ناظر 2 جلسه 
ـ  {data['منشی']}                                        به سمت منشی جلسه انتخاب شدند

{subject_intro}
{data['موضوع جدید']} 
و ماده مربوطه اساسنامه به شرح فوق اصلاح می گردد. 
ج: مجمع به {data['وکیل']} از سهامداران شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکت ها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.

امضاء اعضاء هیات رئیسه: 
رئیس جلسه :  {data['مدیر عامل']}                                   ناظر1 جلسه : {data['نایب رییس']}                               


ناظر2جلسه : {data['رییس']}                                       منشی جلسه: {data['منشی']}





صورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}
{data['نام شرکت']}
ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران
{rows}
"""

        context.bot.send_message(chat_id=chat_id, text=text)

        # فایل Word
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه تغییر موضوع سهامی خاص.docx")
        os.remove(file_path)
        return

    # کد صورتجلسه تغییر آدرس مسئولیت محدود
    
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

به {data['وکیل']} احدی از شرکاء وکالت داده می شود تا ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و امضاء ذیل دفتر ثبت اقدام نماید.

امضاء شرکا : 

"""
        # فاصله بین اسامی امضاءها به سبک نمونه
        signers = ""
        for i in range(1, count + 1):
            signers += f"{data.get(f'شریک {i}', '')}     "
        text += signers
        context.bot.send_message(chat_id=chat_id, text=text)
        
        # ✅ ساخت فایل Word و ارسال
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
    
        os.remove(file_path)  # ← حذف فایل پس از ارسال (اختیاری)
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

        # تبدیل اعداد فارسی به انگلیسی
        def fa_to_en_number(text):
            table = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
            return text.translate(table)

        from collections import defaultdict
import re
from telegram.ext import Dispatcher

DOCX_IMPORTED = False
def _lazy_import_docx():
    global DOCX_IMPORTED, Document, Pt, qn
    if DOCX_IMPORTED:
        return
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
    DOCX_IMPORTED = True


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
    
    
        # جدول سهامداران قبل
        text += f"\n\nصورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}\n{data['نام شرکت']} قبل از نقل و انتقال سهام\n"
        text += "ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران\n"
        for i in range(1, data["تعداد سهامداران قبل"] + 1):
            text += f"{i}\t{data[f'سهامدار قبل {i} نام']}\t{data[f'سهامدار قبل {i} تعداد']}\t\n"

        # جدول سهامداران بعد
        text += f"\nصورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}\n{data['نام شرکت']} بعد از نقل و انتقال سهام\n"
        text += "ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران\n"
        for i in range(1, data["تعداد سهامداران بعد"] + 1):
            text += f"{i}\t{data[f'سهامدار بعد {i} نام']}\t{data[f'سهامدار بعد {i} تعداد']}\t\n"

        # ارسال متن و فایل Word
        context.bot.send_message(chat_id=chat_id, text=text)

        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه نقل و انتقال.docx")

        os.remove(file_path)
        return

    # کد صورتجلسه تغییر آدرس سهامی خاص
    
    if موضوع == "تغییر آدرس" and نوع_شرکت == "سهامی خاص":
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
        context.bot.send_message(chat_id=chat_id, text=text)

        # ✅ ساخت فایل Word و ارسال
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
    
        os.remove(file_path)  # ← حذف فایل پس از ارسال (اختیاری)
        return

    if موضوع == "تغییر موضوع فعالیت" and نوع_شرکت == "مسئولیت محدود":
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

        # فایل Word
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه تغییر موضوع فعالیت.docx")
        os.remove(file_path)
        return

    # -------------------------------
    # خروجی: تغییر نام شرکت - سهامی خاص
    # -------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "سهامی خاص":
        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت})
    شماره ثبت شرکت :     {data['شماره ثبت']}
    شناسه ملی :     {data['شناسه ملی']}
    سرمایه ثبت شده : {data['سرمایه']} ریال
    
    صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل و نسبت به تغییر نام شرکت اتخاذ تصمیم شد: 
    الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 
    
    ـ  {data['مدیر عامل']}                                   به سمت رئیس جلسه 
    ـ  {data['نایب رییس']}                                  به سمت ناظر 1 جلسه 
    ـ  {data['رییس']}                                        به سمت ناظر 2 جلسه 
    ـ  {data['منشی']}                                        به سمت منشی جلسه انتخاب شدند
    
    ب: پس از شور و بررسی مقرر گردید نام شرکت از {data['نام شرکت']} به {data['نام جدید شرکت']} تغییر یابد در نتیجه ماده مربوطه اساسنامه بشرح مذکور اصلاح می گردد.
    
    ج: مجمع به {data['وکیل']} احدی از سهامداران یا وکیل رسمی شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکت ها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.
    
    امضاء اعضاء هیات رئیسه: 
    رئیس جلسه :  {data['مدیر عامل']}                                   ناظر1 جلسه : {data['نایب رییس']}                               
    
    
    ناظر2جلسه : {data['رییس']}                                       منشی جلسه: {data['منشی']}
    """
    
        context.bot.send_message(chat_id=chat_id, text=text)
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه تغییر نام شرکت سهامی خاص.docx")
        os.remove(file_path)
        return

    # -------------------------------
    # خروجی: تغییر نام شرکت - مسئولیت محدود
    # -------------------------------
    if موضوع == "تغییر نام شرکت" and نوع_شرکت == "مسئولیت محدود":
        count = data.get("تعداد شرکا", 0)
    
        # جدول شرکا
        partners_lines = ""
        for i in range(1, count + 1):
            nm = data.get(f"شریک {i}", "")
            sh = data.get(f"سهم الشرکه شریک {i}", "")
            partners_lines += f"{nm}                                              {sh} ریال\n"
    
        # امضاها: هر دو نام در یک خط بعدی خط جدید
        signer_lines = ""
        for i in range(1, count + 1):
            signer_lines += data.get(f"شریک {i}", "")
            if i % 2 == 1 and i != count:
                signer_lines += "\t"
            else:
                signer_lines += "\n"
    
        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت})
    شماره ثبت شرکت :     {data['شماره ثبت']}
    شناسه ملی :     {data['شناسه ملی']}
    سرمایه ثبت شده : {data['سرمایه']} ریال
    
    صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و نسبت به تغییر نام شرکت اتخاذ تصمیم شد: 
    
    اسامی شرکا                                                        میزان سهم الشرکه
    {partners_lines}
    پس از شور و بررسی مقرر گردید نام شرکت از {data['نام شرکت']} به {data['نام جدید شرکت']} تغییر یابد در نتیجه ماده مربوطه اساسنامه بشرح مذکور اصلاح می گردد.
    
    به {data['وکیل']} احدی از شرکاء یا وکیل رسمی شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکت ها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.
    
    امضاء شرکاء: 
    
    {signer_lines}"""
    
        context.bot.send_message(chat_id=chat_id, text=text)
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه تغییر نام شرکت مسئولیت محدود.docx")
        os.remove(file_path)
        return

    # -------------------------------
    # خروجی: انحلال شرکت - مسئولیت محدود
    # -------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "مسئولیت محدود":
        # ساخت لیست شرکا
        partners_lines = ""
        count = data.get("تعداد شرکا", 0)
        for i in range(1, count + 1):
            name = data.get(f"شریک {i}", "")
            share = data.get(f"سهم الشرکه شریک {i}", "")
            partners_lines += f"{name}                                              {share} ریال\n"

        # امضاها: هر دو نام در یک خط، بعدی خط بعد (برای خوانایی)
        signer_lines = ""
        for i in range(1, count + 1):
            signer_lines += data.get(f"شریک {i}", "")
            if i % 2 == 1 and i != count:
                signer_lines += "\t"
            else:
                signer_lines += "\n"

        text = f"""صورتجلسه انحلال شرکت {data['نام شرکت']} ({نوع_شرکت})
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و تصمیمات ذیل اتخاذ گردید.

اسامی شرکا                                                        میزان سهم الشرکه
{partners_lines}
دستور جلسه، اتخاذ تصمیم در خصوص انحلال شرکت {data['نام شرکت']} ){نوع_شرکت}( پس از بحث و بررسی شرکت بعلت {data['علت انحلال']} منحل گردید و آقای {data['نام مدیر تصفیه']} به شماره ملی {data['کد ملی مدیر تصفیه']} به سمت مدیر تصفیه برای مدت {data['مدت مدیر تصفیه']} سال انتخاب شد. آدرس مدیر تصفیه و محل تصفیه {data['آدرس مدیر تصفیه']} می باشد.
مدیر تصفیه اقرار به دریافت کلیه اموال دارایی ها و دفاتر و اوراق و اسناد مربوط به شرکت را نمود.

به {data['وکیل']} از شرکاء یا وکیل رسمی شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکت ها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.

امضاء شرکاء: 

{signer_lines}"""

        # ارسال متن و فایل Word
        context.bot.send_message(chat_id=chat_id, text=text)
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه انحلال مسئولیت محدود.docx")
        os.remove(file_path)
        return

    # -------------------------------
    # خروجی: نقل و انتقال سهم الشرکه - مسئولیت محدود
    # -------------------------------
    if موضوع == "نقل و انتقال سهام" and نوع_شرکت == "مسئولیت محدود":
        # جدول شرکا (بالای متن)
        partners_lines = ""
        count = data.get("تعداد شرکا", 0)
        for i in range(1, count + 1):
            name = data.get(f"شریک {i}", "")
            share = data.get(f"سهم الشرکه شریک {i}", "")
            partners_lines += f"{name}                                              {share} ریال\n"

        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت})
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ({نوع_شرکت}) ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و نسبت به نقل و انتقال سهم الشرکه بشرح ذیل اتخاذ تصمیم شد:

اسامی شرکا                                                        میزان سهم الشرکه
{partners_lines}
"""

        # پاراگراف‌های واگذاری برای هر فروشنده
        for i in range(1, data.get("تعداد فروشندگان", 0) + 1):
            seller_name = data.get(f"فروشنده {i} نام", "")
            seller_nid = data.get(f"فروشنده {i} کد ملی", "")
            seller_total = data.get(f"فروشنده {i} سهم کل", "")
            senad_no = data.get(f"فروشنده {i} سند صلح", "")
            senad_date = data.get(f"فروشنده {i} تاریخ سند", "")
            daftar_no = data.get(f"فروشنده {i} دفترخانه", "")

            sentence = (
                f"پس از مذاکره مقرر شد که {seller_name} به شماره ملی {seller_nid} "
                f"که دارای {seller_total} ریال سهم الشرکه می باشد "
                f"با رعایت مفاد ماده 103 قانون تجارت و بموجب سند صلح به شماره {senad_no} "
                f"مورخ {senad_date} صادره از دفتراسناد رسمی {daftar_no} "
            )

            # خریداران مرتبط با این فروشنده
            total_transferred = 0
            buyers_cnt = data.get(f"تعداد خریداران {i}", 0)
            first = True
            for k in range(1, buyers_cnt + 1):
                b_name = data.get(f"خریدار {i}-{k} نام", "")
                b_father = data.get(f"خریدار {i}-{k} پدر", "")
                b_birth = data.get(f"خریدار {i}-{k} تولد", "")
                b_nid = data.get(f"خریدار {i}-{k} کد ملی", "")
                b_addr = data.get(f"خریدار {i}-{k} آدرس", "")
                b_share = data.get(f"خریدار {i}-{k} سهم منتقل", "")

                # جمع کل منتقل‌شده برای تعیین خروج/عدم‌خروج فروشنده
                try:
                    total_transferred += int(fa_to_en_number(b_share))
                except Exception:
                    pass

                prefix = "معادل" if first else "و همچنین معادل"
                sentence += (
                    f"{prefix} {b_share} ریال سهم الشرکه خود را به {b_name} "
                    f"فرزند {b_father} متولد {b_birth} "
                    f"به شماره ملی {b_nid} آدرس محل سکونت {b_addr} منتقل "
                )
                first = False

            # اگر به اندازه کل سهم‌الشرکه‌اش منتقل کرده باشد → خروج از شرکت
            try:
                seller_total_int = int(fa_to_en_number(seller_total))
            except Exception:
                seller_total_int = None

            if seller_total_int is not None and seller_total_int == total_transferred:
                sentence += "و از شرکت خارج  شد و دیگر هیچ گونه حق و سمتی در شرکت ندارد."
            else:
                sentence += "نمود."
                
            text += sentence + "\n"

        text += "\nاین نقل و انتقال سهم الشرکه مورد موافقت کلیه شرکاء با رعایت مفاد ماده 102 قانون تجارت قرار گرفت.\n\n"
        text += f"به {data['وکیل']} احدی از شرکاء یا وکیل رسمی شرکت وکالت داده شد که ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفتر ثبت اقدام نماید. \n\n"

        # جدول امضاء پایانی
        text += "    نام شرکاء                                        میزان سهم الشرکه                                     امضاء\n"
        for i in range(1, count + 1):
            text += f" {data.get(f'شریک {i}', '')}                                   {data.get(f'سهم الشرکه شریک {i}', '')} ریال\n"

        # ارسال متن و فایل Word
        context.bot.send_message(chat_id=chat_id, text=text)
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه نقل و انتقال سهم‌الشرکه مسئولیت محدود.docx")
        os.remove(file_path)
        return

    
    # -------------------------------
    # خروجی: انحلال شرکت - سهامی خاص
    # -------------------------------
    if موضوع == "انحلال شرکت" and نوع_شرکت == "سهامی خاص":
        # ساخت جدول سهامداران حاضر
        count = data.get("تعداد سهامداران حاضر", 0)
        rows = ""
        for i in range(1, count + 1):
            rows += f"{i}\n\t{data.get(f'سهامدار {i} نام','')}\t{data.get(f'سهامدار {i} تعداد','')}\t\n"

        # متن اصلی مطابق قالب شما (با اصلاح برچسب‌های متنیِ منطقی)
        text = f"""صورتجلسه انحلال شرکت {data['نام شرکت']} ){نوع_شرکت}(
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} ){نوع_شرکت}( ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.
الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت: 

ـ  {data['مدیر عامل']}                                   به سمت رئیس جلسه 
ـ  {data['نایب رییس']}                                  به سمت ناظر 1 جلسه 
ـ  {data['رییس']}                                        به سمت ناظر 2 جلسه 
ـ  {data['منشی']}                                       به سمت منشی جلسه انتخاب شدند

ب: دستور جلسه، اتخاذ تصمیم در خصوص انحلال شرکت {data['نام شرکت']} ){نوع_شرکت}( پس از بحث و بررسی شرکت بعلت {data['علت انحلال']} منحل گردید و  {data['نام مدیر تصفیه']} به شماره ملی {data['کد ملی مدیر تصفیه']} به سمت مدیر تصفیه برای مدت {data['مدت مدیر تصفیه']} سال انتخاب شد. آدرس مدیر تصفیه و محل تصفیه {data['آدرس مدیر تصفیه']} می باشد.
مدیر تصفیه اقرار به دریافت کلیه اموال دارایی ها و دفاتر و اوراق و اسناد مربوط به شرکت را نمود.

ج: مجمع به {data['وکیل']} از سهامداران یا وکیل رسمی شرکت وکالت داده می شود که ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و پرداخت حق الثبت و امضاء ذیل دفاتر ثبت اقدام نماید. 
امضاء اعضاء هیات رئیسه: 

رئیس جلسه :  {data['مدیر عامل']}                                   ناظر1 جلسه : {data['نایب رییس']}                               


ناظر2جلسه : {data['رییس']}                                       منشی جلسه: {data['منشی']}





صورت سهامداران حاضر در مجمع عمومی (فوق العاده) مورخه {data['تاریخ']}
{data['نام شرکت']}
ردیف\tنام و نام خانوادگی\tتعداد سهام\tامضا سهامداران
{rows}"""

        # ارسال متن
        context.bot.send_message(chat_id=chat_id, text=text)

        # فایل Word
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه انحلال.docx")
        os.remove(file_path)
        return

    else:
        # اگر هیچ‌کدام از حالت‌های بالا نبود:
        context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات با موفقیت دریافت شد.\nدر حال حاضر صورتجلسه‌ای برای این ترکیب تعریف نشده است.")

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'
# updater = Updater(...)  # disabled for webhook mode
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)
dispatcher.add_handler(CommandHandler("ai", cmd_ai))
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(button_handler))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


@app.route('/_health', methods=['GET'])
def health():
    return 'ok', 200


def remember_last_question(context, label: str):
    try:
        context.user_data["last_question"] = label
    except Exception:
        pass
