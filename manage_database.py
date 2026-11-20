"""Read/write/create sqlite2 database for date from esp32 thermometer"""

import logging
import argparse
from types import SimpleNamespace
import datetime
import time
import sqlite3
import pathlib
from dotenv import dotenv_values
#from sendemail import email
import paho.mqtt.enums as enums
import paho.mqtt.client as mqtt 


def timestamp(datetimestr):
    return datetime.datetime.fromisoformat(datetimestr).timestamp()

# DB stuff
DBNAME = "esp32thermometer.db"
DBPATH = pathlib.Path().joinpath("/", "opt", "esp32thermometer", DBNAME)
TABLE_NAME = "esp32thermometer"
DBFIELDS = dict(
    time=dict(db="REAL", cfn=timestamp), 
    temperature=dict(db="REAL", cfn=float), 
    humidity=dict(db="REAL", cfn=float), 
    source=dict(db="TEXT", cfn=str)
)
DBVALUES = ", ".join(f":{key}" for key in DBFIELDS)

# logging stuff
loglevel = int(dotenv_values(".env").get("LOGLEVEL", logging.CRITICAL))
logging.basicConfig(format="%(levelname)s:%(asctime)s:%(lineno)d:%(message)s", level=loglevel)
LOGGER = logging.getLogger()

# mqtt stuff
QOS = 0
TOPIC = [(f"10:BD:A3:8F:7B:64/aht/{key}", QOS) for key in ("millis", "temperature", "humidity", "vbat")]
BROKER_ADDRESS = "127.0.0.1" 
PORT = 1883 


def _on_message(client, userdata, message): 
    msg = str(message.payload.decode("utf-8")) 
    key = message.topic.split("/")[-1]
    
    # LOGGER.critical(f"{key}: {msg}")
    
    if key == "battery_ok":
        if msg != "1" and (userdata.last_email_send_date is None or time.time() - userdata.last_email_send_date > 24 * 60 * 60):
            # send email if battery is low every 24 hours
            email_subject = "Warning: weatherstation battery is low"
            email_message = f"Please change weatherstation battery!\nmsg={msg!r}"
            email(email_subject, email_message)
            userdata.last_email_send_date = time.time()
            LOGGER.critical(email_subject)
        return
        
    if key == "time":
        userdata.count += 1
    LOGGER.info(f"message {userdata.count}/{LENGTH} received: {msg!r}, topic: {message.topic}") 
    userdata.data[key].append(DBFIELDS[key]["cfn"](msg))
    #
    if all([len(item) >= LENGTH for item in userdata.data.values()]):
        for key in userdata.data:
            if key == "time":
                userdata.data["time"] = userdata.data["time"][-1]
                # find the time 1 day before
                twentyfour_before = userdata.data["time"] - 24 * 60 * 60
                userdata.cursor.execute(f"SELECT rain_mm FROM weather WHERE time <= ? ORDER BY time DESC LIMIT 1", (twentyfour_before, ))
                userdata.rain_mm_reference = cursor.fetchone()[0]
                LOGGER.info(f"rain reference -> {userdata.rain_mm_reference}")
            else:
                userdata.data[key] = sum(userdata.data[key][:LENGTH]) / LENGTH
                if key == "rain_mm" and userdata.rain_mm_reference is not None:
                    rain_per_day_mm = userdata.data[key] - userdata.rain_mm_reference
                    LOGGER.info(f"rain per day -> {rain_per_day_mm}")
                    userdata.cursor.execute("UPDATE rain_per_day SET rain_per_day_mm = ? WHERE idx = 0", (rain_per_day_mm, ))
        LOGGER.critical(f"db <- {userdata.data}")
        userdata.cursor.execute(f"INSERT OR IGNORE INTO weather VALUES ({DBVALUES})", userdata.data)
        userdata.connection.commit()
        for key in userdata.data:
            userdata.data[key] = [] 
        userdata.count = 0
    
    
