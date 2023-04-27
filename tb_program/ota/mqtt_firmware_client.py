from paho.mqtt.client import Client
import paho.mqtt.client as mqtt
from json import dumps, loads
import time
import math
from hashlib import sha256, sha384, sha512, md5
from mmh3 import hash, hash128
from zlib import crc32
import datetime
from threading import Thread
from subprocess import run

CONNECT_RESULT_CODES = {
    1: "Connect refused -- incorrect protocol version",
    2: "Connect refused -- invalid client identifier",
    3: "Connect refused -- server unavailable",
    4: "Connect refused -- bad username or password",
    5: "Connect refused -- not authorised",
    }

DISCONNECT_RESULT_CODES = {
    1: "Unormal Disconnect -- The connection was refused by the broker",
    2: "Unormal Disconnect -- The connection was lost unexpectedly",
    3: "Unormal Disconnect -- The client has requested a disconnection from the broker",
    4: "Unoraml Disconnect -- The broker has diconnected the client because it did not receive a message within the keep-alive time",
    mqtt.MQTT_ERR_CONN_LOST: "Unormal Disconnect -- Conection Lost"
}

PUBLISH_RESULT_CODES = {
    mqtt.MQTT_ERR_SUCCESS: "The publish operation is successful",
    mqtt.MQTT_ERR_NO_CONN: "The client is currently not connected to an MQTT broker",
    mqtt.MQTT_ERR_AGAIN: "The client is busy and cannot perform the publish operation at this time",
    mqtt.MQTT_ERR_QUEUE_SIZE: "The client's queue is full and cannot accept any more message",
    mqtt.MQTT_ERR_PAYLOAD_SIZE: "The size of the message payload is too large for the broker to accept",
    mqtt.MQTT_ERR_PROTOCOL: "There was an error in the MQTT protocol during the publish operation",
    mqtt.MQTT_ERR_NOT_SUPPORTED: "The QoS level is not supported by the broker",
}

FW_CHECKSUM_ATTR = "fw_checksum"
FW_CHECKSUM_ALG_ATTR = "fw_checksum_algorithm"
FW_SIZE_ATTR = "fw_size"
FW_TITLE_ATTR = "fw_title"
FW_VERSION_ATTR = "fw_version"
FW_STATE_ATTR = "fw_state"


SHARE_KEY = "fw_title,fw_version,fw_size,fw_checksum,fw_checksum_algorithm"
CLIENT_KEY = "current_fw_title,current_fw_version,fw_state,last_update_ts"

def collect_required_data():
    config = {}
    host = "192.168.1.2"
    config["host"] = host if host else "mqtt.thingsboard.cloud"
    port = 1883
    config["port"] = int(port) if port else 1883
    config["token"] = "WZSx45Po9jaPkpNcwS3h"
    device_name = "XFL1XL13G3AV"
    if device_name:
        config["device_name"] = device_name
    return config


