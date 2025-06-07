from io import BytesIO
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import os
import json
from types import CoroutineType, SimpleNamespace
import psycopg
import pytz
from datetime import datetime
import asyncio
import nest_asyncio
from requests.adapters import HTTPAdapter, Retry


class Config:
    
    class Group:
        id: str
        description: str
        lights: list[str]
        water_pumps: list[str]
        fans: list[str]
        sensors: list[str]
        cameras: list[str]
    
    groups: list[Group]    

#DB Connection and other variables involved
DATABASE_URL = f"postgres://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_CONTAINER_NAME')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()
timezone = pytz.timezone(os.getenv("TIMEZONE"))
current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")

#Telegram init
TOKEN = os.getenv("BOT_TOKEN")

#GPIO pins initialization
GPIO.setmode(GPIO.BCM)


#HTTP Connection Init
session = requests.Session()
retries = Retry(total=1)
session.mount('http://', HTTPAdapter(max_retries=retries))
async def sensor_and_display_monitoring(lcd: CharLCD, ip: str):
    lcd.write_string(f" ☾ · ⏾ · ࣪ ִֶָ☾. · ☽ · ☪︎ · ")
    lcd.write_string(f"piantagione")
    await asyncio.sleep(1.337)
    lcd.clear()
    # Define the GPIO pin for the sensor. The GPIO pin is hereby descripted in the for loop as a generic "sensor"  
    # Initialize the sensor and store the result in the sensor_init variable
    try:
        result_temperature = requests.get("http://"+ip+"/temperature")
        result_humidity = requests.get("http://"+ip+"/humidity")
        if result_temperature !=0.00:
            lcd.write_string(f"{float(result_temperature.content)} °C\n")
            await asyncio.sleep(10.337)

        if result_humidity !=0.00:
            lcd.write_string(f"{float(result_humidity.content)} %\n")
            await asyncio.sleep(10.337)
            lcd.write_string(f" ☾ · ⏾ · ࣪ ִֶָ☾. · ☽ · ☪︎ · ⋆.˚ ☾⭒.")
 
        else:
            lcd.write_string("Error in reading data")
        cur.execute("INSERT INTO sensors (ip,temperature, humidity, timestamp) VALUES (%s, %s, %s, %s)", ( ip,float(result_temperature.content),float(result_humidity.content), current_time))
        conn.commit()    
    except requests.exceptions.ConnectionError or OSError as e:
        print(e)
        lcd.write_string(f"Sensor \"{ip}\" not available")




async def sensor_controller(mode: str,ip: str) -> bool:
    # Define the GPIO pin for the sensor. The GPIO pin is hereby descripted in the for loop as a generic "ip"  
    # Initialize the sensor and store the result in the sensor_init variable
    try:
        result = requests.get("http://"+ip+"/"+mode)
        if mode=="temperature":
            return float(result.content)>float(os.getenv("TEMPERATURE_THRESHOLD")) #ALERT! TEMPERATURE > TEMPERATURE_THRESHOLD [C°]
        elif mode=="humidity":
            return float(result.content)>float(os.getenv("MOISTURE_THRESHOLD")) #ALERT! HUMIDITY> MOISTURE_THRESHOLD [%]
    except requests.exceptions.ConnectionError as e:
        print(e)
    
        
async def switch(ip: str, mode: str) -> bool:
    res = session.get("http://"+ip+"/"+mode, timeout=2)
    cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (ip, 1 if res.status_code==200 else 0, current_time))
    conn.commit() 
    return res.status_code==200 

async def force_start(cfg: Config,update: Update, context: CallbackContext):
    for group in cfg.groups:
        for light in group.lights:
            try:
                await switch(light, "on")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The light with this ip {light} belonging to the group \"{group.description}\"  has not started.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (light, 2 , current_time))
                conn.commit() 
                print(e)
                pass
        for water_pump in group.water_pumps:
            try:
                await switch(water_pump, "on")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The water pump with this ip {water_pump} belonging to the group \"{group.description}\"  has not started.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (water_pump, 2 , current_time))
                conn.commit() 
                print(e)
                pass
        for fan in group.fans:
            try:
                await switch(fan, "on")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The fan with this ip {fan} belonging to the group \"{group.description}\"  has not started.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (fan, 2 , current_time))
                conn.commit() 
                print(e)
                pass
    await update.message.reply_text(f"[*] Piantagione is up and running again!")


async def emergency_stop(cfg: Config, update: Update, context: CallbackContext):
    for group in cfg.groups:
        for light in group.lights:
            try:
                await switch(light, "off")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The light with this ip {light} belonging to the group \"{group.description}\"  has not stopped.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (light, 2 , current_time))
                conn.commit() 
                print(e)
                pass
        for water_pump in group.water_pumps:
            try:
                await switch(water_pump, "off")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The water pump with this ip {water_pump} belonging to the group \"{group.description}\"  has not stopped.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (water_pump, 2 , current_time))
                conn.commit() 
                print(e)
                pass
        for fan in group.fans:
            try:
                await switch(fan, "off")
            except requests.exceptions.ConnectionError as e:
                await update.message.reply_text(f"[!] DANGER!!! The fan with this ip {fan} belonging to the group \"{group.description}\"  has not stopped.\n")
                cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (fan, 2 , current_time))
                conn.commit() 
                print(e)
                pass
    await update.message.reply_text("[*] Piantagione is down.")



