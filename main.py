import os
import re
import telegram
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"
bot = telegram.Bot(token=TOKEN)

user_data = {}

fields = [
    "company_name", "company_type", "meeting_type", "registration_number",
    "national_id", "capital", "meeting_date", "meeting_time",
    "members", "ceo", "chairperson", "vice_chair", "secretary",
    "new_address", "postal_code", "lawyer"
]

labels = {
    "company_name": "🏢 نام شرکت را وارد کنید:",
    "company_type": "🏷️ نوع شرکت را انتخاب کنید:",
    "meeting_type": "📄 نوع صورتجلسه درخواستی را انتخاب کنید:",
    "registration_number": "🆔 شماره ثبت شرکت را وارد کنید:",
    "national_id": "🧾 شناسه ملی شرکت را وارد کنید:",
    "capital": "💰 سرمایه اولیه شرکت را به ریال وارد کنید:",
    "meeting_date": "📅 تاریخ صورتجلسه را وارد کنید (مثال: 1403/05/30):",
    "meeting_time": "🕒 ساعت برگزاری جلسه را وارد کنید:",
    "members": "👥 اسامی اعضای هیئت مدیره را وارد کنید:",
    "ceo": "👨‍💼 مدیر عامل را وارد کنید ( مثلا : آقای ... خانم ... ):",
    "chairperson": "🧑‍⚖️ رئیس جلسه را وارد کنید:",
    "vice_chair": "👤 نایب رئیس جلسه را وارد کنید:",
    "secretary": "📝 منشی جلسه را وارد کنید:",
    "new_address": "📍 آدرس جدید شرکت را وارد کنید:",
    "postal_code": "🔢 کد پستی آدرس جدید را وارد کنید:",
    "lawyer": "📚 وکیل را وارد کنید ( منظور شخصی هست که از طرف شما برای ثبت صورتجلسات و امضا دفاتر ثبتی انتخاب میشود ):"
}

keyboard_options = {
    "company_type": [["(سهامی خاص)"], ["(مسئولیت محدود)"]],
    "meeting_type": [["مجمع عمومی فوق العاده"], ["مجمع عمومی عادی بطور فوق العاده"], ["هیئت مدیره"]]
}

def get_label(field):
    return labels.get(field, "لطفاً مقدار را وارد کنید:")

def get_next_field(chat_id):
    data = user_data.get(chat_id, {})
    for field in fields:
        if field not in data:
            return field
    return None

def is_persian_number(text):
    return all('۰' <= ch <= '۹' for ch in text if ch.isdigit())

def is_valid_date_format(text):
    return text.count("/") == 2

def start(update, context):
    chat_id = update.message.chat_id
    user_data[chat_id] = {}
    context.bot.send_message(chat_id=chat_id, text="به خدمات ثبتی کوشا خوش آمدید 🙏🏼\nدر عرض چند دقیقه صورتجلسه خود را بسیار دقیق دریافت خواهید کرد.")
    context.bot.send_message(chat_id=chat_id, text=get_label("company_name"))

def handle_message(update, context):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    data = user_data.get(chat_id, {})

    field = get_next_field(chat_id)
    if not field:
        context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات قبلاً ثبت شده است.")
        return

    # بررسی صحت عدد فارسی برای فیلدهای خاص
    if field in ["capital", "registration_number", "national_id", "postal_code"]:
        if not is_persian_number(text):
            context.bot.send_message(chat_id=chat_id, text="⚠️ لطفاً فقط از اعداد فارسی استفاده کنید.")
            return

    if field == "meeting_date":
        if not is_valid_date_format(text):
            context.bot.send_message(chat_id=chat_id, text="📅 فرمت تاریخ اشتباه است. لطفاً مانند مثال وارد کنید: ۱۴۰۳/۰۵/۳۰")
            return

    data[field] = text
    user_data[chat_id] = data

    next_field = get_next_field(chat_id)
    if next_field:
        if next_field in keyboard_options:
            reply_markup = telegram.ReplyKeyboardMarkup(
                keyboard_options[next_field], one_time_keyboard=True, resize_keyboard=True
            )
            context.bot.send_message(chat_id=chat_id, text=get_label(next_field), reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=chat_id, text=get_label(next_field))
    else:
        context.bot.send_message(chat_id=chat_id, text="⏳ لطفاً منتظر بمانید، صورتجلسه در حال آماده‌سازی است...")
        send_final_text(chat_id, context)

def send_final_text(chat_id, context):
    d = user_data[chat_id]
    text = f"""
صورتجلسه مجمع عمومی فوق‌العاده شرکت {d['company_name']} {d['company_type']}

به شماره ثبت {d['registration_number']} و شناسه ملی {d['national_id']}

در تاریخ {d['meeting_date']} ساعت {d['meeting_time']} مجمع عمومی فوق‌العاده با حضور کلیه شرکاء در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید:

۱. نظر به تغییر محل شرکت، آدرس جدید به شرح ذیل تعیین گردید:

{d['new_address']} - کدپستی: {d['postal_code']}

۲. به خانم/آقای {d['lawyer']} وکالت داده شد تا ضمن مراجعه به اداره ثبت شرکت‌ها، نسبت به ثبت صورتجلسه و امضای دفاتر مربوطه اقدام نماید.

اعضای جلسه:
مدیر عامل: {d['ceo']}
رئیس جلسه: {d['chairperson']}
نایب رئیس: {d['vice_chair']}
منشی جلسه: {d['secretary']}
اعضای هیئت مدیره: {d['members']}

پایان جلسه.
"""
    context.bot.send_message(chat_id=chat_id, text=text)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
