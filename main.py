from flask import Flask, request
import telegram

TOKEN = '7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY'
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

@app.route('/')
def home():
    return 'ربات تنظیم صورتجلسه فعال است ✅'

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        text = update.message.text.strip()

        if chat_id not in user_data:
            user_data[chat_id] = {'step': 0}

        step = user_data[chat_id]['step']

        if text == '/start':
            user_data[chat_id] = {'step': 1}
            bot.send_message(chat_id=chat_id, text='👋 سلام! لطفاً نام شرکت را وارد کنید:')
        elif step == 1:
            user_data[chat_id]['company_name'] = text
            user_data[chat_id]['step'] = 2
            bot.send_message(chat_id=chat_id, text='شماره ثبت شرکت را وارد کنید:')
        elif step == 2:
            user_data[chat_id]['reg_number'] = text
            user_data[chat_id]['step'] = 3
            bot.send_message(chat_id=chat_id, text='نوع جلسه را وارد کنید (مثلاً: هیئت مدیره یا مجمع عمومی):')
        elif step == 3:
            user_data[chat_id]['meeting_type'] = text
            user_data[chat_id]['step'] = 4
            bot.send_message(chat_id=chat_id, text='تاریخ جلسه را وارد کنید (مثلاً: ۱۴۰۳/۰۵/۱۰):')
        elif step == 4:
            user_data[chat_id]['date'] = text
            user_data[chat_id]['step'] = 5
            bot.send_message(chat_id=chat_id, text='موضوع جلسه را بنویسید (مثلاً: تغییر آدرس شرکت):')
        elif step == 5:
            user_data[chat_id]['subject'] = text

            # ساخت متن صورتجلسه
            data = user_data[chat_id]
            message = f"""📄 صورتجلسه {data['meeting_type']}
نام شرکت: {data['company_name']}
شماره ثبت: {data['reg_number']}
تاریخ جلسه: {data['date']}
موضوع جلسه: {data['subject']}

🎯 متن پیشنهادی:
در تاریخ {data['date']} جلسه {data['meeting_type']} شرکت {data['company_name']} به شماره ثبت {data['reg_number']} با موضوع {data['subject']} تشکیل شد و تصمیمات لازم اتخاذ گردید.

✅ پایان.
"""
            bot.send_message(chat_id=chat_id, text=message)
            user_data[chat_id]['step'] = 0  # بازنشانی برای ورود اطلاعات جدید
        else:
            bot.send_message(chat_id=chat_id, text='لطفاً با دستور /start شروع کنید.')
    
    return 'ok'
