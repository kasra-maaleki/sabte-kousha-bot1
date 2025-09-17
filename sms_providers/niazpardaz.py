import requests
from typing import Tuple, Union, List
from sms_config import NIAZ_USER, NIAZ_PASS, NIAZ_SENDER, NIAZ_BASE

SEND_SMS_EP = NIAZ_BASE + "SendBatchSms"
CREDIT_EP = NIAZ_BASE + "GetCredit"
SENDERS_EP = NIAZ_BASE + "GetSenderNumbers"


Headers = {"Content-Type": "application/json"}

def _as_list_str(numbers: Union[str, List[str]]) -> str:
    if isinstance(numbers, str):
        return numbers
# حذف فاصله‌ها و اتصال با comma
    return ",".join([str(x).strip() for x in numbers if str(x).strip()])

def send_sms(
    to_numbers: Union[str, List[str]],
    message: str,
    sender: str = None,
    is_flash: bool = False,
    send_delay: int = 0,
    timeout: int = 10,
) -> Tuple[bool, dict]:
    """
    ارسال پیامک از طریق وب‌سرویس نیازپرداز.
    خروجی: (موفقیت/شکست، پاسخ خام json یا dict خالی)
    """
    payload = {
        "userName": NIAZ_USER,
        "password": NIAZ_PASS,
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

