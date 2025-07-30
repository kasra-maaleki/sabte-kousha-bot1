import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from flask import Flask, request
import os

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

fields = [
    "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": 0}
    update.message.reply_text("به خدمات ثبتی کوشا خوش آمدید 🙏🏼\nدر عرض چند دقیقه صورتجلسه خود را بسیار دقیق دریافت خواهید کرد")
    context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if chat_id not in user_data:
        user_data[chat_id] = {"step": 0}

    data = user_data[chat_id]
    step = data.get("step", 0)

    if step == 0:
        data["نام شرکت"] = text
        data["step"] = 1
        keyboard = [
            [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
            [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("نوع شرکت را انتخاب کنید:", reply_markup=reply_markup)
    elif 2 <= step < len(fields) + 2:
        field = fields[step - 2]
        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields) + 2:
            next_field = fields[data["step"] - 2]
            prompt = get_prompt(next_field)
            context.bot.send_message(chat_id=chat_id, text=prompt)
        else:
            send_summary(chat_id, context)
    else:
        context.bot.send_message(chat_id=chat_id, text="لطفاً منتظر بمانید...")

def get_prompt(field_name):
    prompts = {
        "شماره ثبت": "شماره ثبت شرکت را وارد کنید:",
        "شناسه ملی": "شناسه ملی شرکت را وارد کنید:",
        "سرمایه": "سرمایه اولیه شرکت را به ریال وارد کنید:",
        "تاریخ": "تاریخ صورتجلسه را وارد کنید (بهتر است تاریخ روز باشد چون برای ثبت صورتجلسات در اداره فقط یک ماه فرصت دارید):",
        "ساعت": "ساعت برگزاری جلسه را وارد کنید:",
        "مدیر عامل": "مدیر عامل را وارد کنید (مثلا: آقای ... یا خانم ...):",
        "نایب رییس": "نایب رئیس جلسه را وارد کنید:",
        "رییس": "ناظر دوم جلسه را وارد کنید:",
        "منشی": "منشی جلسه را وارد کنید:",
        "آدرس جدید": "آدرس جدید شرکت را وارد کنید:",
        "کد پستی": "کد پستی آدرس جدید را وارد کنید:",
        "وکیل": "وکیل را وارد کنید (منظور شخصی هست که از طرف شما برای ثبت صورتجلسات و امضا دفاتر ثبتی انتخاب می‌شود):"
    }
    return prompts.get(field_name, f"{field_name} را وارد کنید:")

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()

    user_data[chat_id]["نوع شرکت"] = query.data
    user_data[chat_id]["step"] = 2

    next_field = fields[0]
    prompt = get_prompt(next_field)
    context.bot.send_message(chat_id=chat_id, text=prompt)

def send_summary(chat_id, context):
    data = user_data[chat_id]
    text = f"""📄 صورتجلسه مجمع عمومی فوق‌العاده شرکت {data['نام شرکت']} ({data['نوع شرکت']})

شماره ثبت: {data['شماره ثبت']}
شناسه ملی: {data['شناسه ملی']}
سرمایه ثبت شده: {data['سرمایه']} ریال

✅ جلسه در تاریخ {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت برگزار گردید و تصمیمات زیر اتخاذ شد:

۱. در اجرای ماده ۱۰۱ لایحه اصلاحی قانون تجارت:
- آقای/خانم {data['مدیر عامل']} به عنوان رئیس جلسه
- آقای/خانم {data['نایب رییس']} به عنوان ناظر اول
- آقای/خانم {data['رییس']} به عنوان ناظر دوم
- آقای/خانم {data['منشی']} به عنوان منشی جلسه انتخاب شدند.

۲. در خصوص تغییر محل شرکت، مجمع با انتقال شرکت به آدرس جدید:
{data['آدرس جدید']} (کدپستی: {data['کد پستی']}) موافقت نمود.

۳. به آقای/خانم {data['وکیل']} وکالت داده شد که ضمن مراجعه به اداره ثبت شرکت‌ها نسبت به ثبت صورتجلسه، پرداخت حق‌الثبت و امضاء دفاتر اقدام نماید.

🖋 امضاء اعضای هیئت رئیسه:
رئیس جلسه: {data['مدیر عامل']}  
ناظر اول: {data['نایب رییس']}  
ناظر دوم: {data['رییس']}  
منشی جلسه: {data['منشی']}
"""
    context.bot.send_message(chat_id=chat_id, text=text)

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
