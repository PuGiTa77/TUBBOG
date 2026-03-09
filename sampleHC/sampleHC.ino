#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>

#define TRIG D1
#define ECHO D2

// WIFI SETTINGS
const char* ssid = "RK";
const char* password = "T0ny4ndR0my";

// FLASK SERVER
const char* server = "http://192.168.1.248:8000/update";//this depends on the wifi your connected to 

// FLOOD WARNING LEVEL (cm)
const float floodLevel = 20.0;

long duration;
float distance;

// ---------------- WIFI SETUP CONNECTION----------------
void connectWiFi() {

  Serial.print("Connecting to WiFi");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

// ---------------- ----------------
float readDistance() {

  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  duration = pulseIn(ECHO, HIGH, 30000);

  if (duration == 0) {
    return -1; // no echo received
  }

  float d = duration * 0.034 / 2;//converts time to distance

  if (d <= 0 || d > 400) {
    return -1;
  }

  return d;
}

// ---------------- DATA TRANSMISSION ----------------
void sendData(float distance) {

  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;

  http.begin(client, server);
  http.addHeader("Content-Type", "application/json");

  String json = "{\"distance\":" + String(distance) + "}";

  int httpResponseCode = http.POST(json);

  Serial.print("HTTP Response: ");
  Serial.println(httpResponseCode);

  http.end();
}

// ---------------- SERIAL MONITOR SETUP ----------------
void setup() {

  Serial.begin(115200);

  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);

  connectWiFi();
}

// ---------------- ENDLESS LOOP----------------
void loop() {

  distance = readDistance();

  if (distance > 0) {

    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");

    if (distance < floodLevel) {
      Serial.println("⚠ FLOOD WARNING");
    }
    else {
      Serial.println("✓ Water level normal");
    }

    sendData(distance);

  } 
  else {

    Serial.println("Sensor error.");
  }

  Serial.println("----------------------");

  delay(3000);
}