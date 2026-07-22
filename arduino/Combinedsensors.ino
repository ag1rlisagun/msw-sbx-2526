#include <SoftwareSerial.h>
#include "DFRobot_UVIndex240370Sensor.h"
#include <Wire.h>
#include <DS18B20.h>

// ===== Pin Definitions =====
#define DE_RE_PIN           4
#define CURRENT_SENSOR_PIN  A2
#define TEMP_SENSOR_PIN     5

// ===== ACS723 Current Sensor Config =====
const float SUPPLY_V        = 5.0;
const float SENSITIVITY     = 0.400;
const float ZERO_CURRENT_V  = SUPPLY_V / 2.0;
const int   CURRENT_SAMPLES = 100;

// ===== PAR Sensor Config =====
SoftwareSerial PARsensor(2, 3);
uint8_t Com[8] = { 0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x84, 0x0A };
int PAR;

// ===== UV Sensor =====
DFRobot_UVIndex240370Sensor UVIndex240370Sensor(&Wire);

// ===== UV-C Sensor (MikroE UVC Click, MCP3221 ADC) =====
// Shares the same I2C bus (Wire) as the UV Index sensor above.
// NOTE: verify this address doesn't collide with any other I2C device
// on the Arduino's bus before flight (SEN0636 is on 0x23, this is 0x4D).
#define UVC_I2C_ADDRESS        0x4D
const float UVC_VCC                = 3.3;
const float UVC_CALIBRATION_FACTOR = 2.9;

// ===== UV Data Struct =====
struct UVData {
  uint16_t voltage;
  uint16_t index;
  uint16_t level;
  float    watts;
};

// ===== Temperature Sensor =====
DS18B20 tempSensor(TEMP_SENSOR_PIN);

// ===== Atlas DO Sensor =====
// #define USE_PULSE_OUT
#ifdef USE_PULSE_OUT
  #include "do_iso_surveyor.h"
  Surveyor_DO_Isolated DO = Surveyor_DO_Isolated(A0);
#else
  #include "do_surveyor.h"
  Surveyor_DO DO = Surveyor_DO(A0);
#endif

// ===== DO Command Buffer =====
uint8_t user_bytes_received = 0;
const uint8_t bufferlen = 32;
char user_data[bufferlen];

// =========================================================
// FORWARD DECLARATIONS
// =========================================================
void initUVSensor();
void initDOSensor();
void initPARSensor();
void waitForStart();
float readTemperature();
float readCurrent();
float readDO();
UVData readUV();
void readUVC(float &voltage, float &intensity);
void readPAR();
void handleDOCommands();
void parse_cmd(char* string);
String riskLevelStr(uint16_t level);
uint8_t readN(uint8_t *buf, size_t len);
unsigned int CRC16_2(unsigned char *buf, int len);

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(115200);
  Wire.begin();
  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);

  initUVSensor();
  initDOSensor();
  initPARSensor();

  Serial.println(F("DO Commands: \"CAL\" or \"CAL,CLEAR\""));
  Serial.println(F("All sensors initialized."));

  // Wait for the Pi to connect and send START before entering loop().
  // This ensures no sensor data is printed before the Pi is listening.
  waitForStart();

  Serial.println(F("---"));
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  handleDOCommands();

  float temperature     = readTemperature();
  float current         = readCurrent();
  float do_value        = readDO();
  readPAR();
  UVData uvReading      = readUV();
  float uvcVoltage, uvcIntensity;
  readUVC(uvcVoltage, uvcIntensity);

  Serial.print(F("Temp: "));          Serial.print(temperature, 2);      Serial.println(F(" °C"));
  Serial.print(F("PAR: "));           Serial.print(PAR);                  Serial.println(F(" umol/m²·s"));
  Serial.print(F("Current: "));       Serial.print(current, 3);           Serial.println(F(" A"));
  Serial.print(F("DO: "));            Serial.print(do_value, 2);          Serial.println(F(" %"));
  Serial.print(F("UV Voltage: "));    Serial.print(uvReading.voltage);    Serial.println(F(" mV"));
  Serial.print(F("UV Index: "));      Serial.println(uvReading.index);
  Serial.print(F("UV Irradiance: ")); Serial.print(uvReading.watts, 3);   Serial.println(F(" W/m²"));
  Serial.print(F("Risk Level: "));    Serial.println(riskLevelStr(uvReading.level));
  Serial.print(F("UVC Voltage: "));   Serial.print(uvcVoltage, 5);        Serial.println(F(" V"));
  Serial.print(F("UVC Intensity: ")); Serial.print(uvcIntensity, 5);      Serial.println(F(" mW/cm2"));
  Serial.println(F("---"));

  delay(1000);
}

// =========================================================
// HANDSHAKE — wait for Pi to send "START"
// =========================================================
void waitForStart() {
  Serial.println(F("READY"));
  while (true) {
    if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      if (cmd == "START") return;
    }
  }
}

// =========================================================
// INIT FUNCTIONS
// =========================================================
void initUVSensor() {
  while (UVIndex240370Sensor.begin() != true) {
    Serial.println(F("UV Sensor initialize failed, retrying..."));
    delay(1000);
  }
  Serial.println(F("UV Sensor initialized."));
}

void initDOSensor() {
  delay(200);
  if (DO.begin()) {
    Serial.println(F("DO Sensor EEPROM loaded."));
  } else {
    Serial.println(F("DO Sensor initialize failed!"));
  }
  DO.read_do_percentage(); // discard first reading to allow probe to settle
  delay(1000);
}

