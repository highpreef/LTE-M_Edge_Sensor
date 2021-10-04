import pyb, machine, tf, os, sensor, image, time, math, binascii
from pyb import UART, Pin, ExtInt

# sensor.reset()
# sensor.set_pixformat(sensor.RGB565) # Modify as you like.
# sensor.set_framesize(sensor.QVGA) # Modify as you like.
# sensor.skip_frames(time = 2000)

clock = time.clock()

# Init UART 3, and with specific baudrate.
uart = UART(3, 9600, timeout_char=1000)


def sendData(data, raw=False):
    """
    Sends data over UART.

    :param data: Data to be sent over UART.
    :param raw: Flags whether or not to encode data (note data has to be encoded to be sent over UART).
    """
    uart.write(data.encode("utf-8") + b"\r\n") if not raw else uart.write(data)


def listen(timeout=10, success=None, failure=None):
    """
    Listens UART channel for response from modem.

    :param timeout: Timeout for listening for response.
    :param success: Expected success response.
    :param failure: Expected failure response.
    :return: Expected failure response, response
    """
    start = time.time()
    while not uart.any():
        if (time.time() - start) > timeout:
            return "TIMEOUT"
        time.sleep_ms(20)
    line = uart.read().decode('utf-8')
    return (failure, line) if failure in line else (success, line)


def AT(command="", timeout=10, success="OK", failure="+CME ERROR"):
    """
    Sends AT command over UART to modem.

    :param command: AT command (not including 'AT')
    :param timeout: Timeout for listening over UART.
    :param success: Expected success response.
    :param failure: Expected failure response
    :return: Response from modem
    """
    command = "AT" + command
    print("--->", command)
    sendData(command)
    response = listen(timeout=timeout, success=success, failure=failure)
    if failure in response:
        print(response[1])
    print("TIMEOUT") if "TIMEOUT" in response else print("<---", response[1])
    return response


def init_checks(fast_init=False):
    """
    Sets debug level and removes command echo from modem. Prints extra info about the modem if requested.

    :param fast_init: Flags whether or not to print info about the modem.
    """
    AT("+CMEE=2")  # Set debug level
    AT("E0")  # Remove command echo
    if fast_init:
        return
    # Hardware Info
    AT("+CPIN?")  # Check sim card is present and active
    AT("+CGMM")  # Check module name
    AT("+CGMR")  # Firmware version
    AT('+GSN')  # Get IMEI number
    AT('+CCLK?')  # Get system time
    # Signal info
    AT("+COPS?")  # Check opertaor info
    AT("+CSQ")  # Get signal strength
    AT('+CPSI?')  # Get more detailed signal info
    AT('+CBAND?')  # Get band
    # GPRS info
    AT("+CGREG?")  # Get network registration status
    AT("+CGACT?")  # Show PDP context state
    AT('+CGPADDR')  # Show PDP address


def ping(apn="payandgo.o2.co.uk", ip="", dest="www.google.com"):
    """
    Test modem PING functionality.

    :param apn: Operator APN.
    :param ip: Modem IP address.
    :param dest: Ping target IP address or URL.
    """
    print("++++++++++++++++++++ PING +++++++++++++++++++++\n")
    cstt = AT('+CSTT?')
    if apn not in cstt:
        AT('+CSTT="{}"'.format(apn))
        AT('+CIICR')
    AT('+CIFSR', success=ip)
    AT('+CIPPING="{}"'.format(dest))


def ntp(apn="payandgo.o2.co.uk", dest="pool.ntp.org"):
    """
    Fetches and updates modem clock from NTP server.

    :param apn: Operator APN.
    :param dest: NTP server URL
    """
    print("++++++++++++++++++++ NTP +++++++++++++++++++++\n")
    AT('+SAPBR=3,1,"APN","{}"'.format(apn))
    AT('+SAPBR=1,1')
    AT('+SAPBR=2,1')
    AT('+CNTP="{}",0,1,1'.format(dest))
    AT('+CNTP', timeout=3, success="+CNTP")
    AT('+SAPBR=0,1')


def httpGet(apn="payandgo.o2.co.uk", dest="http://www.google.com"):
    """
    Tests modem connection over HTTP.

    :param apn: Operator APN.
    :param dest: Target IP address or URL.
    """
    print("++++++++++++++++++++ HTTP1 +++++++++++++++++++++\n")
    AT('+SAPBR=3,1,"APN","{}"'.format(apn))
    AT('+SAPBR=1,1')
    AT('+SAPBR=2,1')
    AT('+HTTPINIT')
    AT('+HTTPPARA="CID",1')
    AT('+HTTPPARA="URL",{}'.format(dest))
    AT('+HTTPACTION=0', timeout=30, success="+HTTPACTION: 0,200")
    AT('+HTTPREAD')
    AT('+HTTPTERM')
    AT('+SAPBR=0,1')


