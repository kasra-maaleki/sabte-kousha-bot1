import re
import time
import random
from typing import Dict
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from sms_providers.niazpardaz import send_sms as sms_send


OTP_LENGTH = 5
OTP_TTL_MINUTES = 5
OTP_MAX_TRIES = 3
OTP_RESEND_LOCK_SECONDS = 60

# Storage بیرونی: فرض می‌کنیم main.py یک user_data گلوبال دارد
try:
    user_data # type: ignore
except NameError:
    user_data = {}


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize_digits(s: str) -> str:
    s = str(s)
    s = s.translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    return s




def clean_mobile(phone: str) -> str:
    if not phone:
        return ""
    phone = normalize_digits(phone).strip()
    phone = re.sub(r"^(\+?98|0098)", "0", phone)
    phone = re.sub(r"[\s\-\(\)]", "", phone)
    return phone if re.fullmatch(r"09\d{9}", phone) else ""


def make_otp(length: int = OTP_LENGTH) -> str:
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(random.randint(start, end))


def send_otp_sms(phone: str, code: str) -> bool:
    msg = f"کد تایید ثبت کوشا: {code}\nاعتبار: {OTP_TTL_MINUTES} دقیقه"
    ok, _ = sms_send(phone, msg)
    return ok

def otp_kb_resend_change() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ارسال مجدد کد", callback_data="otp:resend"), InlineKeyboardButton("تغییر شماره", callback_data="otp:change")],
        [InlineKeyboardButton("انصراف ❌", callback_data="otp:cancel")],
    ])


def start_phone_verification(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    d: Dict = user_data.setdefault(chat_id, {})
    d["otp"] = {"state": "ask_phone", "attempts": 0, "resend_after": 0}


    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("ارسال شماره من 📱", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    context.bot.send_message(
        chat_id=chat_id,
        text=("لطفاً شماره موبایل خود را وارد کنید (09xxxxxxxxx)\nیا از دکمه زیر استفاده کنید."),
        reply_markup=kb,
    )

def handle_contact_or_phone(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    d: Dict = user_data.setdefault(chat_id, {})
    otp = d.get("otp") or {}
    if otp.get("state") != "ask_phone":
        return


    if update.message and update.message.contact and update.message.contact.phone_number:
        phone = clean_mobile(update.message.contact.phone_number)
    else:
        phone = clean_mobile((update.message.text or "").strip())

    if not phone:
        context.bot.send_message(chat_id=chat_id, text="شماره معتبر نیست. با فرمت 09xxxxxxxxx ارسال کنید.")
        return

    code = make_otp()
    if not send_otp_sms(phone, code):
        context.bot.send_message(chat_id=chat_id, text="ارسال پیامک ناموفق بود. بعداً تلاش کنید.", reply_markup=ReplyKeyboardRemove())
        return

    now = int(time.time())
    d["otp"] = {
        "phone": phone,
        "code": code,
        "expires_at": now + OTP_TTL_MINUTES * 60,
        "attempts": 0,
        "resend_after": now + OTP_RESEND_LOCK_SECONDS,
        "state": "wait_code",
    }
    
    context.bot.send_message(chat_id=chat_id, text=f"کد به {phone} ارسال شد. کد {OTP_LENGTH} رقمی را وارد کنید.", reply_markup=ReplyKeyboardRemove())
    context.bot.send_message(chat_id=chat_id, text="در صورت عدم دریافت از دکمه‌های زیر استفاده کنید:", reply_markup=otp_kb_resend_change())

def handle_otp_input(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    d: Dict = user_data.setdefault(chat_id, {})
    otp = d.get("otp") or {}
    if otp.get("state") != "wait_code":
        return


    txt = normalize_digits((update.message.text or "").strip())
    if not re.fullmatch(fr"\d{{{OTP_LENGTH}}}", txt or ""):
        context.bot.send_message(chat_id=chat_id, text=f"فرمت کد نامعتبر است. یک کد {OTP_LENGTH} رقمی وارد کنید.")
        return
    
    
    now = int(time.time())
    if now > (otp.get("expires_at") or 0):
        context.bot.send_message(chat_id=chat_id, text="مهلت کد تمام شد. «ارسال مجدد کد».")
        return
    
    
    if (otp.get("attempts") or 0) >= OTP_MAX_TRIES:
        context.bot.send_message(chat_id=chat_id, text="تلاش بیش از حد مجاز. «ارسال مجدد کد».")
        return
    
    
    if txt == otp.get("code"):
        otp["state"] = "verified"
        d["verified"] = True
        context.user_data["verified"] = True
        context.bot.send_message(chat_id=chat_id, text="✅ شماره موبایل شما تایید شد.")
        send_topic_menu(chat_id, context)
        return
    
    
    otp["attempts"] = (otp.get("attempts") or 0) + 1
    remain = OTP_MAX_TRIES - otp["attempts"]
    if remain <= 0:
        context.bot.send_message(chat_id=chat_id, text="کد اشتباه و دفعات تمام شد. از «ارسال مجدد کد» استفاده کنید.")
    else:
        context.bot.send_message(chat_id=chat_id, text=f"کد نادرست است. {remain} تلاش دیگر دارید.")


def otp_buttons_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat.id
    d: Dict = user_data.setdefault(chat_id, {})
    otp = d.get("otp") or {}
    
    
    if not otp:
        query.answer()
        return
    
    
    data = (query.data or "").strip()
    
    
    if data == "otp:cancel":
        otp.clear(); d["otp"] = otp
        query.answer("انصراف")
        query.edit_message_text("فرآیند تایید شماره لغو شد.")
        return
    
    
    if data == "otp:change":
        otp.clear(); d["otp"] = {"state": "ask_phone", "attempts": 0, "resend_after": 0}
        query.answer()
        query.edit_message_text("شماره جدید را ارسال کنید یا از دکمه زیر استفاده کنید.")
        kb = ReplyKeyboardMarkup([[KeyboardButton("ارسال شماره من 📱", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=chat_id, text="منتظر شماره هستم…", reply_markup=kb)
        return
    
    
    if data == "otp:resend":
        now = int(time.time())
        lock = otp.get("resend_after") or 0
        if now < lock:
            query.answer(f"صبر کنید… {lock - now} ثانیه باقی مانده.", show_alert=True)
            return
        phone = otp.get("phone")
        if not phone:
            query.answer("شماره نامشخص است.", show_alert=True)
            return
        code = make_otp()
        ok = send_otp_sms(phone, code)
        if not ok:
            query.answer("ارسال پیامک ناموفق بود.", show_alert=True)
            return
        otp.update({"code": code, "expires_at": now + OTP_TTL_MINUTES * 60, "attempts": 0, "resend_after": now + OTP_RESEND_LOCK_SECONDS, "state": "wait_code"})
        d["otp"] = otp
        query.answer("کد جدید ارسال شد")
        query.edit_message_text(text=f"کد جدید به {phone} ارسال شد. کد {OTP_LENGTH} رقمی را وارد کنید.", reply_markup=otp_kb_resend_change())
        return

  