void initPARSensor() {
  PARsensor.begin(9600);
  PARsensor.listen();
  Serial.println(F("PAR Sensor initialized."));
}

// =========================================================
// SENSOR READ FUNCTIONS
// =========================================================
float readTemperature() {
  // DS18B20 not yet connected — returns placeholder
  // TODO: uncomment these lines once sensor is wired up
  // tempSensor.doConversion();
  // return tempSensor.getTempC();
  return -1.0;
}

float readCurrent() {
  long adcSum = 0;
  for (int i = 0; i < CURRENT_SAMPLES; i++) {
    adcSum += analogRead(CURRENT_SENSOR_PIN);
    delay(1);
  }
  float adcAvg = adcSum / (float)CURRENT_SAMPLES;
  float volts  = (adcAvg / 1023.0) * SUPPLY_V;
  return (volts - ZERO_CURRENT_V) / SENSITIVITY;
}

float readDO() {
  return DO.read_do_percentage();
}
//For debugging
/* float readDO() {
  int raw = analogRead(A0);
  Serial.print(F("DO Raw ADC: "));
  Serial.println(raw);
  return DO.read_do_percentage();
}*/

UVData readUV() {
  UVData uvReading;
  uvReading.voltage = UVIndex240370Sensor.readUvOriginalData();
  uvReading.index   = UVIndex240370Sensor.readUvIndexData();
  uvReading.level   = UVIndex240370Sensor.readRiskLevelData();
  uvReading.watts   = uvReading.index * 0.025;
  return uvReading;
}

// NEW: UV-C sensor read (MikroE UVC Click / MCP3221 12-bit ADC over I2C).
// Same protocol as sensors/real/uvc_sensor.py on the Pi: request 2 bytes,
// mask the top nibble of the first byte, combine to a 12-bit value.
void readUVC(float &voltage, float &intensity) {
  Wire.requestFrom(UVC_I2C_ADDRESS, 2);
  if (Wire.available() == 2) {
    uint8_t b0 = Wire.read();
    uint8_t b1 = Wire.read();
    uint16_t adc = ((b0 & 0x0F) << 8) | b1;   // 12-bit, top nibble masked
    voltage = (adc / 4096.0) * UVC_VCC;
    intensity = voltage * UVC_CALIBRATION_FACTOR;
  } else {
    // Sensor not responding — report a sentinel the Pi-side parser can
    // still log without crashing (matches the -1.0 placeholder pattern
    // used elsewhere in this sketch, e.g. readTemperature()).
    voltage = -1.0;
    intensity = -1.0;
  }
}

void readPAR() {
  PARsensor.listen();
  uint8_t Data[10] = { 0 };
  uint8_t ch = 0;
  bool flag = true;
  while (flag) {
    delay(100);
    digitalWrite(DE_RE_PIN, HIGH);
    delay(1);
    PARsensor.write(Com, 8);
    PARsensor.flush();
    digitalWrite(DE_RE_PIN, LOW);
    delay(100);
    if (readN(&ch, 1) == 1) {
      if (ch == 0x01) {
        Data[0] = ch;
        if (readN(&ch, 1) == 1) {
          if (ch == 0x03) {
            Data[1] = ch;
            if (readN(&ch, 1) == 1) {
              if (ch == 0x02) {
                Data[2] = ch;
                if (readN(&Data[3], 4) == 4) {
                  if (CRC16_2(Data, 5) == (Data[5] * 256 + Data[6])) {
                    PAR = Data[3] * 256 + Data[4];
                    flag = false;
                  }
                }
              }
            }
          }
        }
      }
    }
    PARsensor.flush();
  }
}

// =========================================================
// DO CALIBRATION COMMAND HANDLER
// =========================================================
void handleDOCommands() {
  if (Serial.available() > 0) {
    user_bytes_received = Serial.readBytesUntil(13, user_data, sizeof(user_data));
    parse_cmd(user_data);
    user_bytes_received = 0;
    memset(user_data, 0, sizeof(user_data));
  }
}

void parse_cmd(char* string) {
  strupr(string);
  String cmd = String(string);
  if (cmd.startsWith("CAL")) {
    int i = cmd.indexOf(',');
    if (i != -1) {
      String param = cmd.substring(i + 1);
      if (param.equals("CLEAR")) {
        DO.cal_clear();
        Serial.println(F("Calibration cleared."));
      }
    } else {
      DO.cal();
      Serial.println(F("DO calibrated."));
    }
  }
}

// =========================================================
// HELPERS
// =========================================================
String riskLevelStr(uint16_t level) {
  switch (level) {
    case 0:  return F("Low");
    case 1:  return F("Moderate");
    case 2:  return F("High");
    case 3:  return F("Very High");
    case 4:  return F("Extreme");
    default: return F("Unknown");
  }
}

uint8_t readN(uint8_t *buf, size_t len) {
  size_t offset = 0, left = len;
  uint8_t *buffer = buf;
  long curr = millis();
  while (left) {
    if (PARsensor.available()) {
      buffer[offset++] = PARsensor.read();
      left--;
    }
    if (millis() - curr > 500) break;
  }
  return offset;
}

unsigned int CRC16_2(unsigned char *buf, int len) {
  unsigned int crc = 0xFFFF;
  for (int pos = 0; pos < len; pos++) {
    crc ^= (unsigned int)buf[pos];
    for (int i = 8; i != 0; i--) {
      if ((crc & 0x0001) != 0) { crc >>= 1; crc ^= 0xA001; }
      else                      { crc >>= 1; }
    }
  }
  crc = ((crc & 0x00ff) << 8) | ((crc & 0xff00) >> 8);
  return crc;
}