class MQTTClient(Client):
    ATTRIBUTE_TOPIC_SUBPUB = "v1/devices/me/attributes"
    ATTRIBUTE_TOPIC_RESPONSE = "v1/devices/me/attributes/response/+"
    FW_TOPIC_RESPONSE = "v2/fw/response/+/chunk/+"

    def __init__(self, host, port, token):
        super().__init__()
        self._host = host
        self._port = port
        self._token = token
        self.on_connect = self.__on_connect
        self.on_message = self.__on_message
        self.on_disconnect =self.__on_disconnect
        self.request_id = 0
        self.chunk_id = 0
        self.chunk_size = 0
        self.fw_data = b''
        self.current_fw_info = {
            "current_fw_title": "",
            "current_fw_version": "",
            "fw_state": "",
            "last_update_ts": ""
        }
        self.firmware_received = False
        self.__updating_thread = Thread(target=self.__update_thread, name="Updating thread")
        self.__updating_thread.daemon = True
        self.__updating_thread.start()

    def __on_connect(self, client, userdata, flags, rc):  # Callback for connect
        if rc == 0:
            print("[Thingsboard client] Connected to ThingsBoard ")
            client.subscribe(self.ATTRIBUTE_TOPIC_SUBPUB)
            client.subscribe(self.ATTRIBUTE_TOPIC_RESPONSE)
            client.subscribe(self.FW_TOPIC_RESPONSE)
        else:
            print(CONNECT_RESULT_CODES[rc])

    def __on_disconnect(self, client, userdata, rc):
        if rc == 0:
            print("[Thingsboard Client] Disconnected from ThingsBoard")
        else:
            print(DISCONNECT_RESULT_CODES[rc])
        self.loop_stop()

    def __on_message(self, client, userdata, msg):
        fw_update = "v2/fw/response/" + str(self.request_id) + "/chunk/"
        if msg.topic.startswith(fw_update):
            new_data_chunk = msg.payload
            self.fw_data += new_data_chunk
            if len(self.fw_data) >= self.new_info[FW_SIZE_ATTR]:
                self.chunk_id = 0
                self.check_firmware()
            else:
                #print(".", end="")
                self.chunk_id += 1
                self.get_firmware(self.new_info[FW_SIZE_ATTR])
        elif msg.topic.startswith("v1/devices/me/attributes"):
            fw_info = loads(msg.payload)
            if "/response/" in msg.topic:
                self.current_fw_info = fw_info.get("client", {}) if isinstance(fw_info, dict) else {}
                self.new_info = fw_info.get("shared", {}) if isinstance(fw_info, dict) else {}
                print("Current firmware: " + str(self.current_fw_info))
                print("New firmware: " + str(self.new_info))
                # TODO: need to check local first
                if (self.new_info.get(FW_VERSION_ATTR) is not None and self.new_info.get(FW_VERSION_ATTR) != self.current_fw_info.get("current_" + FW_VERSION_ATTR)) or \
                    (self.new_info.get(FW_TITLE_ATTR) is not None and self.new_info.get(FW_TITLE_ATTR) != self.current_fw_info.get("current_" + FW_TITLE_ATTR)):
                    print("Found new firmware. Size: " + str(self.new_info[FW_SIZE_ATTR]) + "B")
                    self.current_fw_info[FW_STATE_ATTR] = "DOWNLOADING"
                    self.send_telemetry(self.current_fw_info)
                    time.sleep(0.1)
                    print("Wait for DOWNLOADING...")
                    time.sleep(3)
                    self.fw_data = b''
                    self.current_fw_info["last_update_ts"] = str(datetime.datetime.now())
                    self.request_id += 1
                    self.get_firmware(self.new_info[FW_SIZE_ATTR])
            else:
                self.publish(f"v1/devices/me/attributes/request/{self.request_id}", dumps({"sharedKeys": SHARE_KEY, "clientKeys": CLIENT_KEY}))
        else:
            try:
                decoded_payload = msg.payload.decode("UTF-8")
                print("[Thingsboard client] Received data from ThingsBoard: %s" % decoded_payload)
            except:
                print("Unable to process a message from: " + msg.topic)
    
    def __update_thread(self):
        while True:
            if self.firmware_received:
                self.current_fw_info[FW_STATE_ATTR] = "UPDATING"
                self.send_telemetry(self.current_fw_info)
                time.sleep(0.1)

                with open(self.new_info.get(FW_TITLE_ATTR), "wb") as firmware_file:
                    firmware_file.write(self.fw_data)

                for i in range(0, 3):
                    time.sleep(3)
                
                ## process update
                run(["tar", "-xzf", self.new_info.get(FW_TITLE_ATTR)], capture_output=True, text=True)
                time.sleep(3)

                decompress = self.new_info.get(FW_TITLE_ATTR).replace(".tar.gz", "")
                print(decompress)
                run([f"./{decompress}/update.sh"])

                self.current_fw_info["current_" + FW_TITLE_ATTR] = self.new_info.get(FW_TITLE_ATTR)
                self.current_fw_info["current_" + FW_VERSION_ATTR] = self.new_info.get(FW_VERSION_ATTR)
                self.current_fw_info[FW_STATE_ATTR] = "UPDATED"
                self.send_telemetry(self.current_fw_info)
                time.sleep(0.1)
                self.update_attribute(self.current_fw_info)
                self.firmware_received = False
                time.sleep(1)

    def trigger(self):
        print("[Thingsboard Client] Connecting to ThingsBoard")
        self.username_pw_set(self._token)
        self.connect(self._host, self._port, 600)
        self.loop_start()


    def get_firmware(self, size):
        payload = b'' if not self.chunk_size or self.chunk_size > size else str(self.chunk_size).encode()
        self.publish(f"v2/fw/request/{self.request_id}/chunk/{self.chunk_id}", payload=payload, qos=2)

    def check_firmware(self):
        self.current_fw_info[FW_STATE_ATTR] = "DOWNLOADED"
        print("\nFinished Download")
        self.send_telemetry(self.current_fw_info)
        time.sleep(1)

        verification_result = verify_checksum(self.fw_data, self.new_info.get(FW_CHECKSUM_ALG_ATTR), self.new_info.get(FW_CHECKSUM_ATTR))

        # for daemon program
        #client.fw_data = b''
        #client.request_id = 0
        #client.chunk_id = 0
        #client.chunk_size = 0
        if verification_result:
            print("Checksum verified!")
            self.current_fw_info[FW_STATE_ATTR] = "VERIFIED"
            self.send_telemetry(self.current_fw_info)
            time.sleep(0.1)
        else:
            print("Checksum verification failed!")
            self.current_fw_info[FW_STATE_ATTR] = "FAILED"
            self.send_telemetry(self.current_fw_info)
            time.sleep(0.1)

            # resubmit download
            #client.fw_data = b''
            #client.request_id += 1
            #client.chunk_id = 0
            #__get_firmware(client, client.new_info["fw_size"])
            return
        self.firmware_received = True

    def send_telemetry(self, telemetry):
        return self.publish("v1/devices/me/telemetry", dumps(telemetry), qos=1)

    def update_attribute(self, attribute):
        return self.publish("v1/devices/me/attributes", dumps(attribute), qos=1)

