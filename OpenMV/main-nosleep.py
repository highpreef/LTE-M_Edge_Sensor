# Basic UART communications between OpenMV and Arduino Uno.

# 1) Wire up your OpenMV Cam to your Arduino Uno like this:
#
# OpenMV Cam Ground Pin   ----> Arduino Ground
# OpenMV Cam UART3_TX(P4) ----> Arduino Uno UART_RX(0)
# OpenMV Cam UART3_RX(P5) ----> Arduino Uno UART_TX(1)

# 2) Uncomment and upload the following sketch to Arduino:
#
# void setup() {
#   // put your setup code here, to run once:
#   Serial.begin(19200);
# }
#
# void loop() {
#   // put your main code here, to run repeatedly:
#   if (Serial.available()) {
#     // Read the most recent byte
#     byte byteRead = Serial.read();
#     // ECHO the value that was read
#     Serial.write(byteRead);
#   }
# }

# 3) Run the following script in OpenMV IDE:

import pyb, tf, os, sensor, image, time, math, binascii
from pyb import UART

sensor.reset()
sensor.set_pixformat(sensor.RGB565) # Modify as you like.
sensor.set_framesize(sensor.QVGA) # Modify as you like.
sensor.skip_frames(time = 2000)

clock = time.clock()

#sensor.reset()
#sensor.set_pixformat(sensor.GRAYSCALE)
#sensor.set_framesize(sensor.VGA) # High Res!
#sensor.set_windowing((640, 80)) # V Res of 80 == less work (40 for 2X the speed).
#sensor.skip_frames(time = 2000)
#sensor.set_auto_gain(False)  # must turn this off to prevent image washout...
#sensor.set_auto_whitebal(False)  # must turn this off to prevent image washout...
#clock = time.clock()

# UART 3, and baudrate.
uart = UART(3, 9600, timeout_char=1000)                         # init with given baudrate


def sendData(data, raw=False):
    uart.write(data.encode("utf-8") + b"\r\n") if not raw else uart.write(data)


def wait(timeout=10, success=None, failure=None):
    start = time.time()
    while not uart.any():
        if (time.time() - start) > timeout:
            return "TIMEOUT"
        time.sleep_ms(20)
    line = uart.read().decode('utf-8')
    return (failure, line) if failure in line else (success, line)


def AT(command="", timeout=10, success="OK", failure="+CME ERROR"):
    command = "AT" + command
    print("--->", command)
    sendData(command)
    response = wait(timeout=timeout, success=success, failure=failure)
    if failure in response:
        print(response[1])
    print("TIMEOUT") if "TIMEOUT" in response else print("<---", response[1])
    return response


def init_checks():
    AT()            # Check modem is responding
    AT("+CMEE=2")   # Set debug level
    AT("E0")        # Remove command echo
    # Hardware Info
    AT("+CPIN?")    # Check sim card is present and active
    AT("+CGMM")     # Check module name
    AT("+CGMR")     # Firmware version
    AT('+GSN')      # Get IMEI number
    AT('+CCLK?')    # Get system time
    # Signal info
    AT("+COPS?")    # Check opertaor info
    AT("+CSQ")      # Get signal strength
    AT('+CPSI?')    # Get more detailed signal info
    AT('+CBAND?')   # Get band
    # GPRS info
    AT("+CGREG?")   # Get network registration status
    AT("+CGACT?")   # Show PDP context state
    AT('+CGPADDR')  # Show PDP address

    # Check nb-iot Status
    AT('+CGNAPN')


def ping(apn="mobile.o2.co.uk", ip="", dest="www.google.com"):
    print("++++++++++++++++++++ PING +++++++++++++++++++++\n")
    cstt = AT('+CSTT?')
    if apn not in cstt:
        AT('+CSTT="{}"'.format(apn))
        AT('+CIICR')
    AT('+CIFSR', success=ip)
    AT('+CIPPING="{}"'.format(dest))


def ntp(apn="mobile.o2.co.uk", dest="pool.ntp.org"):
    print("++++++++++++++++++++ NTP +++++++++++++++++++++\n")
    AT('+SAPBR=3,1,"APN","{}"'.format(apn))
    AT('+SAPBR=1,1')
    AT('+SAPBR=2,1')
    AT('+CNTP="{}",0,1,1'.format(dest))
    AT('+CNTP', timeout=3, success="+CNTP")
    AT('+SAPBR=0,1')


def httpGet(apn="mobile.o2.co.uk",dest="http://davidpa.pythonanywhere.com"):
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


def pdp(apn="payandgo.o2.co.uk"):
    AT("+CGATT=1")
    res = AT("+CNACT=1", failure="DEACTIVE")
    if "DEACTIVE" in res:
        AT("+CGATT=0")
        AT("+CGDCONT=1,\"IP\",\"\"")#.format("payandgo.o2.co.uk" if apn == "o2" else "o2"))
        AT("+CGATT=1")
        res = AT("+CNACT=1", failure="DEACTIVE")
        if "DEACTIVE" in res: # sure-fire way of activating pdp context
            AT("+CGATT=0")
            AT("+CGDCONT=1,\"IP\",\"{}\"".format("payandgo.o2.co.uk"))
            AT("+CGATT=1")
            res = AT("+CNACT=1", failure="DEACTIVE")
    return res


