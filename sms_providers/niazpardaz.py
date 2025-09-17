import requests
"fromNumber": sender or NIAZ_SENDER,
"toNumbers": _as_list_str(to_numbers),
"messageContent": message,
"isFlash": bool(is_flash),
"sendDelay": int(send_delay),
}
try:
r = requests.post(SEND_SMS_EP, json=payload, headers=Headers, timeout=timeout)
try:
data = r.json()
except Exception:
data = {"raw": r.text}
ok = r.status_code == 200
# بعضی پنل‌ها در بدنه پاسخ هم کد موفقیت می‌دهند، در صورت موجود بودن می‌شه بررسی دقیق‌تری کرد
return ok, data
except Exception as e:
return False, {"error": str(e)}




def get_credit(timeout: int = 10) -> Tuple[bool, dict]:
payload = {"userName": NIAZ_USER, "password": NIAZ_PASS}
try:
r = requests.post(CREDIT_EP, json=payload, headers=Headers, timeout=timeout)
return r.status_code == 200, r.json()
except Exception as e:
return False, {"error": str(e)}




def get_senders(timeout: int = 10) -> Tuple[bool, dict]:
payload = {"userName": NIAZ_USER, "password": NIAZ_PASS}
try:
r = requests.post(SENDERS_EP, json=payload, headers=Headers, timeout=timeout)
return r.status_code == 200, r.json()
except Exception as e:
return False, {"error": str(e)}