def gotoErrorState(red_led):
    """
    Makes OpenMV camera enter an error state indicating that modem needs to be restarted.

    :param red_led: LED class for the red LED.
    """
    while True:
        red_led.on()
        time.sleep_ms(100)
        red_led.off()
        time.sleep_ms(100)


def pdp(apn="payandgo.o2.co.uk"):
    """
    Activates PDP context, which is necessary for data transmission.

    :param apn: Operator APN
    :return: Modem response
    """
    AT("+CGATT=1")
    res = AT("+CNACT=1", failure="DEACTIVE")
    if "DEACTIVE" in res:
        AT("+CGATT=0")
        AT("+CGDCONT=1,\"IP\",\"\"")
        AT("+CGATT=1")
        res = AT("+CNACT=1", failure="DEACTIVE")
        if "DEACTIVE" in res:  # sure-fire way of activating pdp context
            AT("+CGATT=0")
            AT("+CGDCONT=1,\"IP\",\"{}\"".format(apn))
            AT("+CGATT=1")
            res = AT("+CNACT=1", failure="DEACTIVE")
    return res


def sslconf(rootca, clientca, clientkey, ip, rootonly=False):
    """
    Configures certificates and private key for use over TLS connection. NOTE: relevant files need to be previously
    stored into modem. This can be achieved by sending the following AT commands over USB.
    AT+CFSINIT
    AT+CFSWFILE=3,"__file_name__",0,__file_size_in_bytes__,10000
    *PASTE FILE CONTENTS
    (Repeat above two lines for each file to be stored)
    AT+CFSTERM

    :param rootca: Root certificate authority file name
    :param clientca: Client certificate.
    :param clientkey: Client private key.
    :param ip: Modem IP address
    :param rootonly: Flags whether to only configure root certificate authority.
    """
    AT("+CNACT?", success=ip)
    AT("+CFSGFIS=3,\"{}\"".format(rootca))
    AT("+CFSGFIS=3,\"{}\"".format(clientca))
    AT("+CFSGFIS=3,\"{}\"".format(clientkey))
    AT("+CSSLCFG=convert,2,{}".format(rootca))
    if not rootonly:
        AT("+CSSLCFG=convert,1,{},{}".format(clientca, clientkey))
        AT("+SMSSL=1,{},{}".format(rootca, clientca))
    else:
        AT("+SMSSL=1,{},\"\"".format(rootca))
    AT("+CSSLCFG=\"sslversion\",0,3")


def mqttconf(clientid, url, port="8883", username=None, password=None, topic=None):
    """
    Configures MQTT session. NOTE: the '-ats' needs to be removed from the AWS endpoint, and the legacy root
    certificate authority needs to be configured.

    :param clientid: Client ID.
    :param url: AWS Endpoint.
    :param port: Connection port number.
    :param username: MQTT session username.
    :param password: MQTT session password.
    :param topic: MQTT session topic.
    """
    AT("+SMCONF=\"clientid\",\"{}\"".format(clientid))
    AT("+SMCONF=\"url\",\"{}\",\"{}\"".format(url, port))
    AT("+SMCONF=\"KEEPTIME\",60")
    if username:
        AT("+SMCONF=\"username\",\"{}\"".format(username))
    if password:
        AT("+SMCONF=\"password\",\"{}\"".format(password))
    if topic:
        AT("+SMCONF=\"topic\",\"{}\"".format(topic))


def mqttconn():
    """
    Start MQTT session.
    """
    AT("+SMDISC")
    AT("+SMCONN", timeout=10)


def mqttdisc():
    """
    Disconnect from MQTT session.
    """
    AT("+SMDISC")


def mqttpub(topic="basicPubSub", message="Hello World!", raw=False):
    """
    Publish over current MQTT session.

    :param topic: Publish topic.
    :param message: Publish message.
    :param raw: Flags whether or not to encode data when sending over UART.
    """
    AT("+SMPUB=\"{}\",{},1,0".format(topic, len(message)))
    sendData(message, raw)
    response = listen(success="OK", failure="ERROR")
    if "+CME ERROR" in response:
        print(response[1])
    print("TIMEOUT") if "TIMEOUT" in response else print("<---", response[1])
    if "TIMEOUT" in response or "+CME ERROR" in response:
        gotoErrorState(red_led)


def mqttsub(topic="basicPubSub"):
    """
    Subscribe to topic for current MQTT session.

    :param topic: Subscription topic.
    """
    AT("+SMSUB=\"{}\",1".format(topic))


def mqttunsub(topic="basicPubSub"):
    """
    Unsubscribe from topic for current MQTT session.

    :param topic: Subscription topic.
    """
    AT("+SMUNSUB=\"{}\"".format(topic))


