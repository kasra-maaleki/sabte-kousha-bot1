import re
context.bot.send_message(chat_id=chat_id, text="✅ شماره موبایل شما تایید شد.")
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
