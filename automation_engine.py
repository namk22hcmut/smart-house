import os
import time
import logging
import signal
import requests
from datetime import datetime
from pymongo import MongoClient

# Configuration (can be overridden by environment variables)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("SMART_HOME_DB", "SmartHome_DB")
SLEEP_INTERVAL = int(os.getenv("AUTOMATION_INTERVAL", "10"))

# Adafruit IO configuration (optional)
AIO_USERNAME = os.getenv("AIO_USERNAME")
AIO_KEY = os.getenv("AIO_KEY")
# Specific feed keys for temperature/humidity (set these in env)
AIO_FEED_TEMPERATURE = os.getenv("AIO_FEED_TEMPERATURE")
AIO_FEED_HUMIDITY = os.getenv("AIO_FEED_HUMIDITY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("automation_engine")

OPERATORS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def connect_db(uri=MONGO_URI, db_name=DB_NAME):
    client = MongoClient(uri)
    return client[db_name]


def get_latest_value(db, sensor_type):
    doc = db["sensor_data"].find_one({"type": sensor_type}, sort=[("timestamp", -1)])
    return doc.get("value") if doc else None


def fetch_adafruit_feed(feed_key):
    """Fetch latest value from Adafruit IO feed via REST API. Returns numeric value or None."""
    if not (AIO_USERNAME and AIO_KEY and feed_key):
        return None
    url = f"https://io.adafruit.com/api/v2/{AIO_USERNAME}/feeds/{feed_key}/data?limit=1"
    headers = {"X-AIO-Key": AIO_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        val = data[0].get("value")
        # try convert to float/int
        try:
            if isinstance(val, str) and val.isdigit():
                return int(val)
            return float(val)
        except Exception:
            return val
    except Exception:
        logger.debug("Adafruit fetch failed for %s", feed_key, exc_info=True)
        return None


def fetch_and_store_adafruit_data(db):
    """Fetch configured Adafruit feeds and insert into `sensor_data` collection."""
    now_ts = int(time.time())
    # Temperature
    t_val = fetch_adafruit_feed(AIO_FEED_TEMPERATURE)
    if t_val is not None:
        try:
            db["sensor_data"].insert_one({"type": "Temperature", "value": t_val, "timestamp": now_ts})
            logger.info("Saved Temperature from Adafruit: %s", t_val)
        except Exception:
            logger.exception("Failed to save Temperature to DB")
    # Humidity
    h_val = fetch_adafruit_feed(AIO_FEED_HUMIDITY)
    if h_val is not None:
        try:
            db["sensor_data"].insert_one({"type": "Humidity", "value": h_val, "timestamp": now_ts})
            logger.info("Saved Humidity from Adafruit: %s", h_val)
        except Exception:
            logger.exception("Failed to save Humidity to DB")


def evaluate_condition(cond, t_val, h_val):
    sensor = cond.get("sensor_type")
    operator = cond.get("operator")
    threshold = cond.get("threshold_value")

    if operator not in OPERATORS:
        logger.warning("Unknown operator %s", operator)
        return False

    if sensor == "Temperature":
        current_val = t_val
    elif sensor == "Humidity":
        current_val = h_val
    else:
        logger.warning("Unsupported sensor type %s", sensor)
        return False

    if current_val is None:
        return False

    try:
        return OPERATORS[operator](current_val, threshold)
    except Exception:
        logger.exception("Error evaluating condition %s", cond)
        return False


def execute_actions(db, rule_name, actions):
    for action in actions:
        device_id = action.get("device_id")
        cmd = action.get("action_command", "").upper()
        if "TURN_ON" in cmd or cmd == "ON":
            status = "ON"
        elif "TURN_OFF" in cmd or cmd == "OFF":
            status = "OFF"
        else:
            status = "ON" if cmd in ("1", "TRUE") else "OFF"

        try:
            db["devices"].update_one({"device_id": device_id}, {"$set": {"status": status}})
            logger.info("%s: set %s -> %s", rule_name, device_id, status)
        except Exception:
            logger.exception("Failed to update device %s for rule %s", device_id, rule_name)


running = True


def stop_handler(signum, frame):
    global running
    logger.info("Stopping automation engine (signal %s)", signum)
    running = False


def run_loop():
    db = connect_db()
    logger.info("Connected to DB %s", DB_NAME)

    while running:
        try:
            logger.debug("Checking automation rules...")
            t_val = get_latest_value(db, "Temperature")
            h_val = get_latest_value(db, "Humidity")

            if t_val is None or h_val is None:
                logger.warning("Missing sensor data (temp=%s, humi=%s)", t_val, h_val)
            else:
                logger.info("Current values: Temp=%s, Humi=%s", t_val, h_val)

                rules = db["automation_rules"].find({"is_active": True})
                for rule in rules:
                    logic = (rule.get("logic_operator") or "AND").upper()
                    conditions = rule.get("conditions", [])
                    results = [evaluate_condition(c, t_val, h_val) for c in conditions]

                    should_activate = all(results) if logic == "AND" else any(results)

                    if should_activate:
                        execute_actions(db, rule.get("rule_name", "<unnamed>"), rule.get("actions", []))
                    else:
                        logger.debug("Rule %s not triggered", rule.get("rule_name"))

        except Exception:
            logger.exception("Unexpected error in automation loop")

        time.sleep(SLEEP_INTERVAL)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)
    try:
        run_loop()
    finally:
        logger.info("Automation engine stopped")