"""ST3215 시리얼 버스 서보 프로토콜 - 공용 저수준 드라이버.
scripts/test_st3215_serial.py(벤치 테스트)와 scripts/calibrate_st3215.py
(캘리브레이션)가 공유하는 모듈. Feetech SCS/STS 프로토콜을 pyserial로 직접
구현 (ptz/sketch/health_care_ptz.ino 의 st.Ping/st.WritePosEx 와 동일한
레지스터 주소 사용).

레지스터 주소/부호비트는 huggingface/lerobot의 feetech 구현
(src/lerobot/motors/feetech/{feetech.py,tables.py})으로 검증됨:
  - Homing_Offset(addr 31, 2byte): 부호비트 bit11 (매그니튜드 최대 ±2047)
  - Present_Position(addr 56, 2byte): 부호비트 bit15
  두 레지스터의 부호비트 위치가 다르므로 절대 혼용하지 말 것 - 혼용하면
  음수 오프셋이 완전히 다른 값으로 인코딩되어 서보가 예상 못 한 위치로
  회전할 수 있음(2026-07-17 실기 사고, docs/issues/ 참고).
"""
import serial

BROADCAST_ID = 0xFE

INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03

ADDR_ID = 5
ADDR_MODEL_L = 3
ADDR_OFS_L = 31          # Homing_Offset (EEPROM, sign-magnitude bit11, 물리 이동 없이 논리각 재정의)
ADDR_MODE = 33
ADDR_TORQUE_ENABLE = 40
ADDR_ACC = 41
ADDR_GOAL_POSITION_L = 42
ADDR_GOAL_SPEED_L = 46
ADDR_LOCK = 55
ADDR_PRESENT_POSITION_L = 56
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMPERATURE = 63

MODE_POSITION = 0
MODE_WHEEL = 1  # 연속 회전(속도 제어) - 목표위치 필드 무시

TICKS_PER_DEG = 4095.0 / 360.0

PRESENT_POSITION_SIGN_BIT = 15
HOMING_OFFSET_SIGN_BIT = 11


class ServoError(Exception):
    pass


def _checksum(payload: list) -> int:
    return (~sum(payload)) & 0xFF


def _build_packet(servo_id: int, instruction: int, params: list) -> bytes:
    length = len(params) + 2  # instruction + checksum
    body = [servo_id, length, instruction] + params
    return bytes([0xFF, 0xFF] + body + [_checksum(body)])


def _read_status(ser: serial.Serial, expect_param_len: int):
    header = ser.read(4)
    if len(header) < 4 or header[0] != 0xFF or header[1] != 0xFF:
        raise ServoError(f"응답 헤더 없음/깨짐: {header!r} (배선/전원/baudrate 확인)")
    servo_id, length = header[2], header[3]
    rest = ser.read(length)  # error(1) + params(length-2) + checksum(1)
    if len(rest) < length:
        raise ServoError("응답 타임아웃 - 서보 ID/전원/GND 공통 여부 확인")
    error, params, checksum = rest[0], list(rest[1:-1]), rest[-1]
    if _checksum([servo_id, length, error] + params) != checksum:
        raise ServoError("체크섬 불일치 - 노이즈/연장선 신호감쇠 의심")
    if error != 0:
        raise ServoError(f"서보 에러 플래그: 0x{error:02X}")
    if expect_param_len is not None and len(params) != expect_param_len:
        raise ServoError(f"응답 길이 예상과 다름: {params}")
    return params


def ping(ser: serial.Serial, servo_id: int) -> int:
    ser.reset_input_buffer()
    ser.write(_build_packet(servo_id, INST_PING, []))
    _read_status(ser, 0)
    return read_word(ser, servo_id, ADDR_MODEL_L)


def read_bytes(ser: serial.Serial, servo_id: int, addr: int, length: int) -> list:
    ser.reset_input_buffer()
    ser.write(_build_packet(servo_id, INST_READ, [addr, length]))
    return _read_status(ser, length)


def read_word(ser: serial.Serial, servo_id: int, addr: int) -> int:
    lo, hi = read_bytes(ser, servo_id, addr, 2)
    return lo | (hi << 8)


