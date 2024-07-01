from machine import Pin, I2C, ADC
import time
import mcp23017
import dht
from I2C_LCD import I2CLcd
from rotary_irq_rp2 import RotaryIRQ
import network
from simple import MQTTClient

i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
mcp = mcp23017.MCP23017(i2c, 0x20)  #Create an object for using the chip
mcp[7].output(1)
mcp[8].output(1)

#DHT-11
dht11_inside = dht.DHT11(Pin(16))
dht11_outside = dht.DHT11(Pin(17))

#Soil
soil_moisture_analog = ADC(Pin(26))
soil_moisture_digital = Pin(15, Pin.IN)

#Light sensor
light_sensor = ADC(27)

#screen
i2c_screen = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
devices = i2c_screen.scan()
lcd = I2CLcd(i2c_screen, devices[0], 2, 16)

#Rotary
sw=Pin(18,Pin.IN,Pin.PULL_UP) #btn
rotary= RotaryIRQ(21,20)

#Wifi
ssid = 'Honor8'
password = 'xxxx'
ADAFRUIT_IO_USERNAME = "xxxx"
ADAFRUIT_IO_KEY      = "xxxx"
ADAFRUIT_IO_FEED = 'DanielLundberg/feeds/temp'

def connect():
    #Connect to WLAN
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        time.sleep(1)
    print(wlan.ifconfig())

def mqtt_connect():
    client = MQTTClient('umqtt_client', 'io.adafruit.com', user=ADAFRUIT_IO_USERNAME, password=ADAFRUIT_IO_KEY)
    client.connect()
    print('Ansluten till Adafruit IO')
    return client

def publish_temperature(client, temperature):
    client.publish(ADAFRUIT_IO_FEED, str(temperature))
    print(f'Temperatur {temperature} skickad till {ADAFRUIT_IO_FEED}')
    
#variables
light_timer = 0
plant_sleep_time = 3600*6 #6 hour sleep time
water_timer_pause = 3600 # 1h
water_timer = 20 # 20 sek
water = False
seconds = 0

def rotary_button_pressed(pin): #for testing
    if rotary.value() > 0:
        if mcp[7].value() == 0:
            mcp[7].value(1)
        else:
            mcp[7].value(0)
    else:
        if mcp[8].value() == 0:
            mcp[8].value(1)
        else:
            mcp[8].value(0)

sw.irq(trigger=Pin.IRQ_FALLING, handler=rotary_button_pressed)

connect()
while True:
    moisture_value = soil_moisture_analog.read_u16()
    moisture_percent = (moisture_value / 65535) * 100
    moisture_status = soil_moisture_digital.value()
    
    #print("Soil Moisture Level (analog): {:.2f}%".format(moisture_percent))
    #print("Soil Moisture Status (digital): {}".format('Wet' if moisture_status == 0 else 'Dry'))
     
    light = light_sensor.read_u16()
    #print("Ljusvärde: {}".format(light))
    try:
        dht11_inside.measure()  # Ta en mätning
        temp = dht11_inside.temperature()  # Läs temperatur
        hum = dht11_inside.humidity()  # Läs luftfuktighet
      #  print('Temperature inside: {}°C  Humidity: {}%'.format(temp, hum))
        lcd.move_to(0, 0)
        lcd.putstr("Temperatur: {}".format(temp))
        lcd.putchar(chr(223))
        lcd.putstr("C")
        lcd.move_to(0, 1)
        lcd.putstr("Fuktighet : {} %".format(hum))
        dht11_outside.measure()  # Ta en mätning
        temp_outside = dht11_outside.temperature()  # Läs temperatur
        hum_outside = dht11_outside.humidity()  # Läs luftfuktighet
       # print('Temperature outside: {}°C  Humidity: {}%'.format(temp_outside, hum_outside))
    except:
        print('Failed to read sensor.')
    
    if light_timer == -1:
        plant_sleep_time -=1
        if plant_sleep_time ==0:
            light_timer =0
            plant_sleep_timer = 6*3600
            
    if light_timer > 0:
       light_timer -= 1
       if light_timer == 0:
            light_timer == -1
            mcp[8].value(1) #turn off relay 2
       
    if light_sensor.read_u16() < 800 and light_timer == 0: #when darkness enter
        light_timer = 3600*2 # 2 h of light
        mcp[8].value(0) #turn on relay 2   
        print("TURNED ON LIGHT")
        
    if water == True:
        water_timer -=1
    else:
        water_timer_pause -=1
        if water_timer_pause < 0:
            water_timer_pause = 0
    
    if water_timer == 0:
        water == False
        mcp[7].value(1) #turn off
    
    if water_timer_pause == 0 and moisture_percent < 80:
        mcp[7].value(0) #turn off
        water_timer = 20
        water = True
        water_timer_pause = 3600
         
    time.sleep(1)

    if seconds % 300 == 0: # each 5 min
        if wlan.isconnected() == False:
            connect()
        client = mqtt_connect()
        publish_temperature(client, temp)
        client.disconnect()
    
    seconds += 1
    
    if seconds % 10 == 0:
        print("Seconds: {}".format(seconds))

