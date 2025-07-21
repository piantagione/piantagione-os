import shlex
import telegram
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
from datetime import datetime, time as dt_time, timedelta
import asyncio
import time
import nest_asyncio
from requests.adapters import HTTPAdapter, Retry
import subprocess


class Config:
    class Group:
        def __init__(self,id,description,lights,water_pumps,fans,sensors,cameras):
            self.id = id 
            self.description = description
            self.lights = lights
            self.water_pumps = water_pumps
            self.fans = fans
            self.sensors = sensors
            self.cameras = cameras  
    def __init__(self, groups):
        self.groups = groups
    def to_dict(self):
        return {"groups": [group.__dict__ for group in self.groups]} 

#DB Connection and other variables involved
DATABASE_URL = f"postgres://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_CONTAINER_NAME')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
conn = psycopg.connect(DATABASE_URL)
cur = conn.cursor()
timezone = pytz.timezone(os.getenv("TIMEZONE"))
current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")

#Plantation init
seedling_end_time =  datetime.now(timezone) + timedelta(days=int(os.getenv("SEEDLING_DAYS")))
vegetative_end_time =  datetime.now(timezone) + timedelta(days=int(os.getenv("VEGETATIVE_DAYS")))
summer = False
night = False

#Telegram init
TOKEN = os.getenv("BOT_TOKEN")
id = os.getenv("CHAT_ID")

#GPIO pins initialization
GPIO.setmode(GPIO.BCM)


#HTTP Connection Init
session = requests.Session()
retries = Retry(total=1)
session.mount('http://', HTTPAdapter(max_retries=retries))


#Telegram init
application = Application.builder().token(TOKEN).build()
context=CallbackContext(application=application)

#Config init
with open("config.json", "r") as f:
    config: Config = json.loads(f.read(), object_hook=lambda d: SimpleNamespace(**d))


def is_summer()->bool:
    if 5 or 6 or 7 or 8 or 9 or 10 in datetime.date(datetime.now(timezone)):
        summer = True
        return summer

def is_night()->bool:
    time_ = datetime.now(timezone).time()
    if  time_ >=  dt_time(21,00) and time_ <= dt_time(5,00):
        night = True
        return night


async def callback_alert(context: CallbackContext):
    ips = get_connected_loads()
    try:
        for ip in ips:
            res = session.get("http://"+ip+"/whoami", timeout=2)
            if res.ok:  
                if res.content == b'T&H':
                    await context.bot.send_message(id,f"New temperature and humidity sensor attached!: {ip}")
                elif res.content == b'L':
                    await context.bot.send_message(id,f"New light attached!: {ip}")
                elif res.content == b'WP':
                    await context.bot.send_message(id,f"New water pump attached!: {ip}")
                elif res.content == b'F':
                    await context.bot.send_message(id,f"New fan attached!: {ip}")
                elif res.content == b'C':
                    await context.bot.send_message(id,f"New camera attached!: {ip}")
                else:
                    await context.bot.send_message(id,f"[!] Intruder!: {ip}")
    except requests.exceptions.ConnectionError as e:
        print(e)
        pass

def merge_config()-> str:
    old_config = open("./config.json")
    old_config = old_config.read()
    patch_to_config: Config = json.loads(generate_config(config))
    old_config_: Config = json.loads(old_config)
    try:
        merged_json: Config =  {**old_config_, **patch_to_config}
        merged_config = json.dumps(merged_json)
        return merged_config
    except TypeError or json.decoder.JSONDecodeError as e:
        print(e)
        pass
    
async def write_patched_config():
    file_dir = "./config.json"
    try:
        merged_config = merge_config()
        print(merged_config,flush=True)
        if merged_config is not None:
            with open(file_dir, "w") as fp:
                fp.write(bytes(merged_config))
        else:
            pass
    except TypeError as e:
        print(e)
        pass

def init_db():
    conn.autocommit = True
    try:
        cur.execute("CREATE DATABASE strawberrypidb")
        if cur.statusmessage == "CREATE DATABASE":
            cur.execute("SELECT * FROM sensors;") 
            if cur.fetchall():
                cur.execute("""CREATE TABLE sensors (
                id INT PRIMARY KEY NOT NULL, 
                ip VARCHAR(15),
                temperature double precision,
                humidity double precision,
                "timestamp" timestamp without time zone NOT NULL DEFAULT (current_timestamp AT TIME ZONE 'GMT+2'));""")
                conn.commit()
                cur.execute("SELECT * FROM loads;")
            if cur.fetchall():
                cur.execute("""CREATE TABLE sensors (
                id INT PRIMARY KEY NOT NULL, 
                ip VARCHAR(15),
                status INT,
                "timestamp" timestamp without time zone NOT NULL DEFAULT (current_timestamp AT TIME ZONE 'GMT+2'));""")
                conn.commit()
    except Exception as e:
        print(e)
        pass
            
      