def sslconf(rootca,clientca,clientkey,ip,rootonly=False):
    AT("+CNACT?",success=ip)
    AT("+CFSGFIS=3,\"{}\"".format(rootca))
    AT("+CFSGFIS=3,\"{}\"".format(clientca))
    AT("+CFSGFIS=3,\"{}\"".format(clientkey))
    AT("+CSSLCFG=convert,2,{}".format(rootca))
    if not rootonly:
        AT("+CSSLCFG=convert,1,{},{}".format(clientca,clientkey))
        AT("+SMSSL=1,{},{}".format(rootca,clientca))
    else:
        AT("+SMSSL=1,{},\"\"".format(rootca))
    AT("+CSSLCFG=\"sslversion\",0,3")



def mqttconf(clientid, url, port, username=None, password=None, topic=None):
    AT("+SMCONF=\"clientid\",\"{}\"".format(clientid))
    AT("+SMCONF=\"url\",\"{}\",\"{}\"".format(url,port))
    AT("+SMCONF=\"KEEPTIME\",60")
    if username:
        AT("+SMCONF=\"username\",\"{}\"".format(username))
    if password:
        AT("+SMCONF=\"password\",\"{}\"".format(password))
    if topic:
        AT("+SMCONF=\"topic\",\"{}\"".format(topic))


def mqttconn():
    AT("+SMDISC")
    AT("+SMCONN",timeout=10)


def mqttdisc():
    AT("+SMDISC")


def mqttpub(topic="basicPubSub", message="Hello World!", raw=False):
    AT("+SMPUB=\"{}\",{},1,0".format(topic, len(message)))
    sendData(message, raw)
    response = wait(success="OK", failure="ERROR")
    if "+CME ERROR" in response:
        print(response[1])
    print("TIMEOUT") if "TIMEOUT" in response else print("<---", response[1])


def mqttsub(topic="basicPubSub"):
    AT("+SMSUB=\"{}\",1".format(topic))


def mqttunsub(topic="basicPubSub"):
    AT("+SMUNSUB=\"{}\"".format(topic))


def getapnip():
    cgcontrdp = AT("+CGCONTRDP") # Get APN and IP address

    try:
        apn = cgcontrdp[1].split(",")[2]
        ip = cgcontrdp[1].split(",")[3]
    except:
        apn = ""
        ip = ""
    return apn, ip


def wireless(apn, ip):
    AT("+CIPSHUT")
    cstt = AT('+CSTT?')[1].strip().split(',')[0]
    idx = cstt.find('\"')
    if apn != cstt[idx+1:-1]:
        AT('+CSTT="{}"'.format(apn))
    AT('+CIICR')
    AT('+CIFSR', success=ip)


def barcode_name(code):
    if(code.type() == image.EAN2):
        return "EAN2"
    if(code.type() == image.EAN5):
        return "EAN5"
    if(code.type() == image.EAN8):
        return "EAN8"
    if(code.type() == image.UPCE):
        return "UPCE"
    if(code.type() == image.ISBN10):
        return "ISBN10"
    if(code.type() == image.UPCA):
        return "UPCA"
    if(code.type() == image.EAN13):
        return "EAN13"
    if(code.type() == image.ISBN13):
        return "ISBN13"
    if(code.type() == image.I25):
        return "I25"
    if(code.type() == image.DATABAR):
        return "DATABAR"
    if(code.type() == image.DATABAR_EXP):
        return "DATABAR_EXP"
    if(code.type() == image.CODABAR):
        return "CODABAR"
    if(code.type() == image.CODE39):
        return "CODE39"
    if(code.type() == image.PDF417):
        return "PDF417"
    if(code.type() == image.CODE93):
        return "CODE93"
    if(code.type() == image.CODE128):
        return "CODE128"


def takePicture():
    img = sensor.snapshot()
    return img


def imgToChunks(img, chunk_size=512):
    byte_arr = img.compress(quality=50).bytearray()
    #div, mod = divmod(len(byte_arr), chunk_size)
    #send_num = div + 1 if mod > 0 else 0
    l = lambda byte_arr, x: [byte_arr[i:i+x] for i in range(0, len(byte_arr), x)]
    msgs = l(bytes(byte_arr), chunk_size)
    print(binascii.hexlify(bytes(byte_arr)))
    return msgs


def mqttsendimg(msgs, headers=None):
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
    sensor.reset()
    sensor.set_pixformat(sensor.GRAYSCALE)
    sensor.set_framesize(sensor.VGA) # High Res!
    sensor.set_windowing((640, 80)) # V Res of 80 == less work (40 for 2X the speed).
    sensor.skip_frames(time = 2000)
    sensor.set_auto_gain(False)  # must turn this off to prevent image washout...
    sensor.set_auto_whitebal(False)  # must turn this off to prevent image washout...


