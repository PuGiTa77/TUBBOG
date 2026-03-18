#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>

// WIFI
const char* ssid = "RK";
const char* password = "T0ny4ndR0my";

// FLASK SERVER
const char* server = "http://192.168.1.248:5000/data";

// ----------- PINS -----------

// Sensor 1
#define TRIG1 D1
#define ECHO1 D2

// Sensor 2
#define TRIG2 D6
#define ECHO2 D7

// Sensor 3
#define TRIG3 D0
#define ECHO3 D8

// Flow sensor
#define FLOW_PIN D5

volatile int pulseCount = 0;

// ---------- INTERRUPT ----------
void IRAM_ATTR countPulse() {
  pulseCount++;
}

// ---------- DISTANCE FUNCTION ----------
float getDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);

  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  long duration = pulseIn(echo, HIGH, 30000);

  if (duration == 0) return -1;

  float d = duration * 0.034 / 2;

  if (d <= 0 || d > 400) return -1;

  return d;
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.println(WiFi.localIP());

  // Ultrasonic pins
  pinMode(TRIG1, OUTPUT);
  pinMode(ECHO1, INPUT);

  pinMode(TRIG2, OUTPUT);
  pinMode(ECHO2, INPUT);

  pinMode(TRIG3, OUTPUT);
  pinMode(ECHO3, INPUT);

  // Flow sensor
  pinMode(FLOW_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), countPulse, RISING);
}

// ---------- LOOP ----------
void loop() {

  float d1 = getDistance(TRIG1, ECHO1);
  float d2 = getDistance(TRIG2, ECHO2);
  float d3 = getDistance(TRIG3, ECHO3);

  // Flow
  detachInterrupt(digitalPinToInterrupt(FLOW_PIN));
  float flowRate = pulseCount / 7.5;
  pulseCount = 0;
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), countPulse, RISING);

  // Print
  Serial.println("------");

  Serial.print("Sensor 1: ");
  Serial.println(d1);

  Serial.print("Sensor 2: ");
  Serial.println(d2);

  Serial.print("Sensor 3: ");
  Serial.println(d3);

  Serial.print("Flow: ");
  Serial.print(flowRate);
  Serial.println(" L/min");

  // Send to Flask
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    http.begin(client, server);
    http.addHeader("Content-Type", "application/json");

    String json = "{";
    json += "\"s1\":" + String(d1) + ",";
    json += "\"s2\":" + String(d2) + ",";
    json += "\"s3\":" + String(d3) + ",";
    json += "\"flow\":" + String(flowRate);
    json += "}";

    int response = http.POST(json);

    Serial.print("HTTP: ");
    Serial.println(response);

    http.end();
  }

  delay(2000);
}