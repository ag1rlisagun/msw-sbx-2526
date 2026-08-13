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
 * ---------------------------------------------------------------------------
 * CHANGES IN THIS REVISION - ported from Sensors.ino (teammate's branch)
 * ---------------------------------------------------------------------------
 *   1. INA226 now reads the SHUNT VOLTAGE register (0x01) and computes
 *      current in software, instead of programming the calibration register
 *      and reading the current register (0x04). More robust - no calibration
 *      write to go wrong - and the shunt value lives in plain arithmetic
 *      where it is easy to correct. Also yields bus voltage and power.
 *   2. ina226ReadRegister() now reports success via a bool& out-parameter.
 *      Previously it returned 0 on failure, which is indistinguishable from
 *      a genuine 0 A / 0 V reading.
 *   3. handleDOCommands() null-terminates the buffer. readBytesUntil() does
 *      not do this itself, so a full buffer previously let parse_cmd() read
 *      past the end of the array.
 *   4. parse_cmd() uses String::toUpperCase() instead of strupr(). strupr is
 *      an MSVC extension and is not available on all avr-gcc toolchains.
 *   5. riskLevelStr() returns const __FlashStringHelper* instead of String,
 *      keeping the labels in flash and avoiding heap allocation in a loop
 *      that runs for the entire flight.
 *
 * NOT taken from Sensors.ino, deliberately:
 *   - Its unbounded `while (UVIndex240370Sensor.begin() != true)` init loop.
 *     That is the hang that cost nine days of silent downtime.
 *   - Its removal of waitForStart(). The Pi-side reader waits for READY and
 *     will loop on reconnect forever without it.
 *   - Its removal of the UV-C sensor.
 *   - Its `Serial.print(temperature, 0)`, which rounds to whole degrees.
 *   - Its non-ASCII degree and superscript characters in print strings.
 * ---------------------------------------------------------------------------
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
// INA226 I2C address is set by the A0/A1 pins. 0x40 = both tied to GND.
#define INA226_ADDRESS      0x40

// Register map
#define INA226_REG_CONFIG        0x00
#define INA226_REG_SHUNTVOLTAGE  0x01
#define INA226_REG_BUSVOLTAGE    0x02

// !! OPEN ITEM: VERIFY THIS AGAINST THE ACTUAL FLIGHT BOARD !!
// A wrong shunt value scales EVERY current reading by a fixed factor while
// looking entirely plausible - and current output is the primary science
// measurement. Read it off the board silkscreen or ask the electrical lead.
const float INA226_SHUNT_OHMS = 0.1f;

// Datasheet fixed scaling. These are properties of the chip, not the board,
// and should not need changing.
const float INA226_SHUNT_LSB_V = 2.5e-6f;    // 2.5 uV per LSB
const float INA226_BUS_LSB_V   = 0.00125f;   // 1.25 mV per LSB

bool ina226OK = false;

// =========================================================
// PAR SENSOR
// =========================================================
SoftwareSerial PARsensor(2, 3);
uint8_t Com[8] = { 0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x84, 0x0A };
int PAR = -1;

// Bounded retries. An unbounded loop here would hang the entire sketch -
// and therefore all six sensors - if the PAR sensor glitched mid-flight.
// Kept at 3 rather than the 10 in Sensors.ino: each attempt costs ~200 ms
// plus up to 4 x 500 ms of readN() timeouts, so 10 could push a single
// failed read past the 8 s watchdog window.
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
// !! OPEN ITEM: measured 4.5 V at this board's VCC while the sketch assumes
//    3.3 V. Check the VCC SEL jumper before trusting any UV-C reading.
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
// #define USE_PULSE_OUT
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
float readBusVoltage();
float readDO();
UVData readUV();
void readUVC(float &voltage, float &intensity);
void readPAR();
void handleDOCommands();
void parse_cmd(char* string);
const __FlashStringHelper* riskLevelStr(uint16_t level);
uint8_t readN(uint8_t *buf, size_t len);
unsigned int CRC16_2(unsigned char *buf, int len);
int16_t ina226ReadRegister(uint8_t reg, bool &ok);

// =========================================================
// SETUP
// =========================================================
void setup() {
  // Disable the watchdog first thing. If the board reset via watchdog, the
  // timer is still armed at its shortest interval - leaving it armed through
  // a slow init would cause a reset loop.
  wdt_disable();

  Serial.begin(115200);
  Wire.begin();

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

  // Read current and bus voltage once each, then derive power from the values
  // already in hand. Calling a separate readPower() that re-read both would
  // double the I2C traffic and sample the two quantities at different moments.
  float current    = readCurrent();
  float busVoltage = readBusVoltage();
  float power      = current * busVoltage;

  float do_value   = readDO();
  readPAR();
  UVData uvReading = readUV();
  float uvcVoltage, uvcIntensity;
  readUVC(uvcVoltage, uvcIntensity);

  Serial.print(F("Temp: "));          Serial.print(temperature, 2);    Serial.println(F(" C"));
  Serial.print(F("PAR: "));           Serial.print(PAR);                Serial.println(F(" umol/m2/s"));
  Serial.print(F("Current: "));       Serial.print(current, 5);         Serial.println(F(" A"));
  Serial.print(F("Bus Voltage: "));   Serial.print(busVoltage, 5);      Serial.println(F(" V"));
  Serial.print(F("Power: "));         Serial.print(power, 5);           Serial.println(F(" W"));
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
  // Presence check only. This revision reads the shunt voltage register
  // directly and scales it in software, so there is no calibration register
  // to program and nothing to configure at startup - the chip's default
  // continuous shunt-and-bus conversion mode is what we want.
  Wire.beginTransmission(INA226_ADDRESS);
  if (Wire.endTransmission() == 0) {
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
  // DE/RE pin setup lives here rather than in setup() so that everything
  // related to the PAR sensor is in one place.
  pinMode(DE_RE_PIN, OUTPUT);
  digitalWrite(DE_RE_PIN, LOW);

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
  // as a real reading previously caused the Pi-side heater controller to log
  // a continuous LOW warning - and would drive the heater to 100% duty once
  // MOSFET control is enabled.
  //
  // Tradeoff: a genuine 0.00 C reading is now indistinguishable from "no
  // sensor". Acceptable for a 20-25 C bioreactor.
  if (t == 0.0 || t < TEMP_VALID_MIN_C || t > TEMP_VALID_MAX_C) return -1.0;
  return t;
}

// Current from the shunt voltage register, scaled in software.
// I = V_shunt / R_shunt, where V_shunt = raw * 2.5 uV.
float readCurrent() {
  if (!ina226OK) return -1.0;

  bool ok = false;
  int16_t rawShunt = ina226ReadRegister(INA226_REG_SHUNTVOLTAGE, ok);
  if (!ok) return -1.0;

  float shuntVoltage = rawShunt * INA226_SHUNT_LSB_V;
  return shuntVoltage / INA226_SHUNT_OHMS;
}

// Bus voltage register is unsigned, 1.25 mV per LSB.
float readBusVoltage() {
  if (!ina226OK) return -1.0;

  bool ok = false;
  uint16_t rawBus = (uint16_t)ina226ReadRegister(INA226_REG_BUSVOLTAGE, ok);
  if (!ok) return -1.0;

  return rawBus * INA226_BUS_LSB_V;
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

  // Per the WHO Global Solar UV Index standard, 1 UV Index unit = 0.025 W/m2
  // (equivalently, UV Index = erythemal irradiance in W/m2 x 40).
  // The factor 0.025 is correct - do not change it.
  uvReading.watts   = uvReading.index * 0.025f;
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

// Bounded MODBUS read. Sets PAR to -1 if no valid frame arrives, rather than
// blocking the whole sketch until one does.
//
// Note this differs from Sensors.ino, which keeps the last known value on
// failure. A stale reading that looks current is worse for post-flight
// analysis than an obvious sentinel - the Pi logs every block, so a held
// value would be indistinguishable from a genuinely steady one.
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
// Reports success through `ok` rather than returning a sentinel value.
// 0 is a perfectly valid reading for both the shunt and bus registers, so a
// failed read could not otherwise be distinguished from a genuine zero.
int16_t ina226ReadRegister(uint8_t reg, bool &ok) {
  Wire.beginTransmission(INA226_ADDRESS);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    ok = false;
    return 0;
  }

  Wire.requestFrom(INA226_ADDRESS, 2);
  if (Wire.available() < 2) {
    ok = false;
    return 0;
  }

  uint16_t value = Wire.read() << 8;
  value |= Wire.read();
  ok = true;
  return (int16_t)value;
}

// =========================================================
// DO CALIBRATION COMMAND HANDLER
// =========================================================
void handleDOCommands() {
  if (Serial.available() > 0) {
    // Reserve one byte for the terminator. readBytesUntil() does not add one
    // itself, so a completely full buffer would leave parse_cmd() reading
    // past the end of the array.
    user_bytes_received = Serial.readBytesUntil(13, user_data, sizeof(user_data) - 1);
    user_data[user_bytes_received] = '\0';
    parse_cmd(user_data);
    user_bytes_received = 0;
    memset(user_data, 0, sizeof(user_data));
  }
}

void parse_cmd(char* string) {
  // toUpperCase() rather than strupr(). strupr is an MSVC extension and is
  // not present on every avr-gcc toolchain; a String is being constructed
  // here anyway, so this costs nothing.
  String cmd = String(string);
  cmd.toUpperCase();

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
// Returns a flash-resident string rather than a heap-allocated String.
// These labels are fixed constants, and allocating them every loop iteration
// risks heap fragmentation over a flight-length run on a 2 KB machine.
const __FlashStringHelper* riskLevelStr(uint16_t level) {
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
