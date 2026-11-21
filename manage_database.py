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


# DB stuff
DBNAME = "esp32thermometer.db"
DBPATH = pathlib.Path().joinpath("/", "opt", "esp32thermometer", DBNAME)
TABLE_NAME = "esp32thermometer"
DBFIELDS = dict(
    time=dict(db="REAL"), 
    temperature=dict(db="REAL"), 
    humidity=dict(db="REAL"), 
    source=dict(db="TEXT")
)
DBVALUES = ", ".join(f":{key}" for key in DBFIELDS)

# logging stuff
loglevel = int(dotenv_values(".env").get("LOGLEVEL", logging.CRITICAL))
logging.basicConfig(format="%(levelname)s:%(asctime)s:%(lineno)d:%(message)s", level=loglevel)
LOGGER = logging.getLogger()

# mqtt stuff
SOURCE_MAP = {
    "10:BD:A3:8F:7B:64": dict(location="garden")
}
[SOURCE_MAP[key].update(dict(tablename=f't{key.replace(":", "_")}')) for key in SOURCE_MAP]
QOS = 0
TOPIC = [(f"{mac}/aht/{key}", QOS) for mac in SOURCE_MAP for key in ("millis", "temperature", "humidity", "vbat")]
BROKER_ADDRESS = "127.0.0.1" 
PORT = 1883 


def create_database():
    DBPATH.parent.mkdir(parents=True, exist_ok=True)
    
    # sqlite stuff
    connection = sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = connection.cursor()
    for key in SOURCE_MAP:
        tablename = SOURCE_MAP[key]["tablename"]
        s = ",".join(f"{key} {DBFIELDS[key]['db']}" for key in DBFIELDS)    
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {tablename} ({s})")
        s = ",".join(DBFIELDS)
        # avoid writing duplicate items
        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uniquedata ON {tablename} ({s})")
        # create trigger to delete items older than 1 year
        cursor.execute(f"""CREATE TRIGGER IF NOT EXISTS deletelastyear AFTER INSERT ON {tablename}
                    BEGIN
                    DELETE FROM {tablename} WHERE (julianday('now') - julianday(time, 'unixepoch')) > 365;
                    END
                    """)
        print(f"Database {DBPATH} created with table {tablename}")
    connection.commit()


def read_database(args):
    tablenames = [SOURCE_MAP[key]["tablename"] for key in (SOURCE_MAP if args.source is None else (args.source, ))]
    limit = f"LIMIT {args.number_to_read}" if args.number_to_read is not None else ""
    connection=sqlite3.connect(DBPATH, detect_types=sqlite3.PARSE_DECLTYPES)
    connection.row_factory = sqlite3.Row
    cursor=connection.cursor()
    for tablename in tablenames:
        cursor.execute(f"SELECT * FROM {tablename} ORDER BY time DESC {limit}")
        for item in cursor.fetchall():
            time = datetime.datetime.fromtimestamp(item["time"]).isoformat(sep='T', timespec='seconds')
            print(f'{time} {item["temperature"]:5.1f}°C {item["humidity"]:5.1f}%')


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

    tablename = SOURCE_MAP[source]["tablename"]
    data = userdata.payload.setdefault(source, dict())
    data[key] = msg
    if data.get("temperature", None) is not None and data.get("humidity", None) is not None:
        data["time"] = time.time()
        data["source"] = source
        LOGGER.info(f"db <- time: {data['time']}, temperature: {data['temperature']}, humidity: {data['humidity']}: source: {source}")
        userdata.cursor.execute(f"INSERT OR IGNORE INTO {tablename} VALUES ({DBVALUES})", data)
        userdata.connection.commit()
        userdata.payload[source] = dict()


if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--create", action="store_true", help="create database")
    group.add_argument("--read", action="store_true", help="read database")
    group.add_argument("--write", action="store_true", help="write to database (use in service)")
    parser.add_argument("--number", "-n", type=int, dest="number_to_read", default=None, help="number of items to read from database")
    parser.add_argument("--source", "-s", choices=list(SOURCE_MAP.keys()), help="which source to show, default all")
    args = parser.parse_args()
    if args.create is True:
        create_database()
    elif args.read is True:
        read_database(args)
    elif args.write is True:
        write_database()
    else:
        print(args)
