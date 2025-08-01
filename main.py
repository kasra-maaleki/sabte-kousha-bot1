import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from flask import Flask, request

TOKEN = "7483081974:AAGRXi-NxDAgwYF-xpdhqsQmaGbw8-DipXY"
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

user_data = {}

fields_common = [
    "نوع شرکت", "نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

persian_number_fields = ["شماره ثبت", "شناسه ملی", "سرمایه", "کد پستی"]

def is_persian_number(text):
    return all('۰' <= ch <= '۹' or ch.isspace() for ch in text)

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

    # چک کن اول موضوع انتخاب شده باشه
    if "موضوع صورتجلسه" not in data:
        context.bot.send_message(chat_id=chat_id, text="لطفاً ابتدا موضوع صورتجلسه را انتخاب کنید.")
        return

    # مرحله دریافت نوع شرکت
    if step == 0:
        context.bot.send_message(chat_id=chat_id, text="لطفاً نوع شرکت را از دکمه‌ها انتخاب کنید.")
        return

    # مرحله دریافت نام شرکت
    if step == 1:
        data["نام شرکت"] = text
        data["step"] = 2
        context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:")
        return

    # مرحله دریافت شماره ثبت و بعدی‌ها تا قبل از شرکا
    if step >= 2 and "شرکا" not in data:
        current_field = get_field_by_step(data["step"])
        
        # بررسی تاریخ
        if current_field == "تاریخ":
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).")
                return

        # اعداد فارسی
        if current_field in persian_number_fields:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{current_field}' را فقط با اعداد فارسی وارد کنید.")
                return

        data[current_field] = text
        data["step"] += 1

        # اگر موضوع تغییر آدرس و نوع شرکت مسئولیت محدود و مرحله رسید به بعد از کد پستی باید پرسید تعداد شرکا
        if (data["موضوع صورتجلسه"] == "تغییر آدرس" and
            data["نوع شرکت"] == "مسئولیت محدود" and
            current_field == "کد پستی"):
            context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):")
            data["step"] += 1
            return

        # ادامه سوالات عادی
        if data["step"] < len(fields_common):
            next_field = get_field_by_step(data["step"])
            label = get_label(next_field)
            context.bot.send_message(chat_id=chat_id, text=label)
        else:
            send_summary(chat_id, context)
        return

    # اگر موضوع تغییر آدرس و نوع شرکت مسئولیت محدود و در مرحله پرسش تعداد شرکا هستیم
    if "شرکا" not in data and data.get("step") == len(fields_common) + 1:
        if not text.isdigit():
            context.bot.send_message(chat_id=chat_id, text="لطفاً یک عدد صحیح وارد کنید.")
            return
        count = int(text)
        if count < 2 or count > 7:
            context.bot.send_message(chat_id=chat_id, text="تعداد شرکا باید بین ۲ تا ۷ باشد.")
            return
        data["تعداد شرکا"] = count
        data["شرکا"] = []
        data["step"] += 1
        context.bot.send_message(chat_id=chat_id, text=f"نام شریک 1 را وارد کنید:")
        return

    # دریافت نام و سهم الشرکه شرکا
    if "شرکا" in data and data.get("step") >= len(fields_common) + 2:
        idx = data.get("partner_idx", 0)
        if "partner_step" not in data:
            data["partner_step"] = "name"

        if data["partner_step"] == "name":
            data["شرکا"].append({"name": text})
            data["partner_step"] = "share"
            context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک {idx+1} را به ریال وارد کنید (اعداد فارسی):")
            return

        if data["partner_step"] == "share":
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text="لطفاً مقدار سهم الشرکه را فقط با اعداد فارسی وارد کنید.")
                return
            data["شرکا"][idx]["share"] = text
            idx += 1
            data["partner_idx"] = idx
            data["partner_step"] = "name"
            if idx < data["تعداد شرکا"]:
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک {idx+1} را وارد کنید:")
            else:
                # همه شرکا و سهم‌ها دریافت شدند
                send_summary(chat_id, context)
            return

def get_field_by_step(step):
    # step از 0 شروع شده، ولی در user_data.step اولین فیلد نوع شرکت است که از قبل گرفته شده
    # در این کد step 0 برای نوع شرکت نیست، پس این تابع map می کند به fields_common با جابجایی
    return fields_common[step]

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

    data = user_data.setdefault(chat_id, {})

    # اگر موضوع صورتجلسه انتخاب نشده
    if "موضوع صورتجلسه" not in data:
        data["موضوع صورتجلسه"] = query.data
        data["step"] = 0
        keyboard = [
            [InlineKeyboardButton("سهامی خاص", callback_data='سهامی خاص')],
            [InlineKeyboardButton("مسئولیت محدود", callback_data='مسئولیت محدود')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id, text=f"موضوع صورتجلسه انتخاب شد: {query.data}\n\nنوع شرکت را انتخاب کنید:", reply_markup=reply_markup)
        return

    # اگر نوع شرکت انتخاب شده و در مرحله صفر هستیم، به مرحله بعد بریم و نام شرکت رو بخوایم
    if data.get("step") == 0:
        data["نوع شرکت"] = query.data
        data["step"] = 1
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
        return

def send_summary(chat_id, context):
    data = user_data[chat_id]

    # حالت تغییر آدرس مسئولیت محدود با شرکا
    if (data.get("موضوع صورتجلسه") == "تغییر آدرس" and
        data.get("نوع شرکت") == "مسئولیت محدود" and
        "شرکا" in data):
        
        partners_text = ""
        for p in data["شرکا"]:
            partners_text += f"{p['name']:<30} {p['share']} ریال\n"
        
        # امضاها با فاصله
        signatures = "     ".join(p["name"] for p in data["شرکا"])

        text = f"""صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']}
شماره ثبت شرکت :     {data['شماره ثبت']}
شناسه ملی :      {data['شناسه ملی']}
سرمایه ثبت شده : {data['سرمایه']} ریال

صورتجلسه مجمع عمومی فوق العاده شرکت {data['نام شرکت']} {data['نوع شرکت']} ثبت شده به شماره {data['شماره ثبت']} در تاریخ  {data['تاریخ']} ساعت {data['ساعت']} با حضور کلیه شرکا در محل قانونی شرکت تشکیل و نسبت به تغییر محل شرکت اتخاذ تصمیم شد. 

اسامی شرکا                                                     میزان سهم الشرکه
{partners_text}
محل شرکت از آدرس قبلی به آدرس {data['آدرس جدید']} به کدپستی {data['کد پستی']} انتقال یافت.

به آقای {data['وکیل']} احدی از شرکاء وکالت داده می شود تا ضمن مراجعه به اداره ثبت شرکتها نسبت به ثبت صورتجلسه و امضاء ذیل دفتر ثبت اقدام نماید.

امضاء شرکا : 

{signatures}"""

        context.bot.send_message(chat_id=chat_id, text=text)
        return

    # حالت پیش فرض (مثلا سهامی خاص و یا سایر صورتجلسات)
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
