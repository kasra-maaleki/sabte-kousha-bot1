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
    "نام شرکت", "نوع شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_data[chat_id] = {"step": 0}
    update.message.reply_text("نام شرکت را وارد کنید:")

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text
    if chat_id not in user_data:
        user_data[chat_id] = {"step": 0}

    data = user_data[chat_id]
    step = data.get("step", 0)

    if step == 0:
        data["نام شرکت"] = text
        data["step"] = 1
        # ارسال گزینه نوع شرکت
        keyboard = [
            [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
            [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("نوع شرکت چیست؟", reply_markup=reply_markup)
    elif 2 <= step < len(fields):
        field = fields[step]
        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields):
            next_field = fields[data["step"]]
            context.bot.send_message(chat_id=chat_id, text=f"{next_field} را وارد کنید:")
        else:
            send_summary(chat_id, context)
    else:
        context.bot.send_message(chat_id=chat_id, text="لطفاً منتظر بمانید...")

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()

    user_data[chat_id]["نوع شرکت"] = query.data
    user_data[chat_id]["step"] = 2

    next_field = fields[2]
    context.bot.send_message(chat_id=chat_id, text=f"{next_field} را وارد کنید:")

def send_summary(chat_id, context):
    data = user_data[chat_id]
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