def generate_config(config:Config) -> str:
    try:
        for ip in get_connected_loads():
            for group in config.groups:
                if ip not in group.lights or ip not in group.fans or ip not in group.water_pumps or ip not in group.sensors or ip not in group.cameras:
                    res = session.get("http://"+ip+"/whoami", timeout=2)
                    if res.ok: 
                        if res.content == b'T&H':
                            print(f"New temperature and humidity sensor attached!: {ip}",flush=True)
                            ap_ip= Config.Group(id="ap-ip",description="AP detected IPs.",lights=[""],water_pumps=[""],sensors=[ip],fans=[""], cameras=[""])
                        elif res.content == b'L':
                            print(id,f"New light attached!: {ip}", flush=True)
                            ap_ip= Config.Group(id="ap-ip",description="AP detected IPs.",lights=ip,water_pumps=[""],sensors=[""],fans=[""], cameras=[""])
                        elif res.content == b'WP':
                            print(id,f"New water pump attached!: {ip}", flush=True)
                            ap_ip= Config.Group(id="ap-ip",description="AP detected IPs.",water_pumps=[ip],lights=[""],sensors=[""],fans=[""], cameras=[""])
                        elif res.content == b'F':
                            print(id,f"New fan attached!: {ip}", flush=True)
                            ap_ip= Config.Group(id="ap-ip",description="AP detected IPs.",fans=[ip],lights=[""],water_pumps=[""],sensors=[""], cameras=[""])
                        elif res.content == b'C':
                            print(id,f"New camera attached!: {ip}", flush=True)
                            ap_ip= Config.Group(id="ap-ip",description="AP detected IPs.",cameras=[ip],lights=[""],water_pumps=[""],sensors=res.content,fans=[""])
                        else:
                            print(id,f"[!] Intruder!: {ip}", flush=True)
                        config = Config(groups=[ap_ip])    
                        cfg = json.dumps(config.to_dict())
                        return cfg
    except requests.exceptions.ConnectionError or TypeError as e:
        print(e)
        pass

def get_connected_loads() -> list[str]:
    try:
        ips = []
        connected_ips = open("/var/lib/misc/dnsmasq.leases")
        connected_ips = connected_ips.read()
        if connected_ips is not None:
            if connected_ips.count('\n') == 1:
                connected_ip = connected_ips.split(" ")[2]
                print(f"Found ip \"{connected_ip}\" in the plantation network.")
                print("...Processing...")
                ips.append(connected_ip)
                print(ips)
                return ips
            else:
                lines = connected_ips.strip().split('\n')
                connected_ips = [line.split()[2] for line in lines if len(line.split()) >= 2]
                print(f"Found ips \"{connected_ips}\" in the plantation network.")
                print("...Processing...")
                return connected_ips
        else:
            print("No IPs were found.",flush=True)
    except FileNotFoundError as e:
        print(e)
        pass
    

async def whoami(context: CallbackContext):
    try:
        context.job_queue.run_once(callback_alert, datetime.now(timezone), chat_id=id)
        pass
    except Exception as e:
        print(e)
        pass

    

