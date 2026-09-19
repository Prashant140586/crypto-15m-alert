import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask

# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://api.india.delta.exchange"
THRESHOLD = 5.0

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Prevent duplicate alerts
alerted_candles = set()

# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Crypto 15M Alert Scanner is running."

@app.route("/health")
def health():
    return "OK"


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials are missing.")
        return

    url = f"https://api.telegram.org/bot8959079338:AAGOIK9QQDdziwQvNt2FHztPiOHQ3iWwpco/sendMessage"

    data = {
        "chat_id": 1008069540,
        "text": message
    }

    try:

        response = requests.post(
            url,
            data=data,
            timeout=10
        )

        result = response.json()

        if result.get("ok"):
            print("Telegram alert sent.")
        else:
            print("Telegram error:", result)

    except Exception as e:
        print("Telegram connection error:", e)


# ============================================================
# DELTA PRODUCTS
# ============================================================

def get_products():

    url = f"{BASE_URL}/v2/products"

    params = {
        "contract_types": "perpetual_futures",
        "states": "live",
        "page_size": 100
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data.get("result", [])

    except Exception as e:

        print("Product API error:", e)

        return []


# ============================================================
# GET CLOSED 15 MIN CANDLE
# ============================================================

def get_closed_candle(symbol):

    now = int(time.time())

    start = now - 3600

    url = f"{BASE_URL}/v2/history/candles"

    params = {
        "resolution": "15m",
        "symbol": symbol,
        "start": start,
        "end": now
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        candles = data.get("result", [])

        if len(candles) < 2:
            return None

        # Previous candle = CLOSED candle
        return candles[-2]

    except Exception as e:

        print(f"Candle error {symbol}: {e}")

        return None


# ============================================================
# SCAN
# ============================================================

def scan():

    global alerted_candles

    print()
    print("=" * 65)
    print("CRYPTO 15M +/-5% CLOSED CANDLE SCANNER")
    print(datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
    print("=" * 65)

    products = get_products()

    if not products:

        print("No products received.")

        return

    alerts = []

    for product in products:

        symbol = product.get("symbol")

        if not symbol:
            continue

        candle = get_closed_candle(symbol)

        if not candle:
            continue

        try:

            candle_time = str(candle[0])

            open_price = float(candle[1])

            close_price = float(candle[4])

            if open_price == 0:
                continue

            change = (
                (close_price - open_price)
                / open_price
            ) * 100

            candle_id = f"{symbol}_{candle_time}"

            if abs(change) >= THRESHOLD:

                if candle_id in alerted_candles:
                    continue

                direction = (
                    "🚀 UP"
                    if change > 0
                    else "🔻 DOWN"
                )

                alerts.append(
                    (
                        symbol,
                        change,
                        direction,
                        candle_time
                    )
                )

        except Exception as e:

            print(
                f"Processing error {symbol}: {e}"
            )

            continue


    # ========================================================
    # SEND ALERT
    # ========================================================

    if alerts:

        alerts.sort(
            key=lambda x: abs(x[1]),
            reverse=True
        )

        message = "🚨 CRYPTO 15M ALERT\n\n"

        for symbol, change, direction, candle_time in alerts:

            line = (
                f"{direction}  "
                f"{symbol}  "
                f"{change:+.2f}%"
            )

            print(line)

            message += line + "\n"

            alerted_candles.add(
                f"{symbol}_{candle_time}"
            )

        print()
        print("Sending Telegram alert...")

        send_telegram(message)

    else:

        print(
            "No NEW 15-minute candle "
            "moved +/-5%."
        )


# ============================================================
# WAIT FOR NEXT 15 MIN CANDLE
# ============================================================

def wait_until_next_candle():

    now = time.time()

    seconds_into_hour = int(now) % 3600

    next_boundary = (
        (seconds_into_hour // 900) + 1
    ) * 900

    wait_seconds = (
        next_boundary
        - seconds_into_hour
    )

    # Small buffer after candle close
    wait_seconds += 5

    print()

    print(
        f"Next 15M candle check in "
        f"{wait_seconds} seconds..."
    )

    time.sleep(wait_seconds)


# ============================================================
# SCANNER LOOP
# ============================================================

def scanner_loop():

    print()
    print("==============================================")
    print(" Delta 15M Crypto Alert Scanner")
    print(" Render Version")
    print(" Threshold : +/-5%")
    print(" Telegram  : ENABLED")
    print(" Trading   : DISABLED")
    print("==============================================")

    while True:

        try:

            scan()

        except Exception as e:

            print()
            print("Scanner error:", e)

        wait_until_next_candle()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    # Start scanner in background
    scanner_thread = threading.Thread(
        target=scanner_loop,
        daemon=True
    )

    scanner_thread.start()

    # Render PORT
    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print()
    print(
        f"Starting Render web server "
        f"on port {port}"
    )

    app.run(
        host="0.0.0.0",
        port=port
    )