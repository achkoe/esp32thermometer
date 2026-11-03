/*
Measure temperature and humidity using AHT10 sensor and an ESP32
*/
#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_AHT10.h>
/*
_secrets.h contains
const char* mqtt_server -> IP Address of MQTT server
const int mqtt_port     -> Port of MQTT server
const char* ssid        -> SSID of Wifi net
const char* password    -> Password for WiFi net
*/
#include "_secrets.h"


const char* client_name = "ESP32Thermometer";

Adafruit_AHT10 aht;             // the class for AHT10 sensor
sensors_event_t humidity, temp; // used to retrieve data from AHT10
bool aht_ready;                 // indicated if AHT10 is available
uint8_t wifi_status;            
bool mqtt_connected = false;
bool deep_sleep_enabled;
unsigned long tstart;           // variable to hold a time value
uint32_t vbat = 0;              // batterie voltage
String mac_address;             // MAC address of ESP32

WiFiClient espClient;
PubSubClient client(espClient);

#define WIFI_TIMEOUT 10000          // Timeout for WiFi
#define MQTT_TIMEOUT 10000          // Timeout for MQTT
#define uS_TO_S_FACTOR 1000000ULL   // Conversion factor for micro seconds to seconds 
#define TIME_TO_SLEEP  60           // Time span for ESP32 to sleep (in seconds) 
#define ENABLE_DEEP_SLEEP D6        // Pull pin to low to disable deep sleep

/*
Send ESP32 to deep sleep if deep_sleep_enabled is true.
*/
void deep_sleep(bool deep_sleep_enabled) {
    if (deep_sleep_enabled) {
        esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
        esp_deep_sleep_start();
    }
}

/*
Get temperature, humidity and batterie voltage.
*/
void getData() {
    if (aht_ready) {
        aht.getEvent(&humidity, &temp); 
    } else {
        temp.temperature = 0.0;
        humidity.relative_humidity = 0.0;
    }
    vbat = analogReadMilliVolts(A0);
}


void setup() {
    // switch buildin LED off
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    // get pin indicating deep sleep enabled
    pinMode(ENABLE_DEEP_SLEEP, INPUT_PULLUP);
    deep_sleep_enabled = digitalRead(ENABLE_DEEP_SLEEP) == HIGH;
    
    // set analog in 0 to input
    pinMode(A0, INPUT);

    Serial.begin(115200);

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    // wait maximum WIFI_TIMEOUT for connecting to Wifi
    wifi_status = WiFi.waitForConnectResult(WIFI_TIMEOUT); 
    if (wifi_status != WL_CONNECTED) {
        deep_sleep(deep_sleep_enabled);
    } 
    // get MAC address of ESP32
    mac_address = WiFi.macAddress();

    // get data to transmit
    aht_ready = aht.begin();
    getData();

    // connect to MQTT broker, if not possible goto deep sleep if enableb
    client.setServer(mqtt_server, mqtt_port);
    tstart = millis();
    while (!(mqtt_connected = client.connected())) {
        if (!client.connect(client_name)) {
            if (millis() - tstart > MQTT_TIMEOUT) {
                deep_sleep(deep_sleep_enabled);
                break;
            }
        } 
        delay(100);
    }

    String addrbase;
    if (mqtt_connected) {
        addrbase = mac_address + String("/aht/vbat");
        client.publish(addrbase.c_str(), String(vbat).c_str());
        addrbase = mac_address + String("/aht/millis");
        client.publish(addrbase.c_str(), String(tstart).c_str());
        addrbase = mac_address + String("/aht/temperature");
        client.publish(addrbase.c_str(), String(temp.temperature, 1).c_str());
        addrbase = mac_address + String("/aht/humidity");
        client.publish(addrbase.c_str(), String(humidity.relative_humidity, 1).c_str());
        delay(1000);
    }
    if (deep_sleep_enabled) {
        client.disconnect();
    }

    deep_sleep(deep_sleep_enabled);
}

void loop() {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    getData();
    if (Serial) {
        Serial.print("wifi: ");
        Serial.println(wifi_status);
        Serial.print("mqtt: ");
        Serial.println(mqtt_connected);
        Serial.print("aht: ");
        Serial.println(aht_ready);
        Serial.print("temperature: ");
        Serial.print(temp.temperature);
        Serial.println("°C");
        Serial.print("humidity: ");
        Serial.print(humidity.relative_humidity);
        Serial.println("%");
        Serial.print("vbat: ");
        Serial.println(vbat);
        Serial.print("MAC: ");
        Serial.println(mac_address);
        Serial.println();
    }
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);
}