async def stats(cfg:Config,update: Update, context: CallbackContext):
    # Define the GPIO pin for the sensor. The GPIO pin is hereby descripted in the for loop as a generic "ip"  
    # Initialize the sensor and store the result in the sensor_init variable
    
    if not context.args and len(context.args) != 1:
        await update.message.reply_text(f"Don't try sending gibberish to confuse me, you hacker!")
    
    id = context.args[0]
    
    found = False
    for group in cfg.groups:
        if id == group.id:
            found = True
            if found:
                for sensor in group.sensors:
                    try:
                        result_temperature = session.get("http://"+sensor+"/temperature")
                        result_humidity = session.get("http://"+sensor+"/humidity")
                        if float(result_temperature.content) !=0.00 and  float(result_humidity.content) !=0.00:
                            await update.message.reply_text(f"Sensors read-outs:\n Temperature in C°:{float(result_temperature.content)} \n Humidity:  {float(result_humidity.content)} % \n of sensor belonging to ip: {sensor}")
                        else:
                            await update.message.reply_text("Error in reading data")
                        cur.execute("INSERT INTO sensors (ip, temperature, humidity, timestamp) VALUES (%s,%s, %s, %s)", ( sensor,float(result_temperature.content),float(result_humidity.content), current_time))
                        conn.commit()     
                    except requests.exceptions.ConnectionError as conn_e:
                        cur.execute("INSERT INTO loads (ip, status, timestamp) VALUES (%s, %s, %s)", (sensor, 2 , current_time))
                        conn.commit() 
                        await update.message.reply_text(f"Connection error with sensors: {sensor}")
                        pass
                    

            else:
                pass
            
    if not found:
        await update.message.reply_text(f"Don't try sending gibberish to confuse me, you hacker!")



async def send_picture_from_cam(cfg:Config, update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    file_dir="./images/image_"+current_time+"__"+str(chat_id)+"__.jpeg"
    for group in cfg.groups:
        for cam in group.cameras:
            try:
                res = session.get("http://"+cam+"/stream", stream=True, timeout=5)
                img_bytes = b""
                for chunk in res.iter_content(chunk_size=1024):
                    img_bytes += chunk
                    if b"\xff\xd9" in img_bytes: #JPEG end marker
                        break
                img_bytes = b'\n'.join(img_bytes.split(b'\n')[3:]) #Remove uncessary response headers from first three rows
                if res.status_code == 200:
                    directory = os.path.dirname(file_dir)
                    if not os.path.exists(directory):
                        os.makedirs(directory)

                    with open(file_dir, "wb") as fp:
                        fp.write(bytes(img_bytes))
                    print("Image downloaded successfully.", flush=True)
                else:
                    print(f"Failed to download the image")
                res.raise_for_status()
                await context.bot.send_photo(chat_id=chat_id, photo=(open(file_dir,"rb")))
                await update.message.reply_text(f"[*] Camera with ip \"{cam}\" output given")
            except requests.Timeout:
                await update.message.reply_text("Camera request timed out.")
            except requests.RequestException as e:
                await update.message.reply_text(f"[!] Camera error: {e}")
            except requests.exceptions.ConnectionError as conn_e:
                print("Connection Error")
            except Exception as e:
                print(e)


            
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Commands:\n/force_start\n/emergency_stop\n/stats - See sensors stats\n/help - to show this help lines.")

async def start_bot(config: Config):
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("help", help_command, block=False))
    application.add_handler(CommandHandler("cam", lambda a,b: send_picture_from_cam(config,a,b), block=False))
    application.add_handler(CommandHandler("force_start", lambda a,b: force_start(config,a,b), block=False))
    application.add_handler(CommandHandler("emergency_stop", lambda a,b: emergency_stop(config,a,b),block=False) )
    application.add_handler(CommandHandler("stats", lambda a,b: stats(config,a,b), block=False))
    await application.run_polling(poll_interval=0.1337,allowed_updates=Update.MESSAGE, drop_pending_updates=True)



async def start_routine(config:Config):
        for group in config.groups:
            for sensor in group.sensors:
                    lcd = CharLCD(i2c_expander=os.getenv("I2C_EXPANDER"), address=0x27, port=1, cols=16, rows=4, dotsize=10) #LCD initalization 
                    await sensor_and_display_monitoring(lcd,sensor)
                    if await sensor_controller("temperature",sensor)==True: #Temperature too high
                        for fan in group.fans:
                            try:
                                await switch(fan,"on")
                            except:
                                print(f"Error on turning off ip: {fan}",flush=True)
                        for light in group.lights:
                            try:    
                                await switch(light,"off") #Let the environment cool down a bit

                            except:
                                print(f"Error on turning off ip: {light}",flush=True)
                    if await sensor_controller("humidity",sensor)==True: #Humidity too high
                        for fan in group.fans:
                            try:
                                await switch(fan,"on")
                            except:
                                print(f"Error on turning on ip: {fan}",flush=True)
                        for light in group.lights:
                            try:    
                                await switch(light,"off") # Let the environment cool down a bit
                            except:
                                print(f"Error on turning off ip: {light}",flush=True)
                        for water_pump in group.water_pumps:
                            try:
                                await switch(water_pump,"off") #Maybe the water pump mulfunctioned and all the water sinked inside the greenhouse, making the humidity raise
                            except:
                                print(f"Error on turning off ip: {water_pump}",flush=True)
            for fan in group.fans:
                try:
                    await switch(fan,"off")
                except:
                    print(f"Error on turning off ip: {fan}",flush=True)

async def periodic(interval, coro, *args, **kwargs):
    while True:
        await asyncio.sleep(interval)
        await coro(*args, **kwargs)
async def main():
    nest_asyncio.apply()
    with open("config.json", "r") as f:
        config: Config = json.loads(f.read(), object_hook=lambda d: SimpleNamespace(**d))
    asyncio.create_task(periodic(1.337,start_routine,config))
    await start_bot(config)

                
if __name__ == "__main__":
    asyncio.run(main())    
