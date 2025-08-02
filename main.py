import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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

fields = [
    "نوع شرکت", "نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت",
    "مدیر عامل", "نایب رییس", "رییس", "منشی", "آدرس جدید", "کد پستی", "وکیل"
]

persian_number_fields = ["شماره ثبت", "شناسه ملی", "سرمایه", "کد پستی"]

def is_persian_number(text):
    return all('۰' <= ch <= '۹' or ch.isspace() for ch in text)

def create_back_button():
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data='back')]]
    return InlineKeyboardMarkup(keyboard)

def back_button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = user_data.get(chat_id)

    if not data or data.get("step", 0) <= 1:
        query.answer("امکان بازگشت بیشتر وجود ندارد.")
        return

    data["step"] -= 1

    # حذف آخرین ورودی ثبت‌شده
    step = data["step"]
    if step < len(fields):
        field_to_delete = fields[step]
        if field_to_delete in data:
            del data[field_to_delete]

    # اگر وارد مرحله شرکا هستیم
    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step == 10:
            context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):", reply_markup=create_back_button())
            return
        elif step > 10:
            current = data.get("current_partner", 1)
            if f"سهم الشرکه شریک {current}" in data:
                del data[f"سهم الشرکه شریک {current}"]
                context.bot.send_message(chat_id=chat_id, text=f"مبلغ سهم‌الشرکه شریک شماره {current} را وارد کنید (به ریال):", reply_markup=create_back_button())
                return
            elif f"شریک {current}" in data:
                del data[f"شریک {current}"]
                data["current_partner"] = current - 1
                context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {data['current_partner']} را وارد کنید:", reply_markup=create_back_button())
                return

    # بازگشت به مرحله عمومی
    if step < len(fields):
        current_field = fields[step]
        label = get_label(current_field)
        context.bot.send_message(chat_id=chat_id, text=label, reply_markup=create_back_button())
    else:
        context.bot.send_message(chat_id=chat_id, text="مرحله قبلی بازیابی شد.", reply_markup=create_back_button())

    query.answer("مرحله قبلی بازیابی شد.")

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
        context.bot.send_message(chat_id=chat_id, text="لطفاً ابتدا موضوع صورتجلسه را انتخاب کنید.")
        return

    # تعریف فیلدهای پایه برای تغییر آدرس مسئولیت محدود
    common_fields = ["نام شرکت", "شماره ثبت", "شناسه ملی", "سرمایه", "تاریخ", "ساعت", "آدرس جدید", "کد پستی", "وکیل"]

    # حالت تغییر آدرس + مسئولیت محدود
    if data.get("موضوع صورتجلسه") == "تغییر آدرس" and data.get("نوع شرکت") == "مسئولیت محدود":
        if step == 1:
            data["نام شرکت"] = text
            data["step"] = 2
            context.bot.send_message(chat_id=chat_id, text="شماره ثبت شرکت را وارد کنید:", reply_markup=create_back_button())
            return

        if 2 <= step <= 9:
            field = common_fields[step - 1]

            if field == "تاریخ":
                if text.count('/') != 2:
                    context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو / ).")
                    return

            if field in persian_number_fields:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.")
                    return

            data[field] = text
            data["step"] += 1

            if step == 9:
                context.bot.send_message(chat_id=chat_id, text="تعداد شرکا را وارد کنید (بین ۲ تا ۷):", reply_markup=create_back_button())
                return
            else:
                next_field = common_fields[step]
                context.bot.send_message(chat_id=chat_id, text=get_label(next_field))
                return

        if step == 10:
            if not text.isdigit():
                context.bot.send_message(chat_id=chat_id, text="❗️لطفاً تعداد شرکا را فقط با عدد وارد کنید (بین ۲ تا ۷).")
                return
            count = int(text)
            if count < 2 or count > 7:
                context.bot.send_message(chat_id=chat_id, text="❗️تعداد شرکا باید بین ۲ تا ۷ باشد. لطفاً مجدداً وارد کنید.")
                return
            data["تعداد شرکا"] = count
            data["step"] += 1
            data["current_partner"] = 1
            context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره ۱ را وارد کنید:", reply_markup=create_back_button())
            return

        if step > 10:
            current_partner = data.get("current_partner", 1)
            count = data.get("تعداد شرکا", 0)

            if f"شریک {current_partner}" not in data:
                data[f"شریک {current_partner}"] = text
                context.bot.send_message(chat_id=chat_id, text=f"میزان سهم الشرکه شریک شماره {current_partner} را به ریال وارد کنید (عدد فارسی):", reply_markup=create_back_button())
                return
            elif f"سهم الشرکه شریک {current_partner}" not in data:
                if not is_persian_number(text):
                    context.bot.send_message(chat_id=chat_id, text="❗️لطفاً میزان سهم الشرکه را فقط با اعداد فارسی وارد کنید.")
                    return
                data[f"سهم الشرکه شریک {current_partner}"] = text
                if current_partner < count:
                    data["current_partner"] = current_partner + 1
                    context.bot.send_message(chat_id=chat_id, text=f"نام شریک شماره {current_partner + 1} را وارد کنید:", reply_markup=create_back_button())
                    return
                else:
                    send_summary(chat_id, context)
                    return
        return

    # منطق قبلی برای سایر موارد و صورتجلسات

    if step == 1:
        data["نام شرکت"] = text
        data["step"] = 2
        next_field = fields[2]
        label = get_label(next_field)
        context.bot.send_message(chat_id=chat_id, text=label)
        return

    if step == 0:
        context.bot.send_message(chat_id=chat_id, text="لطفاً نوع شرکت را از گزینه‌های ارائه شده انتخاب کنید.", reply_markup=create_back_button())
        return

    if 2 <= step < len(fields):
        field = fields[step]

        if field == "تاریخ":
            if text.count('/') != 2:
                context.bot.send_message(chat_id=chat_id, text="❗️فرمت تاریخ صحیح نیست. لطفاً به صورت ۱۴۰۴/۰۴/۰۷ وارد کنید (با دو /).")
                return

        if field in persian_number_fields:
            if not is_persian_number(text):
                context.bot.send_message(chat_id=chat_id, text=f"لطفاً مقدار '{field}' را فقط با اعداد فارسی وارد کنید.")
                return

        data[field] = text
        data["step"] += 1
        if data["step"] < len(fields):
            next_field = fields[data["step"]]
            label = get_label(next_field)
            context.bot.send_message(chat_id=chat_id, text=label, reply_markup=create_back_button())
        else:
            send_summary(chat_id, context)
        return

    context.bot.send_message(chat_id=chat_id, text="لطفاً منتظر بمانید...", reply_markup=create_back_button())

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
        context.bot.send_message(chat_id=chat_id, text=f"موضوع صورتجلسه انتخاب شد: {query.data}\n\nنوع شرکت را انتخاب کنید:", reply_markup=reply_markup, reply_markup=create_back_button())
        return

    if user_data[chat_id].get("step") == 0:
        user_data[chat_id]["نوع شرکت"] = query.data
        user_data[chat_id]["step"] = 1
        context.bot.send_message(chat_id=chat_id, text="نام شرکت را وارد کنید:")
        return

def send_summary(chat_id, context):
    data = user_data[chat_id]
    موضوع = data.get("موضوع صورتجلسه")
    نوع_شرکت = data.get("نوع شرکت")

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
        context.bot.send_message(chat_id=chat_id, text=text)
        
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
        context.bot.send_message(chat_id=chat_id, text=text)

        # ✅ ساخت فایل Word و ارسال
        file_path = generate_word_file(text)
        with open(file_path, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, filename="صورتجلسه.docx")
    
        os.remove(file_path)  # ← حذف فایل پس از ارسال (اختیاری)

    else:
        # در سایر موارد فعلاً چیزی ارسال نشود
        context.bot.send_message(chat_id=chat_id, text="✅ اطلاعات با موفقیت دریافت شد.\nدر حال حاضر صورتجلسه‌ای برای این ترکیب تعریف نشده است.")

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
dispatcher.add_handler(CallbackQueryHandler(back_button_handler, pattern='^back$'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
