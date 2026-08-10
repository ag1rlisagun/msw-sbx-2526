/*
 * Combinedsensors.ino - MSW CAN-SBX 2025-2026
 *
 * Reads all six flight sensors and streams them to the Raspberry Pi over
 * USB serial. The Pi parses this output in
 * src/sensors/real/arduino_serial_reader.py and logs it to SQLite.
 *
 * NOTE ON HEATER: this sketch does NOT control the heater. It reads and
 * reports only. The heater MOSFET gate is on the Pi (GPIO12), so heater
 * control is Pi-side using the temperature streamed from here. See
 * src/actuators/heater_controller.py and src/config.py.
 *
 * SENSORS:
 *   Temperature  DS18B20             1-Wire, digital pin 5
 *   Current      INA226              I2C 0x40
 *   Dissolved O2 Atlas Surveyor      analog pin A0
 *   PAR          SenseCAP S-PAR      RS-485 MODBUS, SoftwareSerial 2/3, DE/RE pin 4
 *   UV Index     DFRobot SEN0636     I2C 0x23
 *   UV-C         MikroE UVC Click    I2C 0x4D (MCP3221)
 *
 * IMPORTANT - keep the Serial.print() wording below in sync with _PARSERS in
 * src/sensors/real/arduino_serial_reader.py. The Pi matches on these literal
 * strings. If the wording changes and _PARSERS is not updated, that field
 * silently stops being logged - no error is raised.
 *
 * CHANGES IN THIS REVISION:
 *   1. readTemperature() now rejects exactly 0.0 as a sentinel. A missing
 *      DS18B20 reads 0.00 with this library, which previously passed the
 *      validity clamp and would have driven the Pi-side heater controller
 *      to full duty on a phantom reading.
 *   2. Added the AVR watchdog. If any read blocks for more than 8 seconds
 *      the board resets itself rather than wedging for the rest of the
 *      flight. Addresses TR5 (Software Failure).
 */

#include <SoftwareSerial.h>
#include "DFRobot_UVIndex240370Sensor.h"
#include <Wire.h>
#include <DS18B20.h>
#include <avr/wdt.h>

// =========================================================
// PIN DEFINITIONS
// =========================================================
#define DE_RE_PIN           4     // MAX485 direction control (PAR sensor)
#define TEMP_SENSOR_PIN     5     // DS18B20 1-Wire

// =========================================================
// WATCHDOG
// =========================================================
// Nominal loop time is ~2.2 s with all sensors responding, ~3.3 s when
// PAR is timing out. 8 s leaves comfortable margin while still catching a
// genuine hang quickly.
#define WATCHDOG_TIMEOUT    WDTO_8S

// =========================================================
// INA226 CURRENT SENSOR
// =========================================================
// !! VERIFY THESE AGAINST THE ACTUAL FLIGHT BOARD BEFORE TRUSTING READINGS !!
//
// INA226 I2C address is set by the A0/A1 pins. 0x40 = both tied to GND.
#define INA226_ADDRESS      0x40

// Shunt resistor value in ohms. Most INA226 breakouts ship with 0.1 ohm.
// A wrong value here scales EVERY current reading by a fixed factor while
// looking entirely plausible - and current output is the primary science
// measurement. Confirm against the board silkscreen before flight.
const float INA226_SHUNT_OHMS = 0.1;

// Current_LSB sets resolution. 10 uA/bit gives a full-scale range of
// 10e-6 * 32768 = 0.327 A, covering the ~20-25 mA from the fuel cell plus
// baseline electronics draw.
const float INA226_CURRENT_LSB = 0.00001;   // amps per bit

#define INA226_REG_CONFIG        0x00
#define INA226_REG_SHUNTVOLTAGE  0x01
#define INA226_REG_BUSVOLTAGE    0x02
#define INA226_REG_CURRENT       0x04
#define INA226_REG_CALIBRATION   0x05

bool ina226OK = false;

// =========================================================
// PAR SENSOR
// =========================================================
SoftwareSerial PARsensor(2, 3);
uint8_t Com[8] = { 0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x84, 0x0A };
int PAR = -1;

// Bounded retries. An unbounded loop here would hang the entire sketch -
// and therefore all six sensors - if the PAR sensor glitched mid-flight.
const int PAR_MAX_ATTEMPTS = 3;

// =========================================================
// UV INDEX SENSOR (SEN0636)
// =========================================================
DFRobot_UVIndex240370Sensor UVIndex240370Sensor(&Wire);
bool uvOK = false;
const int UV_INIT_MAX_ATTEMPTS = 5;

struct UVData {
  uint16_t voltage;
  uint16_t index;
  uint16_t level;
  float    watts;
};

// =========================================================
// UV-C SENSOR (MikroE UVC Click / MCP3221)
// =========================================================
#define UVC_I2C_ADDRESS        0x4D
const float UVC_VCC                = 3.3;
const float UVC_CALIBRATION_FACTOR = 2.9;

