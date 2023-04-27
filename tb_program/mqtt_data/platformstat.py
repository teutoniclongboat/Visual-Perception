import os


def read_sysfs_entry(filename):
    with open(filename, 'r') as fd:
        try:
            value = fd.readline().strip()
        except:
            return -1
    return value


def count_hwmon_reg_devices():
    num_hwmon_devices = 0
    with os.scandir("/sys/class/hwmon") as it:
        for entry in it:
            if entry.name.startswith("hwmon"):
                num_hwmon_devices += 1
    return num_hwmon_devices


def get_device_hwmon_id(verbose_flag, name):
    
    num_hw_devices = count_hwmon_reg_devices()
    for hwmon_id in range(0, num_hw_devices):
        filename = "/sys/class/hwmon/hwmon" + str(hwmon_id) + "/name"

        device_name = read_sysfs_entry(filename)
        if (name == device_name):
            return hwmon_id
        if (verbose_flag):
            print("filename {}".format(filename))
            print("device_name = {}".format(device_name))

    return -1


#
# info ->
#        power: SOM power
#        curr: SOM current
#        in: SOM voltage
#
def get_ina260_info(verbose_flag, info):
    hwmon_id = get_device_hwmon_id(verbose_flag, "ina260_u14")
    if (hwmon_id == -1):
        print("failed get ina260 id")
        print("no hwmon device found for ina260_u14 under /sys/class/hwmon")
        return -1
    basefilepath = "/sys/class/hwmon/hwmon" + str(hwmon_id) + "/"
    filename = basefilepath + info + "1_input"
    with open(filename, 'r') as fp:
        try:
            value = int(fp.readline().strip())
            if (verbose_flag):
                if (info == "power"):
                    print("SOM total power: {} mW", value / 1000)
                elif (info == "curr"):
                    print("SOM total current: {} mA", value)
                else:
                    print("SOM total voltage: {} mV", value)
        except:
            print("failed to read file {}".format(filename))
            return -1
    return value

def get_SOM_power():
    val = get_ina260_info(0, "power")
    return val / 1000000 if val != -1 else val

#
# info ->
#       temp1: LPD, temp2: FPD, temp3: PL
#       in* : volatge for other part of the system 
#
def get_sysmon_info(verbose_flag, info):
    hwmon_id = get_device_hwmon_id(verbose_flag, "ams")
    if (hwmon_id == -1):
        print("failed get sysmon id")
        print("no hwmon device found for ams under /sys/class/hwmon")
        return -1
    basefilepath = "/sys/class/hwmon/hwmon" + str(hwmon_id) + "/"
    filename = basefilepath + info + "_input"
    with open(filename, 'r') as fp:
        try:
            value = int(fp.readline().strip())
            if (verbose_flag):
                if (info == "temp1"):
                    print("LPD temperature: {} C", value / 1000)
                elif (info == "temp2"):
                    print("FPD temperature: {} C", value / 1000)
                elif (info == "temp3"):
                    print("PL temperature: {} C", value / 1000)
                else:
                    print("Voltage: {} mV", value)
        except:
            print("failed to read file {}".format(filename))
            return -1
    return value

def get_LPD_temp():
    val = get_sysmon_info(0, "temp1")
    return val / 1000 if val != -1 else val

def get_FPD_temp():
    val = get_sysmon_info(0, "temp2")
    return val / 1000 if val != -1 else val

def get_PL_temp():
    val = get_sysmon_info(0, "temp3")
    return val / 1000 if val != -1 else val