def getapnip():
    """
    Fetches modem APN and IP address.

    :return: APN, IP address
    """
    cgcontrdp = AT("+CGCONTRDP")  # Get APN and IP address
    try:
        apn = cgcontrdp[1].split(",")[2]
        ip = cgcontrdp[1].split(",")[3]
    except:
        apn = ""
        ip = ""
    return apn, ip


def wireless(apn, ip):
    """
    Configures modem for TCP connection.

    :param apn: Operator APN.
    :param ip: Modem IP address.
    """
    AT("+CIPSHUT")
    cstt = AT('+CSTT?')[1].strip().split(',')[0]
    idx = cstt.find('\"')
    if apn != cstt[idx + 1:-1]:
        AT('+CSTT="{}"'.format(apn))
    AT('+CIICR')
    AT('+CIFSR', success=ip)


def barcode_name(code):
    """
    Gets barcode type from barcode object.

    :param code: Barcode object.
    :return: Barcode type.
    """
    if code.type() == image.EAN2:
        return "EAN2"
    if code.type() == image.EAN5:
        return "EAN5"
    if code.type() == image.EAN8:
        return "EAN8"
    if code.type() == image.UPCE:
        return "UPCE"
    if code.type() == image.ISBN10:
        return "ISBN10"
    if code.type() == image.UPCA:
        return "UPCA"
    if code.type() == image.EAN13:
        return "EAN13"
    if code.type() == image.ISBN13:
        return "ISBN13"
    if code.type() == image.I25:
        return "I25"
    if code.type() == image.DATABAR:
        return "DATABAR"
    if code.type() == image.DATABAR_EXP:
        return "DATABAR_EXP"
    if code.type() == image.CODABAR:
        return "CODABAR"
    if code.type() == image.CODE39:
        return "CODE39"
    if code.type() == image.PDF417:
        return "PDF417"
    if code.type() == image.CODE93:
        return "CODE93"
    if code.type() == image.CODE128:
        return "CODE128"


def takePicture():
    """
    Helper function - takes a picture with the OpenMV camera.

    :return: image object.
    """
    img = sensor.snapshot()
    return img


def imgToChunks(img, chunk_size=512):
    """
    JPEG compresses image and converts it into chunks of hex strings that the modem can transmit over MQTT.

    :param img: Image object.
    :param chunk_size: Size of split.
    :return: List of hex strings representing the compressed image.
    """
    byte_arr = img.compress(quality=10).bytearray()
    print(len(byte_arr))
    # div, mod = divmod(len(byte_arr), chunk_size)
    # send_num = div + 1 if mod > 0 else 0
    l = lambda byte_arr, x: [byte_arr[i:i + x] for i in range(0, len(byte_arr), x)]
    msgs = l(bytes(byte_arr), chunk_size)
    print(binascii.hexlify(bytes(byte_arr)))
    return msgs


def mqttsendimg(msgs, headers=None):
    """
    Starts the transmission loop for sending chunks of an image over MQTT.

    :param msgs: List of hex strings representing compressed image.
    :param headers: Relevant metadata to be sent to AWS.
    """
    header = "{Image Start"
    if headers:
        for metadata in headers:
            header = header + "," + metadata
    header += "}"
    red_led.on()
    mqttpub(topic="sdk/test/Python", message=header, raw=True)
    red_led.off()
    for msg in msgs:
        red_led.on()
        mqttpub(topic="sdk/test/Python", message=binascii.hexlify(msg), raw=True)
        red_led.off()
    red_led.on()
    mqttpub(topic="sdk/test/Python", message="{Image End}", raw=True)
    red_led.off()


def setGRAYSCALE():
    """
    Sets OpenMV camera to grayscale mode, fit for scanning barcodes.
    """
    sensor.reset()
    sensor.set_pixformat(sensor.GRAYSCALE)
    sensor.set_framesize(sensor.VGA)  # High Res!
    sensor.set_windowing((640, 40))  # V Res of 80 == less work (40 for 2X the speed).
    sensor.skip_frames(time=2000)
    sensor.set_auto_gain(False)  # must turn this off to prevent image washout...
    sensor.set_auto_whitebal(False)  # must turn this off to prevent image washout...


def setRGB565():
    """
    Sets OpenMV camera to RGB mode, necessary for ML model inference.
    """
    sensor.reset()  # Reset and initialize the sensor.
    sensor.set_pixformat(sensor.RGB565)  # Set pixel format to RGB565 (or GRAYSCALE)
    sensor.set_framesize(sensor.QVGA)  # Set frame size to QVGA (320x240)
    sensor.set_windowing((240, 240))  # Set 240x240 window.
    sensor.skip_frames(time=2000)  # Let the camera adjust.


