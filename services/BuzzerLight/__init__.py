import Hobot.GPIO as GPIO
import time
import threading

BUZZER1_PIN = 8
BUZZER2_PIN = 10

LED1_GREEN = 22
LED1_BLUE = 24
LED2_GREEN = 19
LED2_BLUE = 21

_initialized = False
_running = {}
_stop_flags = {}


def init():
    global _initialized
    if _initialized:
        return
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER1_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUZZER2_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED1_GREEN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED1_BLUE, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(LED2_GREEN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED2_BLUE, GPIO.OUT, initial=GPIO.HIGH)
    _initialized = True


init()


def _green_on(pin):
    if pin == BUZZER1_PIN:
        GPIO.output(LED1_GREEN, GPIO.HIGH)
        GPIO.output(LED1_BLUE, GPIO.LOW)
    elif pin == BUZZER2_PIN:
        GPIO.output(LED2_GREEN, GPIO.HIGH)
        GPIO.output(LED2_BLUE, GPIO.LOW)


def _blue_on(pin):
    if pin == BUZZER1_PIN:
        GPIO.output(LED1_GREEN, GPIO.LOW)
        GPIO.output(LED1_BLUE, GPIO.HIGH)
    elif pin == BUZZER2_PIN:
        GPIO.output(LED2_GREEN, GPIO.LOW)
        GPIO.output(LED2_BLUE, GPIO.HIGH)


def beep_twice(pin):
    GPIO.output(pin, GPIO.HIGH)
    _green_on(pin)
    time.sleep(1)
    GPIO.output(pin, GPIO.LOW)
    _blue_on(pin)
    time.sleep(0.5)
    GPIO.output(pin, GPIO.HIGH)
    _green_on(pin)
    time.sleep(0.5)
    GPIO.output(pin, GPIO.LOW)
    _blue_on(pin)


def _loop(pin, stop_flag):
    _green_on(pin)
    while not stop_flag.is_set():
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(1)
    _blue_on(pin)


def start_loop(pin):
    if pin in _running and _running[pin].is_alive():
        return
    stop_flag = threading.Event()
    t = threading.Thread(target=_loop, args=(pin, stop_flag), daemon=True)
    t.start()
    _running[pin] = t
    _stop_flags[pin] = stop_flag


def stop_loop(pin):
    flag = _stop_flags.get(pin)
    if flag:
        flag.set()
    t = _running.get(pin)
    if t:
        t.join(timeout=3)
    _running.pop(pin, None)
    _stop_flags.pop(pin, None)
    GPIO.output(pin, GPIO.LOW)
    _blue_on(pin)