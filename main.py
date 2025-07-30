from flask import Flask, request
import telegram
from telegram import ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

TOKEN = '7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY'
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)
user_data = {}

@app.route('/')
def home():
    return 'ربات ثبت کوشا فعال است ✅'

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dp = Dispatcher(bot, None, workers=0)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.process_update(update)
    return 'ok'

def start(update, context):
    chat_id = update.message.chat.id
    user_data[chat_id] = {'step': 'name'}
    context.bot.send_message(chat_id=chat_id, text="سلام! لطفاً نام شرکت را وارد کنید:")

def handle_message(update, context):
    chat_id = update.message.chat.id
    text = update.message.text
    data = user_data.get(chat_id, {})

    step = data.get('step', 'name')

    if step == 'name':
        data['name'] = text
        data['step'] = 'type'
        reply_markup = ReplyKeyboardMarkup([['سهامی خاص', 'مسئولیت محدود']], one_time_keyboard=True, resize_keyboard=True)
        context.bot.send_message(chat_id=chat_id, text="نوع شرکت چیست؟", reply_markup=reply_markup)

    elif step == 'type':
        data['type'] = text
        data['step'] = 'reg_number'
        context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:")

    elif step == 'reg_number':
        data['reg_number'] = text
        data['step'] = 'national_id'
        context.bot.send_message(chat_id=chat_id, text="شناسه ملی شرکت را وارد کنید:")

    elif step == 'national_id':
        data['national_id'] = text
        data['step'] = 'capital'
        context.bot.send_message(chat_id=chat_id, text="سرمایه ثبت شده (ریال):")

    elif step == 'capital':
        data['capital'] = text
        data['step'] = 'date'
        context.bot.send_message(chat_id=chat_id, text="تاریخ برگزاری مجمع (مثلاً ۱۴۰۴/۰۵/۱۰):")

    elif step == 'date':
        data['date'] = text
        data['step'] = 'time'
        context.bot.send_message(chat_id=chat_id, text="ساعت برگزاری مجمع:")

    elif step == 'time':
        data['time'] = text
        data['step'] = 'manager'
        context.bot.send_message(chat_id=chat_id, text="نام مدیرعامل (رئیس جلسه):")

    elif step == 'manager':
        data['manager'] = text
        data['step'] = 'observer1'
        context.bot.send_message(chat_id=chat_id, text="نام ناظر اول:")

    elif step == 'observer1':
        data['observer1'] = text
        data['step'] = 'observer2'
        context.bot.send_message(chat_id=chat_id, text="نام ناظر دوم:")

    elif step == 'observer2':
        data['observer2'] = text
        data['step'] = 'secretary'
        context.bot.send_message(chat_id=chat_id, text="نام منشی جلسه:")

    elif step == 'secretary':
        data['secretary'] = text
        data['step'] = 'new_address'
        context.bot.send_message(chat_id=chat_id, text="آدرس جدید شرکت:")

    elif step == 'new_address':
        data['new_address'] = text
        data['step'] = 'postal_code'
        context.bot.send_message(chat_id=chat_id, text="کد پستی:")

    elif step == 'postal_code':
        data['postal_code'] = text
        data['step'] = 'attorney'
        context.bot.send_message(chat_id=chat_id, text="نام وکیل جهت ثبت صورتجلسه:")

    elif step == 'attorney':
        data['attorney'] = text
        user_data[chat_id] = {'step': 'done'}  # پایان مراحل
        send_final_summary(chat_id, data, context)

    else:
        context.bot.send_message(chat_id=chat_id, text="دستور را از ابتدا شروع کنید با /start")

    user_data[chat_id] = data

def send_final_summary(chat_id, data, context):
    text = f"""📄 صورتجلسه مجمع عمومی فوق العاده شرکت {data['name']} {data['type']}
شماره ثبت شرکت: {data['reg_number']}
شناسه ملی: {data['national_id']}
سرمایه ثبت شده: {data['capital']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['name']} {data['type']} ثبت شده به شماره {data['reg_number']} در تاریخ {data['date']} ساعت {data['time']} با حضور کلیه سهامداران در محل قانونی شرکت تشکیل گردید و تصمیمات ذیل اتخاذ گردید.

الف: در اجرای ماده 101 لایحه اصلاحی قانون تجارت:
- {data['manager']} به سمت رئیس جلسه
- {data['observer1']} به سمت ناظر اول جلسه
- {data['observer2']} به سمت ناظر دوم جلسه
- {data['secretary']} به سمت منشی جلسه انتخاب شدند.

ب: دستور جلسه اتخاذ تصمیم در خصوص تغییر محل شرکت، مجمع موافقت و تصویب نمود که:
محل شرکت از آدرس قبلی به آدرس جدید {data['new_address']} کد پستی {data['postal_code']} انتقال یافت.

مجمع به {data['attorney']} احدی از سهامداران شرکت وکالت داده می‌شود که ضمن مراجعه به اداره ثبت شرکت‌ها نسبت به ثبت صورتجلسه و پرداخت حق‌الثبت و امضای ذیل دفاتر ثبت اقدام نماید.

✍️ امضای اعضای هیأت رئیسه:
- رئیس جلسه: {data['manager']}
- ناظر اول جلسه: {data['observer1']}
- ناظر دوم جلسه: {data['observer2']}
- منشی جلسه: {data['secretary']}"""

    context.bot.send_message(chat_id=chat_id, text=text)

