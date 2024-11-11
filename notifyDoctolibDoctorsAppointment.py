from datetime import date, datetime, timedelta
import json
import urllib.parse
import urllib.request
import sys

TELEGRAM_BOT_TOKEN = ''
TELEGRAM_CHAT_ID = ''
BOOKING_URL = 'https://www.doctolib.de/'
AVAILABILITIES_URL = ''
APPOINTMENT_NAME = None
MOVE_BOOKING_URL = None
UPCOMING_DAYS = 15
MAX_ALLOWED_DAYS = 30  # Maximum allowed days to look ahead (do not change unless you know what you're doing)
MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days = UPCOMING_DAYS)
NOTIFY_HOURLY = False

DEBUG_MODE = False

def debug_print(message):
    if DEBUG_MODE:
        print(f"DEBUG: {message}", file=sys.stderr)

if UPCOMING_DAYS > MAX_ALLOWED_DAYS:
    debug_print(f"⚠️ UPCOMING_DAYS ({UPCOMING_DAYS}) exceeds maximum allowed value ({MAX_ALLOWED_DAYS}). Setting to {MAX_ALLOWED_DAYS}")
    UPCOMING_DAYS = MAX_ALLOWED_DAYS

MAX_DATETIME_IN_FUTURE = datetime.today() + timedelta(days=UPCOMING_DAYS)

def parse_url_safely(url):
    debug_print("Analyzing URL components:")
    parsed = urllib.parse.urlparse(url)
    query_params = dict(urllib.parse.parse_qsl(parsed.query))
    
    for key, value in query_params.items():
        debug_print(f"  - {key}: {value}")
    
    return parsed, query_params

debug_print("Checking initial parameters...")
debug_print(f"Current configuration:")
debug_print(f"- TELEGRAM_BOT_TOKEN: {'✅ SET' if TELEGRAM_BOT_TOKEN else '❌ MISSING'}")
debug_print(f"- TELEGRAM_CHAT_ID: {'✅ SET' if TELEGRAM_CHAT_ID else '❌ MISSING'}")
debug_print(f"- BOOKING_URL: {'✅ SET' if BOOKING_URL else '❌ MISSING'}")
debug_print(f"- AVAILABILITIES_URL: {'✅ SET' if AVAILABILITIES_URL else '❌ MISSING'}")
debug_print(f"- UPCOMING_DAYS: {UPCOMING_DAYS}")
debug_print(f"- Looking for slots between now and: {MAX_DATETIME_IN_FUTURE}")

