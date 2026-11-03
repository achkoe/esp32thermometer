"""Sample for thermometer"""

import logging
from time import gmtime, strftime
from types import SimpleNamespace
import paho.mqtt.enums as enums
import paho.mqtt.client as mqtt 


logging.basicConfig(format="%(levelname)s:%(asctime)s:%(message)s", level=logging.INFO)
LOGGER = logging.getLogger()


QOS = 0
TOPIC = [(f"10:BD:A3:8F:7B:64/aht/{key}", QOS) for key in ("millis", "temperature", "humidity", "vbat")]

BROKER_ADDRESS = "127.0.0.1" 
PORT = 1883 


def on_message(client, userdata, message): 
    t = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    msg = str(message.payload.decode("utf-8")) 
    key = message.topic
    print(f"{t}: {key} -> {msg}")
    
    
def on_connect(client, userdata, flags, rc, properties): 
    LOGGER.info(f"Connected to MQTT Broker {BROKER_ADDRESS}") 
    client.subscribe(TOPIC) 
    
    
if __name__ == "__main__": 
        
    # set userdata for paho client
    userdata = SimpleNamespace()
    # mqtt stuff
    client = mqtt.Client(enums.CallbackAPIVersion(2), userdata=userdata) 
    client.on_connect = on_connect 
    client.on_message = on_message 
    client.connect(BROKER_ADDRESS, PORT) 
    client.loop_forever()