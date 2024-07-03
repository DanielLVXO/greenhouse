from machine import Pin, I2C, ADC
import time
import network
import dht

#External libs
from I2C_LCD import I2CLcd
from rotary_irq_rp2 import RotaryIRQ
import mcp23017
from simple import MQTTClient
import credentials

i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)
mcp = mcp23017.MCP23017(i2c, 0x20)  #Create an object for using the chip
mcp[7].output(1)
mcp[8].output(1)

#DHT-11
dht11_inside = dht.DHT11(Pin(16))
dht11_outside = dht.DHT11(Pin(17))

#Soil
soil_moisture_analog = ADC(Pin(26))
soil_moisture_digital = Pin(15, Pin.IN) #Not used in this project

#Light sensor
light_sensor = ADC(27)

#screen
i2c_screen = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
devices = i2c_screen.scan()
lcd = I2CLcd(i2c_screen, devices[0], 2, 16)

#Rotary
sw=Pin(18,Pin.IN,Pin.PULL_UP) #btn
rotary= RotaryIRQ(21,20)

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

#Wifi
ADAFRUIT_IO_FEED_TEMP = 'DanielLundberg/feeds/temp'
ADAFRUIT_IO_FEED_TEMP_OUT = 'DanielLundberg/feeds/tempout'

def connect():
    #Connect to WLAN
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(credentials.ssid, credentials.password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        time.sleep(1)
    print(wlan.ifconfig())

def mqtt_connect():
    client = MQTTClient('umqtt_client', 'io.adafruit.com', user=credentials.ADAFRUIT_IO_USERNAME, password=credentials.ADAFRUIT_IO_KEY)
    client.connect()
    print('Ansluten till Adafruit IO')
    return client

def publish_temperature(client, temperature_greenhouse,temperature_outside):
    client.publish(ADAFRUIT_IO_FEED_TEMP, str(temperature_greenhouse))
    print(f'Temperatur {temperature_greenhouse} skickad till {ADAFRUIT_IO_FEED_TEMP}')
    time.sleep(1)
    client.publish(ADAFRUIT_IO_FEED_TEMP_OUT, str(temperature_outside))
    print(f'Temperatur {temperature_outside} skickad till {ADAFRUIT_IO_FEED_TEMP_OUT}')
    
#variables
light_timer = 0
plant_sleep_time = 3600*6 #6 hour sleep time
water_timer_pause = 3600 # 1h
water_timer = 20 # 20 sek
water = False
seconds = 0

connect() #Connect to Wifi
while True:
    #Soil Moisture sensor
    moisture_value = soil_moisture_analog.read_u16()
    moisture_percent = (moisture_value / 65535) * 100
    moisture_status = soil_moisture_digital.value()
     
    #Light Sensor
    light = light_sensor.read_u16()

    try:
        dht11_inside.measure()  # Messure dht11
        temp = dht11_inside.temperature()  # Read temperaure inside greenhouse
        hum = dht11_inside.humidity()  # Read humidity inside greenhouse
        
        #Present on screen
        lcd.move_to(0, 0)
        lcd.putstr("Temperatur: {}".format(temp))
        lcd.putchar(chr(223))
        lcd.putstr("C")
        lcd.move_to(0, 1)
        lcd.putstr("Fuktighet : {} %".format(hum))
        
        dht11_outside.measure()  # messure dht11 (outside)
        temp_outside = dht11_outside.temperature()  # Read temperaure outside greenhouse
        hum_outside = dht11_outside.humidity()  # Read humidity outside greenhouse    
    except:
        print('Failed to read sensor.')
    
    #Controlling light
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
    
    #controlling water-pump
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
  
    #Send data to Adafruit
    if seconds % 300 == 0: # each 5 min
        if wlan.isconnected() == False:
            connect()
        client = mqtt_connect()
        publish_temperature(client, temp,temp_outside)
        client.disconnect() 
    seconds += 1
