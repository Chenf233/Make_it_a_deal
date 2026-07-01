import Hobot.GPIO as GPIO
import time
import threading

PUL_PIN1 = 13
DIR_PIN1 = 11
PUL_PIN2 = 16
DIR_PIN2 = 15
PULSES_PER_HALF_REV = 400

MOTOR3_CW_PIN = 37
MOTOR3_CCW_PIN = 35

_initialized = False

def init():
    global _initialized
    if _initialized:
        return
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(PUL_PIN1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PUL_PIN2, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN2, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(MOTOR3_CW_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(MOTOR3_CCW_PIN, GPIO.OUT, initial=GPIO.LOW)
    _initialized = True

init()

def _rotate_blocking(pul_pin, dir_pin, direction, pulses):
    GPIO.output(dir_pin, direction)
    delay = 800 / 1_000_000
    for _ in range(pulses):
        GPIO.output(pul_pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(pul_pin, GPIO.LOW)
        time.sleep(delay)

def half_turn(direction):
    init()
    _rotate_blocking(PUL_PIN1, DIR_PIN1, direction, PULSES_PER_HALF_REV)

def half_turn2(direction):
    init()
    _rotate_blocking(PUL_PIN2, DIR_PIN2, direction, PULSES_PER_HALF_REV)

def rotate_turns(motor_id, direction, turns):
    init()
    pulses = turns * 800
    if motor_id == 1:
        _rotate_blocking(PUL_PIN1, DIR_PIN1, direction, pulses)
    else:
        _rotate_blocking(PUL_PIN2, DIR_PIN2, direction, pulses)

_running_motors = {}
_stop_flags_motors = {}

def _continuous_rotate(pul_pin, dir_pin, direction, stop_flag):
    GPIO.output(dir_pin, direction)
    delay = 800 / 1_000_000
    while not stop_flag.is_set():
        GPIO.output(pul_pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(pul_pin, GPIO.LOW)
        time.sleep(delay)

def start_continuous(motor_id, direction):
    init()
    stop_continuous(motor_id)
    pul, dir = (PUL_PIN1, DIR_PIN1) if motor_id == 1 else (PUL_PIN2, DIR_PIN2)
    stop_flag = threading.Event()
    t = threading.Thread(target=_continuous_rotate, args=(pul, dir, direction, stop_flag), daemon=True)
    t.start()
    _running_motors[motor_id] = t
    _stop_flags_motors[motor_id] = stop_flag

def stop_continuous(motor_id):
    flag = _stop_flags_motors.pop(motor_id, None)
    if flag:
        flag.set()
    t = _running_motors.pop(motor_id, None)
    if t:
        t.join(timeout=2)

def motor3_cw(duration):
    init()
    GPIO.output(MOTOR3_CW_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(MOTOR3_CW_PIN, GPIO.LOW)

def motor3_ccw(duration):
    init()
    GPIO.output(MOTOR3_CCW_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(MOTOR3_CCW_PIN, GPIO.LOW)

__all__ = ["half_turn", "half_turn2", "rotate_turns", "start_continuous", "stop_continuous", "motor3_cw", "motor3_ccw"]