def verify_checksum(firmware_data, checksum_alg, checksum):
    if firmware_data is None:
        print("Firmware wasn't received!")
        return False
    if checksum is None:
        print("Checksum was't provided!")
        return False
    checksum_of_received_firmware = None
    print(f"Checksum algorithm is: {checksum_alg}")
    if checksum_alg.lower() == "sha256":
        checksum_of_received_firmware = sha256(firmware_data).digest().hex()
    elif checksum_alg.lower() == "sha384":
        checksum_of_received_firmware = sha384(firmware_data).digest().hex()
    elif checksum_alg.lower() == "sha512":
        checksum_of_received_firmware = sha512(firmware_data).digest().hex()
    elif checksum_alg.lower() == "md5":
        checksum_of_received_firmware = md5(firmware_data).digest().hex()
    elif checksum_alg.lower() == "murmur3_32":
        reversed_checksum = f'{hash(firmware_data, signed=False):0>2X}'
        if len(reversed_checksum) % 2 != 0:
            reversed_checksum = '0' + reversed_checksum
        checksum_of_received_firmware = "".join(reversed([reversed_checksum[i:i+2] for i in range(0, len(reversed_checksum), 2)])).lower()
    elif checksum_alg.lower() == "murmur3_128":
        reversed_checksum = f'{hash128(firmware_data, signed=False):0>2X}'
        if len(reversed_checksum) % 2 != 0:
            reversed_checksum = '0' + reversed_checksum
        checksum_of_received_firmware = "".join(reversed([reversed_checksum[i:i+2] for i in range(0, len(reversed_checksum), 2)])).lower()
    elif checksum_alg.lower() == "crc32":
        reversed_checksum = f'{crc32(firmware_data) & 0xffffffff:0>2X}'
        if len(reversed_checksum) % 2 != 0:
            reversed_checksum = '0' + reversed_checksum
        checksum_of_received_firmware = "".join(reversed([reversed_checksum[i:i+2] for i in range(0, len(reversed_checksum), 2)])).lower()
    else:
        print("Client error. Unsupported checksum algorithm.")
    return checksum_of_received_firmware == checksum


def test_request_shared_attribute():
    ret = mqtt_client.publish("v1/devices/me/attributes/request/1", dumps({"sharedKeys": REQUIRED_SHARE_KEY}))
    return ret

def test_update_client_attribute():
    ret = mqtt_client.publish("v1/devices/me/attributes", dumps({
        "current_fw_title": "hellow world",
        "current_fw_version": "v0.0",
        "fw_state": "UNKNOWN",
        "last_update_ts": "fasdf"
    }))
    return ret

def test_ota():
    ret = mqtt_client.publish("v2/fw/request/0/chunk/0", dumps(1230))
    return ret

if __name__ == '__main__':

    config = collect_required_data()

    THINGSBOARD_HOST = config["host"]  # ThingsBoard instance host
    THINGSBOARD_PORT = config["port"]  # ThingsBoard instance MQTT port
    THINGSBOARD_TOKEN = config["token"]

    mqtt_client = MQTTClient(THINGSBOARD_HOST, THINGSBOARD_PORT, THINGSBOARD_TOKEN)
    mqtt_client.trigger()
    while not mqtt_client.is_connected():
        time.sleep(0.001)

    mqtt_client.publish(f"v1/devices/me/attributes/request/{mqtt_client.request_id}", dumps({"sharedKeys": SHARE_KEY, "clientKeys": CLIENT_KEY}))
    while True:
        continue

    # testing request shared attribute
    #test_request_shared_attribute()
    #time.sleep(0.1)
    #print("first time: " + PUBLISH_RESULT_CODES[ret1.rc])

    # testing update client attribute
    #time.sleep(1)
    #test_update_client_attribute()
    #print("publish client attribute: " + PUBLISH_RESULT_CODES[ret3.rc])
    #time.sleep(3)
    #ret2 = mqtt_client.publish("v1/devices/me/attributes/request/2", dumps({"clientKeys": CLIENT_KEY}))
    #print("second time: " + PUBLISH_RESULT_CODES[ret2.rc])
    

    # testing ota
    #time.sleep(1)
    #fw_size = 8970597
    #for i in range(0, math.ceil(fw_size/1230)):
    #ret5 = mqtt_client.publish("v2/fw/request/0/chunk/0", dumps(1230))
    #print(PUBLISH_RESULT_CODES[ret5.rc])
    #time.sleep(5)


    # disconnect connection
    #mqtt_client.disconnect()
    #time.sleep(0.1)