missing_params = []
if not TELEGRAM_BOT_TOKEN:
    missing_params.append("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_CHAT_ID:
    missing_params.append("TELEGRAM_CHAT_ID")
if not BOOKING_URL:
    missing_params.append("BOOKING_URL")
if not AVAILABILITIES_URL:
    missing_params.append("AVAILABILITIES_URL")

if missing_params:
    debug_print(f"❌ Missing required parameters: {', '.join(missing_params)}")
    debug_print("⛔ Exiting due to missing required parameters")
    exit()

debug_print(f"Original URL: {AVAILABILITIES_URL}")
urlParts, query = parse_url_safely(AVAILABILITIES_URL)

original_start_date = query.get('start_date')
debug_print(f"Original start date in URL: {original_start_date}")

today = date.today()
if original_start_date:
    try:
        start_date = datetime.strptime(original_start_date, '%Y-%m-%d').date()
        if start_date < today:
            debug_print(f"Start date {start_date} is in the past, updating to today")
            query['start_date'] = today.isoformat()
        else:
            debug_print(f"Keeping original start date: {start_date}")
    except ValueError as e:
        debug_print(f"❌ Error parsing start_date: {e}")
        query['start_date'] = today.isoformat()
else:
    query['start_date'] = today.isoformat()

if 'limit' not in query:
    query['limit'] = UPCOMING_DAYS
else:
    debug_print(f"Keeping original limit: {query['limit']}")

newAvailabilitiesUrl = urlParts._replace(query=urllib.parse.urlencode(query)).geturl()
debug_print(f"Modified URL: {newAvailabilitiesUrl}")
debug_print("Changes made to URL:")
for key, value in query.items():
    original = dict(urllib.parse.parse_qsl(urlParts.query)).get(key)
    if original != value:
        debug_print(f"  - {key}: {original} → {value}")

try:
    request = urllib.request.Request(newAvailabilitiesUrl)
    request.add_header(
        'User-Agent',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    )
    debug_print("Sending HTTP request...")
    response = urllib.request.urlopen(request)
    debug_print(f"Response status: {response.status}")
    response_content = response.read().decode('utf-8')
    debug_print(f"Response length: {len(response_content)} characters")
    
    availabilities = json.loads(response_content)
    debug_print(f"JSON parsed successfully")
    debug_print(f"Response overview:")
    debug_print(f"- Total slots in response: {availabilities.get('total', 0)}")
except Exception as e:
    debug_print(f"❌ Error during request/response handling: {str(e)}")
    if DEBUG_MODE:
        debug_print("Full error details:")
        import traceback
        debug_print(traceback.format_exc())
    exit()

debug_print("\nAnalyzing available slots...")
earliest_slot = None

for day in availabilities['availabilities']:
    debug_print(f"Checking date: {day['date']}")
    if day['slots']:
        debug_print(f"Found {len(day['slots'])} slots on this day:")
        for slot in day['slots']:
            debug_print(f"  - Raw slot: {slot}")
            try:
                slot_datetime = datetime.fromisoformat(slot.replace('Z', '+00:00'))
                slot_datetime = slot_datetime.replace(tzinfo=None)
                debug_print(f"  - Parsed slot: {slot_datetime}")
                
                if earliest_slot is None or slot_datetime < earliest_slot:
                    earliest_slot = slot_datetime
                    debug_print(f"  ✅ New earliest slot found: {earliest_slot}")
            except ValueError as e:
                debug_print(f"  ❌ Error parsing slot datetime: {slot} - Error: {str(e)}")

if 'next_slot' in availabilities and not earliest_slot:
    try:
        next_slot = datetime.fromisoformat(availabilities['next_slot'].replace('Z', '+00:00'))
        next_slot = next_slot.replace(tzinfo=None)
        debug_print(f"Found next_slot in response: {next_slot}")
        if earliest_slot is None or next_slot < earliest_slot:
            earliest_slot = next_slot
    except ValueError as e:
        debug_print(f"❌ Error parsing next_slot datetime: {str(e)}")

days_until_next_slot = None
if earliest_slot:
    days_until_next_slot = (earliest_slot - datetime.now()).days
    debug_print(f"\nSlot analysis summary:")
    debug_print(f"- Earliest available slot: {earliest_slot}")
    debug_print(f"- Days until slot: {days_until_next_slot}")
else:
    debug_print("\nNo valid slots found in any format")

slotInNearFuture = days_until_next_slot is not None and days_until_next_slot <= UPCOMING_DAYS
isOnTheHour = datetime.now().minute == 0
isHourlyNotificationDue = isOnTheHour and NOTIFY_HOURLY

debug_print(f"\nNotification decision breakdown:")
debug_print(f"- Found slots total: {availabilities.get('total', 0)}")
debug_print(f"- Earliest slot within {UPCOMING_DAYS} days: {slotInNearFuture}")
debug_print(f"- Days until earliest slot: {days_until_next_slot}")
debug_print(f"- Hourly notification due: {isHourlyNotificationDue}")
debug_print(f"- Debug mode: {DEBUG_MODE}")

should_exit = not (slotInNearFuture or isHourlyNotificationDue or DEBUG_MODE)
if should_exit:
    if DEBUG_MODE:
        if earliest_slot is None:
            debug_print("⛔ No appointments available at all")
        else:
            debug_print(f"⛔ Next appointment is in {days_until_next_slot} days (beyond {UPCOMING_DAYS} days threshold)")
    debug_print("⛔ Exiting - No notification needed")
    exit()

debug_print("\nBuilding notification message...")
message = ''
if APPOINTMENT_NAME:
    message += f'👨‍⚕️👩‍⚕️ {APPOINTMENT_NAME}'
    message += '\n'

if slotInNearFuture:
    message += f'🔥 Appointment available in {days_until_next_slot} days!'
    message += f' ({earliest_slot.strftime("%Y-%m-%d %H:%M")})'
    message += '\n'
    if MOVE_BOOKING_URL:
        message += f'<a href="{MOVE_BOOKING_URL}">🚚 Move existing booking</a>.'
        message += '\n'
elif DEBUG_MODE:
    if earliest_slot is None:
        message += f'🔍 Debug: No appointments available'
    else:
        message += f'🔍 Debug: Next appointment in {days_until_next_slot} days'
        message += f' ({earliest_slot.strftime("%Y-%m-%d %H:%M")})'
    message += '\n'

if isHourlyNotificationDue and earliest_slot:
    message += f'🐌 Next available: <i>{earliest_slot.strftime("%d %B %Y %H:%M")}</i>'
    message += '\n'

message += f'Book now on <a href="{BOOKING_URL}">doctolib.de</a>.'
debug_print(f"Final message: {message}")

debug_print("\nPreparing to send Telegram message...")
urlEncodedMessage = urllib.parse.quote(message)
telegram_url = (f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
                f'?chat_id={TELEGRAM_CHAT_ID}'
                f'&text={urlEncodedMessage}'
                f'&parse_mode=HTML'
                f'&disable_web_page_preview=true')
debug_print(f"Telegram API URL (token hidden): {telegram_url.replace(TELEGRAM_BOT_TOKEN, 'HIDDEN')}")

try:
    telegram_response = urllib.request.urlopen(telegram_url)
    debug_print(f"Telegram response status: {telegram_response.status}")
    debug_print(f"Message sent successfully!")
except Exception as e:
    debug_print(f"❌ Error sending Telegram message: {str(e)}")
    if DEBUG_MODE:
        debug_print("Full error details:")
        import traceback
        debug_print(traceback.format_exc())
