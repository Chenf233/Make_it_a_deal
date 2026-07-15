import logging
import threading
from typing import Iterable

from services.BuzzerLight import BUZZER1_PIN, BUZZER2_PIN, start_loop, stop_loop
from services.electromagnet import LOCK_PIN_1, LOCK_PIN_2, init as init_locks
from services.electromagnet import lock as lock_pin
from services.electromagnet import lock_all as lock_all_pins
from services.electromagnet import unlock as unlock_pin

logger = logging.getLogger("SmartStation")

CABINET_HARDWARE_MAP = {
    "A01": {"buzzer_pin": BUZZER1_PIN, "lock_pin": LOCK_PIN_1},
    "A02": {"buzzer_pin": BUZZER2_PIN, "lock_pin": LOCK_PIN_2},
}

_state_lock = threading.Lock()
_open_cabinets_by_user: dict[int, set[str]] = {}


def init():
    init_locks()
    lock_all_pins()
    logger.info("Cabinet hardware manager initialized; all configured locks are engaged.")


def normalize_cabinet_number(cabinet_number: str) -> str:
    return (cabinet_number or "").strip().upper()


def _unique_cabinet_numbers(cabinet_numbers: Iterable[str]) -> list[str]:
    unique = []
    seen = set()
    for cabinet_number in cabinet_numbers:
        normalized = normalize_cabinet_number(cabinet_number)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _config_for(cabinet_number: str) -> dict | None:
    normalized = normalize_cabinet_number(cabinet_number)
    return CABINET_HARDWARE_MAP.get(normalized)


def start_cabinet_buzzer(cabinet_number: str) -> bool:
    cfg = _config_for(cabinet_number)
    if not cfg:
        logger.warning("Cabinet %s has no buzzer mapping; skipped.", cabinet_number)
        return False
    start_loop(cfg["buzzer_pin"])
    return True


def stop_cabinet_buzzer(cabinet_number: str) -> bool:
    cfg = _config_for(cabinet_number)
    if not cfg:
        logger.warning("Cabinet %s has no buzzer mapping; skipped.", cabinet_number)
        return False
    stop_loop(cfg["buzzer_pin"])
    return True


def unlock_cabinet(cabinet_number: str) -> bool:
    cfg = _config_for(cabinet_number)
    if not cfg:
        logger.warning("Cabinet %s has no lock mapping; skipped.", cabinet_number)
        return False
    unlock_pin(cfg["lock_pin"])
    return True


def lock_cabinet(cabinet_number: str) -> bool:
    cfg = _config_for(cabinet_number)
    if not cfg:
        logger.warning("Cabinet %s has no lock mapping; skipped.", cabinet_number)
        return False
    stop_loop(cfg["buzzer_pin"])
    lock_pin(cfg["lock_pin"])
    return True


def close_user_cabinet(user_id: int, cabinet_number: str) -> bool:
    normalized = normalize_cabinet_number(cabinet_number)
    if not normalized:
        return False

    with _state_lock:
        cabinet_numbers = _open_cabinets_by_user.get(user_id)
        if cabinet_numbers and normalized in cabinet_numbers:
            cabinet_numbers.remove(normalized)
            if not cabinet_numbers:
                _open_cabinets_by_user.pop(user_id, None)

    return lock_cabinet(normalized)


def open_cabinet(cabinet_number: str) -> bool:
    normalized = normalize_cabinet_number(cabinet_number)
    cfg = _config_for(normalized)
    if not cfg:
        logger.warning("Cabinet %s has no hardware mapping; skipped.", cabinet_number)
        return False

    unlock_pin(cfg["lock_pin"])
    start_loop(cfg["buzzer_pin"])
    return True


def open_user_cabinets(user_id: int, cabinet_numbers: Iterable[str]) -> dict:
    opened = []
    skipped = []

    for cabinet_number in _unique_cabinet_numbers(cabinet_numbers):
        if open_cabinet(cabinet_number):
            opened.append(cabinet_number)
        else:
            skipped.append(cabinet_number)

    if opened:
        with _state_lock:
            _open_cabinets_by_user.setdefault(user_id, set()).update(opened)
        logger.info("Opened cabinets for user %s: %s", user_id, opened)

    return {"opened": opened, "skipped": skipped}


def _lock_pin_used_by_other_user(lock_pin_value: int, user_id: int) -> bool:
    for other_user_id, cabinet_numbers in _open_cabinets_by_user.items():
        if other_user_id == user_id:
            continue
        for cabinet_number in cabinet_numbers:
            cfg = _config_for(cabinet_number)
            if cfg and cfg["lock_pin"] == lock_pin_value:
                return True
    return False


def lock_user_cabinets(user_id: int) -> dict:
    with _state_lock:
        cabinet_numbers = _open_cabinets_by_user.pop(user_id, set())
        pins_to_lock = []
        skipped = []
        for cabinet_number in cabinet_numbers:
            cfg = _config_for(cabinet_number)
            if not cfg:
                skipped.append(cabinet_number)
                continue
            if not _lock_pin_used_by_other_user(cfg["lock_pin"], user_id):
                pins_to_lock.append((cabinet_number, cfg["lock_pin"]))

    locked = []
    for cabinet_number, pin in pins_to_lock:
        stop_cabinet_buzzer(cabinet_number)
        lock_pin(pin)
        locked.append(cabinet_number)

    if cabinet_numbers:
        logger.info("Locked cabinets for user %s: %s", user_id, locked)
    return {"locked": locked, "skipped": skipped}


def lock_all_cabinets():
    for cabinet_number in CABINET_HARDWARE_MAP:
        stop_cabinet_buzzer(cabinet_number)
    lock_all_pins()
    with _state_lock:
        _open_cabinets_by_user.clear()
    logger.info("All configured cabinet locks are engaged.")


__all__ = [
    "CABINET_HARDWARE_MAP",
    "close_user_cabinet",
    "init",
    "lock_all_cabinets",
    "lock_cabinet",
    "lock_user_cabinets",
    "open_cabinet",
    "open_user_cabinets",
    "start_cabinet_buzzer",
    "stop_cabinet_buzzer",
    "unlock_cabinet",
]
