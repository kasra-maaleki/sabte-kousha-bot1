import os
from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters, Dispatcher

TOKEN = os.environ.get("BOT_TOKEN", "توکن_ربات_تو_اینجا")
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

@app.route(f"/webhook", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

def start(update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    user_data[user_id] = {}
    context.bot.send_message(chat_id=user_id, text="👋 لطفاً نام شرکت را وارد کنید:")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    text = update.message.text

    if 'نام شرکت' not in user_data[user_id]:
        user_data[user_id]['نام شرکت'] = text
        # گزینه‌های نوع شرکت
        keyboard = [
            [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
            [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=user_id, text="نوع شرکت چیست؟", reply_markup=reply_markup)
    elif 'شماره ثبت' not in user_data[user_id]:
        user_data[user_id]['شماره ثبت'] = text
        context.bot.send_message(chat_id=user_id, text="شناسه ملی شرکت را وارد کنید:")
    elif 'شناسه ملی' not in user_data[user_id]:
        user_data[user_id]['شناسه ملی'] = text
        context.bot.send_message(chat_id=user_id, text="میزان سرمایه ثبت شده (به ریال) را وارد کنید:")
    elif 'سرمایه' not in user_data[user_id]:
        user_data[user_id]['سرمایه'] = text
        context.bot.send_message(chat_id=user_id, text="تاریخ جلسه را وارد کنید (مثال: 1403/05/01):")
    elif 'تاریخ' not in user_data[user_id]:
        user_data[user_id]['تاریخ'] = text
        context.bot.send_message(chat_id=user_id, text="ساعت جلسه را وارد کنید (مثال: 14:00):")
    elif 'ساعت' not in user_data[user_id]:
        user_data[user_id]['ساعت'] = text
        context.bot.send_message(chat_id=user_id, text="نام مدیرعامل (رئیس جلسه) را وارد کنید:")
    elif 'مدیر عامل' not in user_data[user_id]:
        user_data[user_id]['مدیر عامل'] = text
        context.bot.send_message(chat_id=user_id, text="نام نایب رئیس را وارد کنید:")
    elif 'نایب رییس' not in user_data[user_id]:
        user_data[user_id]['نایب رییس'] = text
        context.bot.send_message(chat_id=user_id, text="نام ناظر 2 را وارد کنید:")
    elif 'رییس' not in user_data[user_id]:
        user_data[user_id]['رییس'] = text
        context.bot.send_message(chat_id=user_id, text="نام منشی جلسه را وارد کنید:")
    elif 'منشی' not in user_data[user_id]:
        user_data[user_id]['منشی'] = text
        context.bot.send_message(chat_id=user_id, text="آدرس جدید شرکت را وارد کنید:")
    elif 'آدرس جدید' not in user_data[user_id]:
        user_data[user_id]['آدرس جدید'] = text
        context.bot.send_message(chat_id=user_id, text="کد پستی آدرس جدید را وارد کنید:")
    elif 'کد پستی' not in user_data[user_id]:
        user_data[user_id]['کد پستی'] = text
        context.bot.send_message(chat_id=user_id, text="نام وکیل یا نماینده برای ثبت را وارد کنید:")
    elif 'وکیل' not in user_data[user_id]:
        user_data[user_id]['وکیل'] = text
        send_final_output(update, context)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat_id
    user_data[user_id]['نوع شرکت'] = query.data
    context.bot.send_message(chat_id=user_id, text="شماره ثبت شرکت را وارد کنید:")
    query.answer()

def send_final_output(update: Update, context: CallbackContext):
    user_id = update.effective_chat.id
    data = user_data[user_id]

    text = f"""
صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']}
شماره ثبت شرکت : {data['شماره ثبت']}
شناسه ملی : {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']} ثبت شده به شماره {data['شماره ثبت']} در تاریخ {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.

الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت:
ـ {data['مدیر عامل']} به سمت رئیس جلسه
ـ {data['نایب رییس']} به سمت ناظر 1 جلسه
ـ {data['رییس']} به سمت ناظر 2 جلسه
ـ {data['منشی']} به سمت منشی جلسه انتخاب شدند

ب: دستور جلسه اتخاذ تصمیم در خصوص تغییر محل شرکت، مجمع موافقت و تصویب نمود که:
محل شرکت از آدرس قبلی به آدرس جدید {data['آدرس جدید']} کد پستی {data['کد پستی']} انتقال یافت.

مجمع به {data['وکیل']} احدی از سهامداران شرکت وکالت داده می‌شود که ضمن مراجعه به اداره ثبت شرکت‌ها نسبت به ثبت صورتجلسه و پرداخت حق‌الثبت و امضاء ذیل دفاتر ثبت اقدام نماید.

✍️ امضاء اعضای هیئت‌رئیسه:
رئیس جلسه: {data['مدیر عامل']}
ناظر 1 جلسه: {data['نایب رییس']}
ناظر 2 جلسه: {data['رییس']}
منشی جلسه: {data['منشی']}
"""
    context.bot.send_message(chat_id=user_id, text=text.strip())

# راه‌اندازی Dispatcher
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
