\#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define TRIG D1
#define ECHO D2

LiquidCrystal_I2C lcd(0x27, 16, 2);

const char* ssid = "PLDTWIFIjaip";
const char* password = "EXAMPle123";
const char* serverName = "http://127.0.0.1:5000";

float floodThreshold = 20.0;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);

  lcd.init();
  lcd.backlight();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void loop() {

  // ---- ULTRASONIC ----
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  long duration = pulseIn(ECHO, HIGH);
  float distance = duration * 0.034 / 2;

  // ---- LM35 ----
  int sensorValue = analogRead(A0);
  float voltage = sensorValue * (3.3 / 1023.0);
  float temperature = voltage * 100.0;

  // ---- LCD ----
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Water:");
  lcd.print(distance);
  lcd.print("cm");

  lcd.setCursor(0,1);
  lcd.print("Temp:");
  lcd.print(temperature);
  lcd.print("C");

  if(distance <= floodThreshold){
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("!!! FLOOD !!!");
  }

  // ---- SEND TO SERVER ----
  if(WiFi.status()== WL_CONNECTED){
    WiFiClient client;
    HTTPClient http;
    http.begin(client, serverName);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"distance\":" + String(distance) + 
                  ",\"temperature\":" + String(temperature) + "}";

    http.POST(json);
    http.end();
  }

  delay(5000);
}
