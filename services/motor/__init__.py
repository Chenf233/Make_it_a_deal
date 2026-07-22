import Hobot.GPIO as GPIO
import time
import threading
from enum import Enum

PUL_PIN1 = 13
DIR_PIN1 = 11
PUL_PIN2 = 16
DIR_PIN2 = 15
PULSES_PER_HALF_REV = 400

MOTOR3_CW_PIN = 37
MOTOR3_CCW_PIN = 35

LEFT_FORWARD_PIN = 26
LEFT_BACKWARD_PIN = 29
RIGHT_FORWARD_PIN = 36
RIGHT_BACKWARD_PIN = 32
WHEEL_PINS = (
    LEFT_FORWARD_PIN,
    LEFT_BACKWARD_PIN,
    RIGHT_FORWARD_PIN,
    RIGHT_BACKWARD_PIN,
)

POSITION_B = 0.0
POSITION_MIDDLE = 0.5
POSITION_A = 1.0
FULL_TRAVEL_SECONDS = 6.0


class WheelMotion(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    TURN_LEFT = "turn-left"
    TURN_RIGHT = "turn-right"


class WheelDestination(str, Enum):
    A = "a"
    B = "b"


class WheelBusyError(RuntimeError):
    pass


MOTION_PINS = {
    WheelMotion.FORWARD: (LEFT_FORWARD_PIN, RIGHT_FORWARD_PIN),
    WheelMotion.BACKWARD: (LEFT_BACKWARD_PIN, RIGHT_BACKWARD_PIN),
    WheelMotion.TURN_LEFT: (LEFT_BACKWARD_PIN, RIGHT_FORWARD_PIN),
    WheelMotion.TURN_RIGHT: (LEFT_FORWARD_PIN, RIGHT_BACKWARD_PIN),
}

_initialized = False
_wheel_lock = threading.Lock()
_wheel_motion = None
_wheel_mode = None
_wheel_position = POSITION_MIDDLE
_wheel_destination = None
_auto_start_position = None
_auto_started_at = None
_auto_duration = None
_motion_token = 0

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
    for pin in WHEEL_PINS:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
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

def _set_wheel_outputs(high_pins=()):
    for pin in WHEEL_PINS:
        GPIO.output(pin, GPIO.LOW)
    for pin in high_pins:
        GPIO.output(pin, GPIO.HIGH)


def _estimated_position_locked():
    if _wheel_mode != "automatic" or not _auto_duration:
        return _wheel_position

    elapsed = max(0.0, time.monotonic() - _auto_started_at)
    progress = min(1.0, elapsed / _auto_duration)
    target = POSITION_A if _wheel_destination == WheelDestination.A else POSITION_B
    return _auto_start_position + (target - _auto_start_position) * progress


def _status_locked():
    position = _estimated_position_locked()
    remaining_seconds = 0.0
    if _wheel_mode == "automatic" and _auto_duration:
        elapsed = max(0.0, time.monotonic() - _auto_started_at)
        remaining_seconds = max(0.0, _auto_duration - elapsed)

    return {
        "mode": _wheel_mode,
        "motion": _wheel_motion.value if _wheel_motion else None,
        "destination": _wheel_destination.value if _wheel_destination else None,
        "position": round(position, 4),
        "remaining_seconds": round(remaining_seconds, 2),
        "busy": _wheel_motion is not None,
    }


def get_wheel_status():
    with _wheel_lock:
        return _status_locked()


def start_manual_motion(motion):
    global _wheel_motion, _wheel_mode, _wheel_position, _wheel_destination
    global _auto_start_position, _auto_started_at, _auto_duration, _motion_token

    init()
    motion = WheelMotion(motion)
    with _wheel_lock:
        if _wheel_motion is not None:
            if _wheel_mode == "manual" and _wheel_motion == motion:
                return _status_locked()
            raise WheelBusyError(f"底盘正在执行 {_wheel_motion.value}，请先停止当前动作")

        _set_wheel_outputs(MOTION_PINS[motion])
        _wheel_motion = motion
        _wheel_mode = "manual"
        _wheel_position = POSITION_MIDDLE
        _wheel_destination = None
        _auto_start_position = None
        _auto_started_at = None
        _auto_duration = None
        _motion_token += 1
        return _status_locked()


def stop_manual_motion(motion):
    global _wheel_motion, _wheel_mode, _motion_token

    init()
    motion = WheelMotion(motion)
    with _wheel_lock:
        if _wheel_mode != "manual" or _wheel_motion != motion:
            return False, _status_locked()

        _set_wheel_outputs()
        _wheel_motion = None
        _wheel_mode = None
        _motion_token += 1
        return True, _status_locked()


def start_destination(destination):
    global _wheel_motion, _wheel_mode, _wheel_position, _wheel_destination
    global _auto_start_position, _auto_started_at, _auto_duration, _motion_token

    init()
    destination = WheelDestination(destination)
    target = POSITION_A if destination == WheelDestination.A else POSITION_B

    with _wheel_lock:
        if _wheel_motion is not None:
            raise WheelBusyError(f"底盘正在执行 {_wheel_motion.value}，请先停止当前动作")

        distance = abs(target - _wheel_position)
        duration = distance * FULL_TRAVEL_SECONDS
        if duration <= 0.001:
            _wheel_position = target
            return {"token": None, "duration_seconds": 0.0, "status": _status_locked()}

        motion = WheelMotion.FORWARD if target > _wheel_position else WheelMotion.BACKWARD
        _set_wheel_outputs(MOTION_PINS[motion])
        _wheel_motion = motion
        _wheel_mode = "automatic"
        _wheel_destination = destination
        _auto_start_position = _wheel_position
        _auto_started_at = time.monotonic()
        _auto_duration = duration
        _motion_token += 1
        return {
            "token": _motion_token,
            "duration_seconds": round(duration, 3),
            "status": _status_locked(),
        }


def complete_destination(token):
    global _wheel_motion, _wheel_mode, _wheel_position, _wheel_destination
    global _auto_start_position, _auto_started_at, _auto_duration, _motion_token

    init()
    with _wheel_lock:
        if token != _motion_token or _wheel_mode != "automatic":
            return False, _status_locked()

        _set_wheel_outputs()
        _wheel_position = POSITION_A if _wheel_destination == WheelDestination.A else POSITION_B
        _wheel_motion = None
        _wheel_mode = None
        _wheel_destination = None
        _auto_start_position = None
        _auto_started_at = None
        _auto_duration = None
        _motion_token += 1
        return True, _status_locked()


def stop_all_wheels():
    global _wheel_motion, _wheel_mode, _wheel_position, _wheel_destination
    global _auto_start_position, _auto_started_at, _auto_duration, _motion_token

    init()
    with _wheel_lock:
        if _wheel_mode == "automatic":
            _wheel_position = _estimated_position_locked()
        _set_wheel_outputs()
        _wheel_motion = None
        _wheel_mode = None
        _wheel_destination = None
        _auto_start_position = None
        _auto_started_at = None
        _auto_duration = None
        _motion_token += 1
        return _status_locked()

__all__ = [
    "WHEEL_PINS",
    "WheelBusyError",
    "WheelDestination",
    "WheelMotion",
    "complete_destination",
    "get_wheel_status",
    "half_turn",
    "half_turn2",
    "rotate_turns",
    "start_continuous",
    "stop_continuous",
    "motor3_cw",
    "motor3_ccw",
    "start_destination",
    "start_manual_motion",
    "stop_manual_motion",
    "stop_all_wheels",
]
