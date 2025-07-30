import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"

bot = telegram.Bot(token=TOKEN)

user_data = {}

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=chat_id, text="به خدمات ثبتی کوشا خوش آمدید 🙏🏼 در عرض چند دقیقه صورتجلسه خود را بسیار دقیق دریافت خواهید کرد")
    context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
    user_data[chat_id] = {"step": "ask_name"}

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text
    data = user_data.get(chat_id, {})

    if not data:
        context.bot.send_message(chat_id=chat_id, text="لطفاً ابتدا دستور /start را وارد کنید.")
        return

    step = data.get("step")

    if step == "ask_name":
        data["company_name"] = text
        data["step"] = "ask_company_type"
        keyboard = [
            [InlineKeyboardButton("(سهامی خاص)", callback_data="سهامی خاص")],
            [InlineKeyboardButton("(مسئولیت محدود)", callback_data="مسئولیت محدود")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id, text="نوع شرکت را انتخاب کنید:", reply_markup=reply_markup)

    elif step == "ask_capital":
        data["capital"] = text
        data["step"] = "ask_date"
        context.bot.send_message(chat_id=chat_id, text="تاریخ صورتجلسه را وارد کنید (بهتر است تاریخ روز باشد چون برای ثبت صورتجلسات در اداره فقط یک ماه فرصت دارید):")

    elif step == "ask_date":
        data["date"] = text
        data["step"] = "ask_time"
        context.bot.send_message(chat_id=chat_id, text="ساعت جلسه را وارد کنید (مثلاً: ۱۴:۰۰):")

    elif step == "ask_time":
        data["time"] = text
        data["step"] = "ask_members"
        context.bot.send_message(chat_id=chat_id, text="اسامی اعضای حاضر در جلسه را وارد کنید (با کاما جدا کنید):")

    elif step == "ask_members":
        data["members"] = text
        data["step"] = "ask_new_address"
        context.bot.send_message(chat_id=chat_id, text="آدرس جدید شرکت را وارد کنید:")

    elif step == "ask_new_address":
        data["new_address"] = text
        data["step"] = "ask_ceo"
        context.bot.send_message(chat_id=chat_id, text="مدیر عامل را وارد کنید (مثلا: آقای ... خانم ...):")

    elif step == "ask_ceo":
        data["ceo"] = text
        data["step"] = "ask_lawyer"
        context.bot.send_message(chat_id=chat_id, text="وکیل را وارد کنید (منظور شخصی هست که از طرف شما برای ثبت صورتجلسات و امضا دفاتر ثبتی انتخاب میشود):")

    elif step == "ask_lawyer":
        data["lawyer"] = text
        data["step"] = "completed"
        send_result(update, context, data)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()
    data = user_data.get(chat_id, {})

    step = data.get("step")

    if step == "ask_company_type":
        data["company_type"] = query.data
        data["step"] = "ask_meeting_type"
        keyboard = [
            [InlineKeyboardButton("مجمع عمومی فوق العاده", callback_data="مجمع عمومی فوق العاده")],
            [InlineKeyboardButton("مجمع عمومی عادی بطور فوق العاده", callback_data="مجمع عمومی عادی بطور فوق العاده")],
            [InlineKeyboardButton("هیئت مدیره", callback_data="هیئت مدیره")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id, text="نوع صورتجلسه درخواستی را وارد کنید:", reply_markup=reply_markup)

    elif step == "ask_meeting_type":
        data["meeting_type"] = query.data
        data["step"] = "ask_capital"
        context.bot.send_message(chat_id=chat_id, text="سرمایه اولیه شرکت را به ریال وارد کنید:")

def send_result(update: Update, context: CallbackContext, data):
    chat_id = update.message.chat_id
    msg = f"""صورتجلسه {data['meeting_type']}
نام شرکت: {data['company_name']}
نوع شرکت: {data['company_type']}
سرمایه: {data['capital']} ریال
تاریخ: {data['date']}
ساعت: {data['time']}
اعضا: {data['members']}
آدرس جدید: {data['new_address']}
مدیر عامل: {data['ceo']}
وکیل: {data['lawyer']}

موضوع جلسه:
با توجه به تصمیمات اتخاذ شده در جلسه {data['meeting_type']}، تغییر آدرس شرکت به نشانی جدید صورت گرفت و اختیار ثبت آن به وکیل شرکت واگذار شد.
"""
    context.bot.send_message(chat_id=chat_id, text=msg)
    user_data.pop(chat_id, None)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