// =========================================================
// TEMPERATURE SENSOR
// =========================================================
DS18B20 tempSensor(TEMP_SENSOR_PIN);

// A disconnected DS18B20 reads exactly 0.00 with this library (other
// libraries return ~-127). Neither is a plausible bioreactor temperature.
// Both map to the -1.0 sentinel so the Pi-side heater controller can
// recognise "no data" rather than acting on a phantom reading.
const float TEMP_VALID_MIN_C = -50.0;
const float TEMP_VALID_MAX_C = 100.0;

// =========================================================
// ATLAS DO SENSOR
// =========================================================
#define USE_PULSE_OUT
#ifdef USE_PULSE_OUT
  #include "do_iso_surveyor.h"
  Surveyor_DO_Isolated DO = Surveyor_DO_Isolated(A0);
#else
  #include "do_surveyor.h"
  Surveyor_DO DO = Surveyor_DO(A0);
#endif

uint8_t user_bytes_received = 0;
const uint8_t bufferlen = 32;
char user_data[bufferlen];

// =========================================================
// HANDSHAKE
// =========================================================
// Bounded wait, so the sketch still works with a plain serial monitor or
// if the Pi-side handshake is unavailable.
const unsigned long START_TIMEOUT_MS = 15000;

// =========================================================
// FORWARD DECLARATIONS
// =========================================================
void initUVSensor();
void initDOSensor();
void initPARSensor();
void initINA226();
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
void ina226WriteRegister(uint8_t reg, uint16_t value);
bool ina226ReadRegister(uint8_t reg, uint16_t &value);

// =========================================================
// SETUP
// =========================================================
void setup() {
  // Disable the watchdog first thing. If the board reset via watchdog, the
  // timer is still armed and running at its shortest interval - leaving it
  // armed through a slow init would cause a reset loop.
  wdt_disable();

  Serial.begin(115200);
  Wire.begin();
  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);

  initUVSensor();
  initINA226();
  initDOSensor();
  initPARSensor();

  Serial.println(F("DO Commands: \"CAL\" or \"CAL,CLEAR\""));
  Serial.println(F("All sensors initialized."));

  waitForStart();

  // Arm the watchdog only after all init and the handshake are done.
  wdt_enable(WATCHDOG_TIMEOUT);

  Serial.println(F("---"));
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  wdt_reset();

  handleDOCommands();

  float temperature = readTemperature();
  float current     = readCurrent();
  float do_value    = readDO();
  readPAR();
  UVData uvReading  = readUV();
  float uvcVoltage, uvcIntensity;
  readUVC(uvcVoltage, uvcIntensity);

  Serial.print(F("Temp: "));          Serial.print(temperature, 2);    Serial.println(F(" C"));
  Serial.print(F("PAR: "));           Serial.print(PAR);                Serial.println(F(" umol/m2/s"));
  Serial.print(F("Current: "));       Serial.print(current, 5);         Serial.println(F(" A"));
  Serial.print(F("DO: "));            Serial.print(do_value, 2);        Serial.println(F(" %"));
  Serial.print(F("UV Voltage: "));    Serial.print(uvReading.voltage);  Serial.println(F(" mV"));
  Serial.print(F("UV Index: "));      Serial.println(uvReading.index);
  Serial.print(F("UV Irradiance: ")); Serial.print(uvReading.watts, 3); Serial.println(F(" W/m2"));
  Serial.print(F("Risk Level: "));    Serial.println(riskLevelStr(uvReading.level));
  Serial.print(F("UVC Voltage: "));   Serial.print(uvcVoltage, 5);      Serial.println(F(" V"));
  Serial.print(F("UVC Intensity: ")); Serial.print(uvcIntensity, 5);    Serial.println(F(" mW/cm2"));
  Serial.println(F("---"));

  delay(1000);
}

// =========================================================
// HANDSHAKE - wait for the Pi, but do not wait forever
// =========================================================
void waitForStart() {
  Serial.println(F("READY"));
  unsigned long deadline = millis() + START_TIMEOUT_MS;
  while (millis() < deadline) {
    if (Serial.available() > 0) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      if (cmd == "START") {
        Serial.println(F("Handshake complete."));
        return;
      }
    }
  }
  Serial.println(F("No START received - streaming anyway."));
}

// =========================================================
// INIT FUNCTIONS
// =========================================================
void initUVSensor() {
  for (int i = 0; i < UV_INIT_MAX_ATTEMPTS; i++) {
    if (UVIndex240370Sensor.begin() == true) {
      uvOK = true;
      Serial.println(F("UV Sensor initialized."));
      return;
    }
    delay(500);
  }
  uvOK = false;
  Serial.println(F("UV Sensor init failed - continuing without it."));
}