def modelDetect(model, labels, timeout=60):
    """
    Uses the OpenMV camera to search for a parcel in good/bad condition, and returns once it has found it. Aborts process if a timeout occurs.
    ML model needs to be present in flash memory. Timeout if no parcel is detected for a set duration.

    :param model: ML model file name.
    :param labels: Model labels
    :param timeout: Timeout duration.
    :return: Image, Label
    """
    green_led.on()
    start = time.time()
    while True:
        clock.tick()

        img = sensor.snapshot()

        for obj in tf.classify(model, img, min_scale=1.0, scale_mul=0.5, x_overlap=-1, y_overlap=-1):
            print("**********\nDetections at [x=%d,y=%d,w=%d,h=%d]" % obj.rect())
            for i in range(len(obj.output())):
                print("%s = %f" % (labels[i], obj.output()[i]))
            img.draw_rectangle(obj.rect())
            img.draw_string(obj.x() + 3, obj.y() - 1, labels[obj.output().index(max(obj.output()))], mono_space=False)

            if max(obj.output()) > 0.95:  # HIGH CONFIDENCE
                green_led.off()
                return img, labels[obj.output().index(max(obj.output()))]
        print(clock.fps(), "fps")

        if (time.time() - start) > timeout:
            green_led.off()
            return None, None


def callback(line):
    """
    Defines callback function for external interrupt.
    """
    pass


def gotoSleep():
    """
    Sets OpenMV camera into sleep mode.
    """
    sensor.reset()

    # Enable sensor softsleep
    sensor.sleep(True)

    # Optionally bypass the regulator on OV7725
    # for the lowest possible power consumption.
    if sensor.get_id() == sensor.OV7725:
        # Bypass internal regulator
        sensor.__write_reg(0x4F, 0x18)

    # Shutdown the sensor (pulls PWDN high).
    sensor.shutdown(True)

    machine.sleep()


if __name__ == "__main__":
    # Set interrupt for motion sensor on pin 9
    IOpin = Pin("P9", Pin.IN, Pin.PULL_UP)
    ext = ExtInt(IOpin, ExtInt.IRQ_FALLING, Pin.PULL_UP, callback)

    # Initialize variables for ML and LEDs
    net = 'trained.tflite'
    labels = ['background', 'Damaged Parcel', 'Parcel']
    red_led = pyb.LED(1)
    green_led = pyb.LED(2)
    blue_led = pyb.LED(3)

    # Test if modem is responding
    red_led.on()
    while "OK" not in AT():
        pass
    red_led.off()

    # initialize modem (set debug level and echo mode)
    init_checks(fast_init=True)
    apn, ip = getapnip()

    # Get PDP active
    res = pdp(apn=apn)
    if "DEACTIVE" in res:  # default: flash red LED to alert users to restart modem
        gotoErrorState(red_led)

    # configure SSL certificates and private key + setup mqtt session details
    sslconf(rootca="rootleg.pem", clientca="clientcert.pem", clientkey="clientkey.pem", ip=ip, rootonly=False)
    mqttconf(clientid="simcom", url="a1qrdh5dmin77y.iot.eu-west-2.amazonaws.com", port="8883", topic="sdk/test/Python")

    # go to sleep and wait for interrupt
    gotoSleep()

    # Set grayscale for reading barcode
    setGRAYSCALE()

    # Configure idle timeout
    timeout = 30
    start_time = time.time()

    # Start main loop
    while True:
        # light up blue LED while searching for barcodes
        blue_led.on()

        # Search for barcode (for best performance scan barcode from top to bottom
        clock.tick()
        img = sensor.snapshot()
        codes = img.find_barcodes()
        # If barcode is found init ML model
        for code in codes:
            blue_led.off()
            img.draw_rectangle(code.rect())
            print_args = (
                barcode_name(code), code.payload(), (180 * code.rotation()) / math.pi, code.quality(), clock.fps())
            print("Barcode %s, Payload \"%s\", rotation %f (degrees), quality %d, FPS %f" % print_args)
            # Give some time for users to show full parcel
            time.sleep(5)

            # Set to RGB to use image classification model
            setRGB565()
            imgout, outlabel = modelDetect(model=net, labels=labels)

            # Model timeout
            if imgout is None and outlabel is None:
                setGRAYSCALE()
                break

            # Prepare image+headers for data transmission
            msgs = imgToChunks(imgout, chunk_size=512)

            # Start data transmission loop
            mqttconn()
            mqttsendimg(msgs=msgs, headers=(barcode_name(code), code.payload(), outlabel))
            mqttdisc()

            # not needed anymore with timeout
            # gotoSleep()
            # refresh timeout to allow for multiple packages to be read
            start_time = time.time()

            # prepare for barcode reading
            setGRAYSCALE()
            break
        if not codes:
            print("FPS %f" % clock.fps())

        # Timeout has occured
        if (time.time() - start_time) > timeout:
            blue_led.off()
            gotoSleep()
            start_time = time.time()
            setGRAYSCALE()
