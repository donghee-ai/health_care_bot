"""ST3215 yaw/pitch 캘리브레이션 - 재조립 후 재사용하는 전용 스크립트.
프로토콜 저수준 구현은 scripts/st3215_bus.py 공용 모듈 참고. 순수 동작
테스트(ping/read/move/sweep 등)는 scripts/test_st3215_serial.py 로 분리돼
있음 - 이 스크립트는 "현재 물리 위치를 중앙으로 재정의"만 다룬다.

원리: 서보 EEPROM의 Homing_Offset(addr 31, 부호비트 bit11)을 조정해서
Present_Position = Actual_Position - Homing_Offset 관계로 현재 위치가
tick 2047(0~4095 정중앙)로 읽히게 만든다 - 서보는 물리적으로 전혀
움직이지 않는다 (LeRobot huggingface/lerobot의 feetech 구현으로 검증된
공식/부호비트, 상세는 docs/issues/2026-07-17_01_...md).

[!] torque가 켜진 채로 offset을 바꾸면, Present_Position이 순간적으로
달라진 것처럼 보여 서보가 옛 Goal_Position으로 실제 회전할 수 있다(실기
사고 이력 있음) - 그래서 calibrate 명령은 항상 torque off -> 계산 ->
Goal_Position 동기화 -> torque on 순서를 자동으로 지킨다.

사용법:
  python scripts/calibrate_st3215.py --port COM5 calibrate     # 추천: ID 1,2 전체, torque 안전 처리 포함
  python scripts/calibrate_st3215.py --port COM5 --id 1 set-center   # 서보 하나만, torque=0 상태 직접 확인 필요
  python scripts/calibrate_st3215.py --port COM5 stop          # 긴급 정지 - torque 즉시 OFF
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from st3215_bus import (
    ServoError,
    ADDR_LOCK,
    ADDR_TORQUE_ENABLE,
    TICKS_PER_DEG,
    read_bytes,
    read_offset,
    write_offset,
    read_position_deg,
    read_position_ticks,
    write_byte,
    write_pos_ex,
)

import serial


def calibrate_center(ser: serial.Serial, servo_id: int) -> float:
    """서보를 움직이지 않고 '지금 이 물리 위치'를 tick 2047(0~4095 정중앙, LeRobot의
    half-turn 컨벤션과 동일)로 재정의 (Homing_Offset EEPROM).

    [!] torque가 켜진 상태에서 이 함수를 쓰면, offset 변경으로 Present_Position이
    갑자기 바뀐 것처럼 보여 서보가 남아있던 Goal_Position 쪽으로 실제로 회전할 수
    있다(실기 사고 이력 있음) - 반드시 Torque_Enable=0인 상태에서만 호출할 것.
    (전체 안전 절차가 필요하면 full_calibration()을 쓸 것.)"""
    torque = read_bytes(ser, servo_id, ADDR_TORQUE_ENABLE, 1)[0]
    if torque != 0:
        raise ServoError(f"ID={servo_id} torque가 켜져 있음 - 안전을 위해 중단 (먼저 torque off)")

    write_byte(ser, servo_id, ADDR_LOCK, 0)  # EEPROM unlock
    old_offset = read_offset(ser, servo_id)
    actual = read_position_ticks(ser, servo_id) + old_offset  # Actual = Present + Homing_Offset
    new_offset = actual - 2047
    write_offset(ser, servo_id, new_offset)
    write_byte(ser, servo_id, ADDR_LOCK, 1)  # lock

    return read_position_deg(ser, servo_id)


def full_calibration(ser: serial.Serial, servo_id: int) -> dict:
    """재조립 후 재사용 가능한 전체 안전 캘리브레이션 절차 (2026-07-17 실기 사고 이후
    확립됨, docs/issues/2026-07-17_01_... 참고):
      1. torque가 켜져 있으면 먼저 끈다 (검증 없이 EEPROM에 쓰지 않기 위해)
      2. calibrate_center()로 '지금 이 물리 위치'를 tick 2047(정중앙)로 재정의
      3. Goal_Position을 새 Present_Position에 동기화 (torque 재활성화 시 오차 0)
      4. torque를 다시 켠다 - 항상 켜진 상태로 끝남(호출 전 꺼져있었더라도)"""
    torque_before = read_bytes(ser, servo_id, ADDR_TORQUE_ENABLE, 1)[0]
    if torque_before:
        write_byte(ser, servo_id, ADDR_TORQUE_ENABLE, 0)

    before_deg = read_position_deg(ser, servo_id)
    after_deg = calibrate_center(ser, servo_id)  # 이 시점엔 torque=0 보장됨

    write_pos_ex(ser, servo_id, after_deg, speed=569, acc=20)  # goal을 새 위치로 동기화
    write_byte(ser, servo_id, ADDR_TORQUE_ENABLE, 1)

    return {
        "before_deg": before_deg,
        "after_deg": after_deg,
        "final_tick": read_position_ticks(ser, servo_id),
        "torque_was_on": bool(torque_before),
    }


def cmd_set_center(ser, args):
    before = read_position_deg(ser, args.id)
    after = calibrate_center(ser, args.id)
    after_tick = round(after * TICKS_PER_DEG)
    print(f"[OK] ID={args.id} 현재 물리 위치를 tick 2047(정중앙, {after:.1f}deg)로 재정의 (이동 전 표시값 {before:.1f}deg)")
    if abs(after_tick - 2047) > 5:
        print("[WARN] tick 2047 근처가 아닙니다 - 재확인하세요.")


def cmd_calibrate(ser, args):
    print("짐벌을 원하는 중앙 자세로 손으로 맞춰둔 상태에서 실행하세요 (서보는 안 움직입니다).")
    for sid in (1, 2):
        r = full_calibration(ser, sid)
        torque_note = "torque 켜진 채였음 -> off/재계산/on 순서로 안전 처리" if r["torque_was_on"] else "torque 꺼져있었음 -> 계산 후 on으로 마무리"
        print(f"[OK] ID={sid}: {r['before_deg']:.1f}deg -> tick {r['final_tick']}(정중앙, {r['after_deg']:.1f}deg)  {torque_note}")
        if abs(r["final_tick"] - 2047) > 5:
            print(f"[WARN] ID={sid} tick 2047 근처가 아닙니다 - 재확인하세요.")


def cmd_stop(ser, args):
    """긴급 정지 - ID 1,2 torque를 즉시 끈다 (다른 터미널에서 move 진행 중일 때도 바로 실행 가능)."""
    for sid in (1, 2):
        write_byte(ser, sid, ADDR_TORQUE_ENABLE, 0)
        print(f"[OK] ID={sid} torque OFF")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True, help="예: COM5 (Windows) / /dev/ttyUSB0 (Linux)")
    parser.add_argument("--baud", type=int, default=1_000_000, help="ST3215 공장 기본값")
    parser.add_argument("--id", type=int, default=1, help="set-center 전용 (calibrate/stop은 항상 ID 1,2 둘 다)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("calibrate", help="재조립 후 짐벌 전체(ID 1,2) 재캘리브레이션 - torque on/off까지 전부 알아서 안전하게 처리 (추천)")
    sub.add_parser("set-center", help="--id 서보 하나만: 현재 물리 위치를 tick 2047(정중앙)로 재정의. torque=0 상태여야 함(직접 확인 필요)")
    sub.add_parser("stop", help="긴급 정지 - ID 1,2 torque 즉시 OFF (다른 터미널에서 move 도중에도 실행 가능)")

    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.3)
    except Exception as e:
        print(f"[FAIL] 포트 열기 실패: {e}")
        sys.exit(1)

    try:
        {
            "calibrate": cmd_calibrate,
            "set-center": cmd_set_center,
            "stop": cmd_stop,
        }[args.cmd](ser, args)
    except ServoError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
