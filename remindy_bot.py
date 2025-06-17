
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import dateparser
import requests

app = Flask(__name__)
reminders = []
stock_alerts = []

# Load reminders
try:
    with open("reminders.json", "r") as f:
        reminders = json.load(f)
except:
    reminders = []

# Load stock alerts
try:
    with open("stock_alerts.json", "r") as f:
        stock_alerts = json.load(f)
except:
    stock_alerts = []

scheduler = BackgroundScheduler()
scheduler.start()

def send_reminder(number, message):
    from twilio.rest import Client
    account_sid = 'YOUR_TWILIO_SID'
    auth_token = 'YOUR_AUTH_TOKEN'
    client = Client(account_sid, auth_token)
    client.messages.create(
        from_='whatsapp:+14155238886',
        to=number,
        body=f'⏰ Reminder: {message}'
    )

def send_alert(number, message):
    send_reminder(number, f'📈 Stock Alert: {message}')

def get_nse_price(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=5)
        response = session.get(url, timeout=5)
        data = response.json()
        return float(data["priceInfo"]["lastPrice"])
    except Exception as e:
        print(f"Error: {e}")
        return None

def check_stock_prices():
    global stock_alerts
    updated_alerts = []
    for alert in stock_alerts:
        symbol = alert["symbol"]
        price = get_nse_price(symbol)
        if price:
            if price >= alert["target"]:
                send_alert(alert["number"], f'{symbol} hit target ₹{alert["target"]} (current ₹{price:.2f})')
            elif price <= alert["stoploss"]:
                send_alert(alert["number"], f'{symbol} hit stoploss ₹{alert["stoploss"]} (current ₹{price:.2f})')
            else:
                updated_alerts.append(alert)
        else:
            updated_alerts.append(alert)
    stock_alerts = updated_alerts
    with open("stock_alerts.json", "w") as f:
        json.dump(stock_alerts, f)

# Run check every 5 minutes
scheduler.add_job(check_stock_prices, 'interval', minutes=5)

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    incoming_msg = request.form.get('Body')
    from_number = request.form.get('From')
    resp = MessagingResponse()
    msg = resp.message()

    lower_msg = incoming_msg.lower()
    if "remind" in lower_msg:
        reminder_time = dateparser.parse(incoming_msg, settings={'PREFER_DATES_FROM': 'future'})
        if reminder_time:
            clean_msg = incoming_msg.strip()
            reminders.append({
                "time": str(reminder_time),
                "message": clean_msg,
                "number": from_number
            })
            with open("reminders.json", "w") as f:
                json.dump(reminders, f)

            scheduler.add_job(send_reminder, 'date', run_date=reminder_time, args=[from_number, clean_msg])
            msg.body(f"✅ Reminder set for {reminder_time.strftime('%d-%b-%Y %I:%M %p')}")
        else:
            msg.body("❌ Couldn't understand the time. Use format like: remind me to drink water at 3pm")
    elif "alert me when" in lower_msg and "target" in lower_msg and "stoploss" in lower_msg:
        try:
            parts = incoming_msg.upper().replace("ALERT ME WHEN", "").strip().split("HITS")
            symbol = parts[0].strip()
            target_stop = parts[1].split("TARGET")[1].split("STOPLOSS")
            target = float(target_stop[0].strip())
            stoploss = float(target_stop[1].strip())

            alert = {
                "symbol": symbol,
                "target": target,
                "stoploss": stoploss,
                "number": from_number
            }
            stock_alerts.append(alert)
            with open("stock_alerts.json", "w") as f:
                json.dump(stock_alerts, f)
            msg.body(f"✅ Stock alert set for {symbol}\n🎯 Target: ₹{target}\n🛑 Stoploss: ₹{stoploss}")
        except Exception as e:
            msg.body("❌ Couldn't parse your stock alert. Use format like:\nalert me when RELIANCE hits 3000 target and 2500 stoploss")
    else:
        msg.body("👋 Hi! I'm Remindy.\n\n- 📅 Set reminder:\n'remind me to call dad at 5pm on 18 June'\n- 📈 Set stock alert:\n'alert me when RELIANCE hits 3000 target and 2500 stoploss'")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)