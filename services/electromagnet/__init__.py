import threading

import Hobot.GPIO as GPIO

LOCK_PIN_1 = 40
LOCK_PIN_2 = 38
LOCK_PINS = (LOCK_PIN_1, LOCK_PIN_2)

_initialized = False
_gpio_lock = threading.Lock()


def init():
    global _initialized
    if _initialized:
        return
    with _gpio_lock:
        if _initialized:
            return
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        for pin in LOCK_PINS:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
        _initialized = True


def lock(pin):
    init()
    with _gpio_lock:
        GPIO.output(pin, GPIO.HIGH)


def unlock(pin):
    init()
    with _gpio_lock:
        GPIO.output(pin, GPIO.LOW)


def lock_all():
    init()
    with _gpio_lock:
        for pin in LOCK_PINS:
            GPIO.output(pin, GPIO.HIGH)


__all__ = ["LOCK_PIN_1", "LOCK_PIN_2", "LOCK_PINS", "init", "lock", "unlock", "lock_all"]