def setRGB565():
    sensor.reset()                         # Reset and initialize the sensor.
    sensor.set_pixformat(sensor.RGB565)    # Set pixel format to RGB565 (or GRAYSCALE)
    sensor.set_framesize(sensor.QVGA)      # Set frame size to QVGA (320x240)
    sensor.set_windowing((240, 240))       # Set 240x240 window.
    sensor.skip_frames(time=2000)          # Let the camera adjust.


def modelDetect(model, labels):
    while(True):
        green_led.on()
        time.sleep_ms(200)
        green_led.off()

        clock.tick()

        img = sensor.snapshot()

        # net.classify() will run the network on an roi in the image (or on the whole image if the roi is not
        # specified). A classification score output vector will be generated for each location. At each scale the
        # detection window is moved around in the ROI using x_overlap (0-1) and y_overlap (0-1) as a guide.
        # If you set the overlap to 0.5 then each detection window will overlap the previous one by 50%. Note
        # the computational work load goes WAY up the more overlap. Finally, for multi-scale matching after
        # sliding the network around in the x/y dimensions the detection window will shrink by scale_mul (0-1)
        # down to min_scale (0-1). For example, if scale_mul is 0.5 the detection window will shrink by 50%.
        # Note that at a lower scale there's even more area to search if x_overlap and y_overlap are small...

        # Setting x_overlap=-1 forces the window to stay centered in the ROI in the x direction always. If
        # y_overlap is not -1 the method will search in all vertical positions.

        # Setting y_overlap=-1 forces the window to stay centered in the ROI in the y direction always. If
        # x_overlap is not -1 the method will serach in all horizontal positions.

        # default settings just do one detection... change them to search the image...
        for obj in tf.classify(model, img, min_scale=1.0, scale_mul=0.5, x_overlap=-1, y_overlap=-1):
            print("**********\nDetections at [x=%d,y=%d,w=%d,h=%d]" % obj.rect())
            for i in range(len(obj.output())):
                print("%s = %f" % (labels[i], obj.output()[i]))
            img.draw_rectangle(obj.rect())
            img.draw_string(obj.x()+3, obj.y()-1, labels[obj.output().index(max(obj.output()))], mono_space = False)

            if max(obj.output()) > 0.95: # HIGH CONFIDENCE
                return img, labels[obj.output().index(max(obj.output()))]
        print(clock.fps(), "fps")


if __name__ == "__main__":
    net = 'trained.tflite'
    labels = ['background', 'Damaged Parcel', 'Parcel']
    red_led = pyb.LED(1)
    green_led = pyb.LED(2)
    blue_led = pyb.LED(3)

    red_led.on()

    while "OK" not in AT():
        pass

    red_led.off()


    init_checks()
    apn, ip = getapnip()

    #Get PDP active
    pdp(apn=apn)
    #print(apn,ip)

    ##PING##
    #ping(apn=apn,ip=ip)

    ##GET NTP TIME##
    #time.sleep(2)
    #ntp(apn=apn, dest="pool.ntp.org")

    #httpGet()
    #httpPut

    #wireless(apn=apn,ip=ip)
    #mqttsub(topic="sdk/test/Python")
    #mqttunsub(topic="sdk/test/Python")

    sslconf(rootca="rootleg.pem",clientca="clientcert.pem",clientkey="clientkey.pem",ip=ip,rootonly=False)
    mqttconf(clientid="simcom", url="a1qrdh5dmin77y.iot.eu-west-2.amazonaws.com", port="8883", topic="sdk/test/Python")

    #img = takePicture()
    #msgs = imgToChunks(img, chunk_size=512)

    #mqttconn()
    #mqttsendimg(msgs)
    #mqttdisc()

    setGRAYSCALE()  # Set grayscale for reading barcode

    ####BAR CODE READING####
    while(True):
        blue_led.on()
        time.sleep_ms(200)
        blue_led.off()

        clock.tick()
        img = sensor.snapshot()
        codes = img.find_barcodes()
        for code in codes:
            img.draw_rectangle(code.rect())
            print_args = (barcode_name(code), code.payload(), (180 * code.rotation()) / math.pi, code.quality(), clock.fps())
            print("Barcode %s, Payload \"%s\", rotation %f (degrees), quality %d, FPS %f" % print_args)
            #Add one time read only restriction
            time.sleep(5)

            setRGB565() # Set to RGB to use image classification model
            imgout, outlabel = modelDetect(model=net, labels=labels)

            msgs = imgToChunks(imgout, chunk_size=512)
            mqttconn()
            mqttsendimg(msgs=msgs, headers=(barcode_name(code),code.payload(),outlabel))
            mqttdisc()
            setGRAYSCALE()
            break
        if not codes:
            print("FPS %f" % clock.fps())