#Acce Point init
def init_ap():
    os.system("sudo service hostapd stop")
    os.system("sudo service dnsmasq stop")
    os.system("sudo dhclient -r wlan0")
    os.system("sudo iw dev wlan0 interface add ap0 type __ap")
    os.system("sudo ip addr add 192.168.4.1/24 dev ap0")
    os.system("sudo ip link set ap0 up")
    os.system("sudo hostapd -B /etc/hostapd/hostapd.conf")
    cmd = "sudo dnsmasq -C /dev/null -kd -F 192.168.4.2,192.168.4.254 -i ap0 --bind-dynamic"
    subprocess.Popen(shlex.split(cmd))
    os.system("sudo sysctl net.ipv4.ip_forward=1")
    os.system("sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
    os.system("sudo iptables -A FORWARD -i ap0 -o eth0 -j ACCEPT")
    os.system("sudo iptables -A FORWARD -i eth0 -o ap0 -m state --state RELATED,ESTABLISHED -j ACCEPT")
    time.sleep(60)


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
                    except telegram.error.TimedOut:
                        await update.message.reply_text("Telegram request timed out.")
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
            except telegram.error.TimedOut:
                await update.message.reply_text("Telegram request timed out.")
            except requests.RequestException as e:
                await update.message.reply_text(f"[!] Camera error: {e}")
            except requests.exceptions.ConnectionError as conn_e:
                print("Connection Error")
            except Exception as e:
                print(e)


            
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Commands:\n/force_start\n/emergency_stop\n/stats - See sensors stats\n/help - to show this help lines.")

async def start_bot(config: Config):
    application.add_handler(CommandHandler("help", help_command, block=False))
    application.add_handler(CommandHandler("cam", lambda a,b: send_picture_from_cam(config,a,b), block=False))
    application.add_handler(CommandHandler("force_start", lambda a,b: force_start(config,a,b), block=False))
    application.add_handler(CommandHandler("emergency_stop", lambda a,b: emergency_stop(config,a,b),block=False) )
    application.add_handler(CommandHandler("stats", lambda a,b: stats(config,a,b), block=False))
    await application.run_polling(allowed_updates=Update.MESSAGE)

            
                        
async  def start_routine(config:Config):
    for group in config.groups:
        if datetime.now(timezone) <= seedling_end_time:
            for water_pump in group.water_pumps:
                try:
                    await switch(water_pump,"on")
                    await asyncio.sleep(120)
                    await switch(water_pump,"off")
                    await asyncio.sleep(1800)
                except:
                    print(f"Error on turning on ip: {water_pump}",flush=True)
        elif datetime.now(timezone) <= vegetative_end_time:
            for water_pump in group.water_pumps:
                try:
                    await switch(water_pump,"on")
                    await asyncio.sleep(240)
                    await switch(water_pump,"off")
                    await asyncio.sleep(1800)

                except:
                    print(f"Error on turning on ip: {water_pump}",flush=True)
        else:
            for water_pump in group.water_pumps:
                try:
                    await switch(water_pump,"on")
                    await asyncio.sleep(120)
                    await switch(water_pump,"off")
                    await asyncio.sleep(1800)

                except:
                    print(f"Error on turning on ip: {water_pump}",flush=True)
        for sensor in group.sensors:
            lcd = CharLCD(i2c_expander=os.getenv("I2C_EXPANDER"), address=0x27, port=1, cols=16, rows=4, dotsize=10) #LCD initalization 
            await sensor_and_display_monitoring(lcd,sensor)
            if await sensor_controller("temperature",sensor)==True: #Temperature too high
                    for fan in group.fans:
                        try:
                            await switch(fan,"on")
                            await asyncio.sleep(13.37)
                        except:
                            print(f"Error on turning off ip: {fan}",flush=True)
            if await sensor_controller("humidity",sensor)==True: #Humidity too high
                for fan in group.fans:
                    try:
                        await switch(fan,"on")
                        await asyncio.sleep(13.37)
                    except:
                        print(f"Error on turning on ip: {fan}",flush=True)
                for water_pump in group.water_pumps:
                    try:
                        await switch(water_pump,"off") #Maybe the water pump mulfunctioned and all the water sinked inside the greenhouse, making the humidity raise
                        await asyncio.sleep(13.37)
                    except:
                        print(f"Error on turning off ip: {water_pump}",flush=True)
            else:
                for fan in group.fans:
                    try:
                        await switch(fan,"on")
                        await asyncio.sleep(13.37)

                    except:
                        print(f"Error on turning on ip: {fan}",flush=True)
                        
async def light_routine(config):
    for group in config.groups:
        for light in group.lights:
            if is_summer() and is_night():
                print("turning off lights for fun an profit", flush=True)
                await switch(light,mode="off")
            else:
                await switch(light,mode="on")
async def periodic(interval,coro, *args, **kwargs):
    while True:
        await coro(*args, **kwargs)
        await asyncio.sleep(interval)
async def run_forever(coro, *args, **kwargs):
    while True:
        await coro(*args, **kwargs)
async def run_with_delay(interval,coro, *args, **kwargs):
        await asyncio.sleep(interval)
        await coro(*args, **kwargs)
        

        
async def main():
    nest_asyncio.apply()
    asyncio.create_task(run_forever(start_routine,config)) # About every 30 minutes
    asyncio.create_task(whoami(context))
    asyncio.create_task(run_forever(light_routine, config))
    await start_bot(config)
    

        
                
if __name__ == "__main__":
    init_ap()
    init_db()
    asyncio.run(asyncio.sleep(1.337))
    #asyncio.run(run_with_delay(10,write_patched_config))
    asyncio.run(main())    