def _decode_sign_magnitude(raw: int, sign_bit_index: int) -> int:
    direction_bit = (raw >> sign_bit_index) & 1
    magnitude = raw & ((1 << sign_bit_index) - 1)
    return -magnitude if direction_bit else magnitude


def _encode_sign_magnitude(value: int, sign_bit_index: int) -> int:
    max_magnitude = (1 << sign_bit_index) - 1
    magnitude = min(abs(int(round(value))), max_magnitude)
    direction_bit = 1 if value < 0 else 0
    return (direction_bit << sign_bit_index) | magnitude


def read_position_ticks(ser: serial.Serial, servo_id: int) -> int:
    return _decode_sign_magnitude(read_word(ser, servo_id, ADDR_PRESENT_POSITION_L), PRESENT_POSITION_SIGN_BIT)


def read_position_deg(ser: serial.Serial, servo_id: int) -> float:
    return read_position_ticks(ser, servo_id) / TICKS_PER_DEG


def read_offset(ser: serial.Serial, servo_id: int) -> int:
    return _decode_sign_magnitude(read_word(ser, servo_id, ADDR_OFS_L), HOMING_OFFSET_SIGN_BIT)


def write_offset(ser: serial.Serial, servo_id: int, value: int):
    raw = _encode_sign_magnitude(value, HOMING_OFFSET_SIGN_BIT)
    write_byte(ser, servo_id, ADDR_OFS_L, raw & 0xFF)
    write_byte(ser, servo_id, ADDR_OFS_L + 1, (raw >> 8) & 0xFF)


def write_byte(ser: serial.Serial, servo_id: int, addr: int, value: int):
    ser.reset_input_buffer()
    ser.write(_build_packet(servo_id, INST_WRITE, [addr, value & 0xFF]))
    _read_status(ser, 0)


def write_pos_ex(ser: serial.Serial, servo_id: int, deg: float, speed: int = 569, acc: int = 20):
    """health_care_ptz.ino 의 BUS_SPEED(≈569 tick/s, STEP_DELAY 20ms/° 환산)와 동일 기본값."""
    tick = max(0, min(4095, round(deg * TICKS_PER_DEG)))
    params = [
        acc,
        tick & 0xFF, (tick >> 8) & 0xFF,
        0, 0,  # goal time - 미사용
        speed & 0xFF, (speed >> 8) & 0xFF,
    ]
    ser.reset_input_buffer()
    ser.write(_build_packet(servo_id, INST_WRITE, [ADDR_ACC] + params))
    _read_status(ser, 0)


def set_id(ser: serial.Serial, current_id: int, new_id: int):
    """EEPROM ID 변경. 실제 반영은 서보 전원 재투입(power-cycle) 후 이뤄짐 -
    unlock/write/lock 모두 current_id로 보내야 함 (Feetech 펌웨어 동작)."""
    write_byte(ser, current_id, ADDR_LOCK, 0)       # EEPROM unlock
    write_byte(ser, current_id, ADDR_ID, new_id)     # ID 레지스터 기록
    write_byte(ser, current_id, ADDR_LOCK, 1)       # EEPROM lock


def set_mode(ser: serial.Serial, servo_id: int, mode: int):
    write_byte(ser, servo_id, ADDR_LOCK, 0)
    write_byte(ser, servo_id, ADDR_MODE, mode)
    write_byte(ser, servo_id, ADDR_LOCK, 1)


def write_wheel_speed(ser: serial.Serial, servo_id: int, speed: int, acc: int = 50):
    """휠 모드 전용 - 목표위치는 0으로 채우고 속도만 부호(sign-magnitude, bit15)로 방향 지정."""
    magnitude = min(abs(speed), 0x7FFF)
    raw = magnitude | 0x8000 if speed < 0 else magnitude
    params = [
        acc,
        0, 0,  # 목표 위치 - 휠 모드에서는 무시됨
        0, 0,  # goal time - 미사용
        raw & 0xFF, (raw >> 8) & 0xFF,
    ]
    ser.reset_input_buffer()
    ser.write(_build_packet(servo_id, INST_WRITE, [ADDR_ACC] + params))
    _read_status(ser, 0)
