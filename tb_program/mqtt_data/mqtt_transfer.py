import paho.mqtt.client as mqtt
import json
import time
import perfstat
import platformstat

broker_address="192.168.1.2"
port=1883
token="WZSx45Po9jaPkpNcwS3h"
client = mqtt.Client()
client.username_pw_set(token)
client.connect(broker_address, port)
s_time = 0.1

while True:
    som_power = platformstat.get_SOM_power()
    FPD_temp = platformstat.get_FPD_temp()
    PL_temp = platformstat.get_PL_temp()
    branch1_fps = perfstat.get_branch1_pf()
    branch2_fps = perfstat.get_branch2_pf()

    payload = {"power": som_power, "fpd_temp": FPD_temp, "pl_temp": PL_temp, "branch1_fps": branch1_fps, "branch2_fps": branch2_fps}
    print(json.dumps(payload))
    client.publish("v1/devices/me/telemetry", json.dumps(payload))
    time.sleep(0.1)