void initINA226() {
  //   [11:9]  010  AVG    = 16 samples
  //   [8:6]   100  VBUSCT = 1.1 ms
  //   [5:3]   100  VSHCT  = 1.1 ms
  //   [2:0]   111  MODE   = shunt + bus, continuous
  const uint16_t config = 0x4527;

  // CAL = 0.00512 / (Current_LSB * R_shunt)
  uint16_t cal = (uint16_t)(0.00512 / (INA226_CURRENT_LSB * INA226_SHUNT_OHMS));

  ina226WriteRegister(INA226_REG_CONFIG, config);
  ina226WriteRegister(INA226_REG_CALIBRATION, cal);

  uint16_t readback = 0;
  if (ina226ReadRegister(INA226_REG_CONFIG, readback) && readback == config) {
    ina226OK = true;
    Serial.println(F("INA226 initialized."));
  } else {
    ina226OK = false;
    Serial.println(F("INA226 not detected! Check wiring/address."));
  }
}

void initDOSensor() {
  delay(200);
  if (DO.begin()) {
    Serial.println(F("DO Sensor EEPROM loaded."));
  } else {
    Serial.println(F("DO Sensor initialize failed!"));
  }
  DO.read_do_percentage();   // discard first reading, let the probe settle
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
  tempSensor.doConversion();
  float t = tempSensor.getTempC();

  // Exactly 0.0 means no sensor on the bus with this library. Treating it
  // as a real reading previously caused the Pi-side heater controller to
  // log a continuous LOW warning - and would have driven the heater to
  // 100% duty once MOSFET control is enabled.
  //
  // Tradeoff: a genuine 0.00 C reading is now indistinguishable from "no
  // sensor". Acceptable for a 20-25 C bioreactor.
  if (t == 0.0 || t < TEMP_VALID_MIN_C || t > TEMP_VALID_MAX_C) return -1.0;
  return t;
}

float readCurrent() {
  if (!ina226OK) return -1.0;

  uint16_t raw = 0;
  if (!ina226ReadRegister(INA226_REG_CURRENT, raw)) return -1.0;

  int16_t signedRaw = (int16_t)raw;   // two's complement
  return signedRaw * INA226_CURRENT_LSB;
}

float readDO() {
  return DO.read_do_percentage();
}

UVData readUV() {
  UVData uvReading;

  if (!uvOK) {
    uvReading.voltage = 0;
    uvReading.index   = 0;
    uvReading.level   = 0;
    uvReading.watts   = -1.0;
    return uvReading;
  }

  uvReading.voltage = UVIndex240370Sensor.readUvOriginalData();
  uvReading.index   = UVIndex240370Sensor.readUvIndexData();
  uvReading.level   = UVIndex240370Sensor.readRiskLevelData();
  uvReading.watts   = uvReading.index * 0.025;
  return uvReading;
}

void readUVC(float &voltage, float &intensity) {
  Wire.requestFrom(UVC_I2C_ADDRESS, 2);
  if (Wire.available() == 2) {
    uint8_t b0 = Wire.read();
    uint8_t b1 = Wire.read();
    uint16_t adc = ((b0 & 0x0F) << 8) | b1;   // 12-bit, top nibble masked
    voltage = (adc / 4096.0) * UVC_VCC;
    intensity = voltage * UVC_CALIBRATION_FACTOR;
  } else {
    voltage = -1.0;
    intensity = -1.0;
  }
}

void readPAR() {
  PARsensor.listen();
  uint8_t Data[10] = { 0 };
  uint8_t ch = 0;

  for (int attempt = 0; attempt < PAR_MAX_ATTEMPTS; attempt++) {
    delay(100);
    digitalWrite(DE_RE_PIN, HIGH);
    delay(1);
    PARsensor.write(Com, 8);
    PARsensor.flush();
    digitalWrite(DE_RE_PIN, LOW);
    delay(100);

    if (readN(&ch, 1) == 1 && ch == 0x01) {
      Data[0] = ch;
      if (readN(&ch, 1) == 1 && ch == 0x03) {
        Data[1] = ch;
        if (readN(&ch, 1) == 1 && ch == 0x02) {
          Data[2] = ch;
          if (readN(&Data[3], 4) == 4) {
            if (CRC16_2(Data, 5) == (Data[5] * 256 + Data[6])) {
              PAR = Data[3] * 256 + Data[4];
              PARsensor.flush();
              return;
            }
          }
        }
      }
    }
    PARsensor.flush();
  }

  PAR = -1;   // no valid response after all attempts
}

// =========================================================
// INA226 LOW-LEVEL I2C
// =========================================================
void ina226WriteRegister(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(reg);
  Wire.write((value >> 8) & 0xFF);
  Wire.write(value & 0xFF);
  Wire.endTransmission();
}

bool ina226ReadRegister(uint8_t reg, uint16_t &value) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) return false;

  Wire.requestFrom(INA226_ADDRESS, 2);
  if (Wire.available() != 2) return false;

  uint8_t hi = Wire.read();
  uint8_t lo = Wire.read();
  value = ((uint16_t)hi << 8) | lo;
  return true;
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
