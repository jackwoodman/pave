import Adafruit_BMP.BMP085 as BMP085

# @

bmp_sensor = BMP085.BMP085()

def get_temp():
	return bmp_sensor.read_temperature()

def get_press_local():
	return bmp_sensor.read_pressure()

def get_alt():
	return bmp_sensor.read_altitude()

def get_press_sea():
	return bmp_sensor.read_sealevel_pressure()