def _on_connect(client, userdata, flags, rc, properties): 
    LOGGER.info(f"Connected to MQTT Broker {BROKER_ADDRESS}") 
    client.subscribe(TOPIC) 
    

def old():    
    # sqlite stuff
    connection = sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = connection.cursor()
    s = ",".join(f"{key} {DBFIELDS[key]['db']}" for key in DBFIELDS)    
    cursor.execute(f"CREATE TABLE IF NOT EXISTS weather ({s})")
    s = ",".join(DBFIELDS)
    # avoid writing duplicate items
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uniquedata ON weather ({s})")
    # create trigger to delete items older than 1 year
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS deletelastyear AFTER INSERT ON weather
                   BEGIN
                   DELETE FROM weather WHERE (julianday('now') - julianday(time, 'unixepoch')) > 365;
                   END
                   """)
    cursor.execute("CREATE TABLE IF NOT EXISTS rain_per_day (idx INT, rain_per_day_mm REAL)")
    connection.commit()
        
    # set userdata for paho client
    userdata = SimpleNamespace(cursor=cursor, connection=connection, data=dict((key, []) for key in DBFIELDS), rain_mm_reference=None, count=0, last_email_send_date=None)
    # mqtt stuff
    client = mqtt.Client(enums.CallbackAPIVersion(2), userdata=userdata) 
    client.on_connect = on_connect 
    client.on_message = on_message 
    client.connect(BROKER_ADDRESS, PORT) 
    client.loop_forever()


def create_database():
    DBPATH.parent.mkdir(parents=True, exist_ok=True)
    
    # sqlite stuff
    connection = sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = connection.cursor()
    s = ",".join(f"{key} {DBFIELDS[key]['db']}" for key in DBFIELDS)    
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({s})")
    s = ",".join(DBFIELDS)
    # avoid writing duplicate items
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uniquedata ON {TABLE_NAME} ({s})")
    # create trigger to delete items older than 1 year
    cursor.execute(f"""CREATE TRIGGER IF NOT EXISTS deletelastyear AFTER INSERT ON {TABLE_NAME}
                   BEGIN
                   DELETE FROM {TABLE_NAME} WHERE (julianday('now') - julianday(time, 'unixepoch')) > 365;
                   END
                   """)
    connection.commit()


def read_database():
    connection=sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor=connection.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY time DESC")
    for item in cursor.fetchall():
        print(item)


def write_database():
    connection=sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor=connection.cursor()
    client = mqtt.Client(enums.CallbackAPIVersion(2), userdata=SimpleNamespace(
        payload=dict(),
        connection=connection,
        cursor=cursor
    )) 
    client.on_connect = on_connect 
    client.on_message = on_message 
    client.connect(BROKER_ADDRESS, PORT) 
    client.loop_forever()


def on_connect(client, userdata, flags, rc, properties): 
    LOGGER.info(f"Connected to MQTT Broker {BROKER_ADDRESS}") 
    client.subscribe(TOPIC) 


def on_message(client, userdata, message): 
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    msg = str(message.payload.decode("utf-8")) 
    source, _, key = message.topic.split("/")
    LOGGER.info(f"{t}: {source}|{key} -> {msg}")

    data = userdata.payload.setdefault(source, dict())
    data[key] = msg
    if data.get("temperature", None) is not None and data.get("humidity", None) is not None:
        data["time"] = time.time()
        data["source"] = source
        LOGGER.info(f"db <- time: {data['time']}, temperature: {data['temperature']}, humidity: {data['humidity']}: source: {source}")
        userdata.cursor.execute(f"INSERT OR IGNORE INTO {TABLE_NAME} VALUES ({DBVALUES})", data)
        userdata.connection.commit()
        userdata.payload[source] = dict()


if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--create", action="store_true", help="create database")
    group.add_argument("--read", action="store_true", help="read database")
    group.add_argument("--write", action="store_true", help="write to database (use in service)")
    args = parser.parse_args()
    if args.create is True:
        create_database()
    elif args.read is True:
        read_database()
    elif args.write is True:
        write_database()
