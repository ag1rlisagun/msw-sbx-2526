import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import time

# Create the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create the ADC object using the I2C bus
ads = ADS.ADS1115(i2c)

# Create single-ended input on channel 3
chan = AnalogIn(ads, ADS.P3)

# Known values
R1 = 4700  # 4.7k ohms pull-up resistor
Vin = 3.3    # Supply voltage, adjust according to your setup

def read_average(channel, sample_time=1):
    values = []
    voltages = []
    start_time = time.time()
    
    while time.time() - start_time < sample_time:
        values.append(channel.value)
        voltages.append(channel.voltage)
        time.sleep(0.1)  # Delay as you've found beneficial
    
    avg_value = sum(values) / len(values)
    avg_voltage = sum(voltages) / len(voltages)
    
    return avg_value, avg_voltage

def calculate_resistance(avg_voltage):
    if avg_voltage >= Vin:
        return "Invalid reading, voltage too high"
    elif avg_voltage <= 0:
        return "Invalid reading, voltage too low"
    else:
        R2 = R1 * (avg_voltage / (Vin - avg_voltage))
        return R2

try:
    while True:
        avg_value, avg_voltage = read_average(chan)
        resistance = calculate_resistance(avg_voltage)
        if isinstance(resistance, str):
            print(resistance)
        else:
            print(f"AIN3 Average Raw Value: {avg_value:.2f}, Average Voltage: {avg_voltage:.4f}V, Calculated Resistance: {resistance / 1000:.2f}k ohms")
except KeyboardInterrupt:
    print("Program stopped")
