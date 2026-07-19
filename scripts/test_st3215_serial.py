"""ST3215 단독 시험 스크립트 - USB-TTL 어댑터로 PC에 직결한 서보 벤치 테스트.
Arduino(health_care_ptz.ino)를 거치지 않고 PC가 직접 서보 버스 프로토콜을
말한다. 프로토콜 저수준 구현은 scripts/st3215_bus.py 공용 모듈 참고.

캘리브레이션(현재 위치를 중앙으로 재정의)은 이 스크립트가 아니라
scripts/calibrate_st3215.py 로 분리돼 있음 - 순수 동작 테스트(ping/read/
move/sweep/set-id/dual-spin)만 여기서 다룬다.

배선: USB-TTL 어댑터 TX/RX <-> ST3215 Bus Servo Adapter, GND 공통, 서보 전원
(6~12.6V)은 어댑터 전용 커넥터로 별도 공급.

사용법:
  python scripts/test_st3215_serial.py --port COM5 ping
  python scripts/test_st3215_serial.py --port COM5 --id 1 read
  python scripts/test_st3215_serial.py --port COM5 --id 1 move 90
  python scripts/test_st3215_serial.py --port COM5 --id 1 move -30 --relative   # 현재각 - 30도
  python scripts/test_st3215_serial.py --port COM5 --id 1 sweep
  python scripts/test_st3215_serial.py --port COM5 --id 1 set-id 2
  python scripts/test_st3215_serial.py --port COM5 dual-spin --id-a 1 --id-b 2 --seconds 10
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))   # st3215_bus는 런타임 모듈(src/)

from st3215_bus import (
    ServoError,
    ADDR_PRESENT_VOLTAGE,
    ADDR_PRESENT_TEMPERATURE,
    MODE_POSITION,
    MODE_WHEEL,
    ping,
    read_bytes,
    read_position_deg,
    write_pos_ex,
    set_id,
    set_mode,
    write_wheel_speed,
)

import serial


def cmd_ping(ser, args):
    model = ping(ser, args.id)
    print(f"[OK] ID={args.id} 응답, model number={model}")


def cmd_read(ser, args):
    deg = read_position_deg(ser, args.id)
    voltage = read_bytes(ser, args.id, ADDR_PRESENT_VOLTAGE, 1)[0] / 10.0
    temp = read_bytes(ser, args.id, ADDR_PRESENT_TEMPERATURE, 1)[0]
    print(f"[OK] ID={args.id} pos={deg:.1f}deg  voltage={voltage:.1f}V  temp={temp}C")


def cmd_move(ser, args):
    target = args.degrees
    if args.relative:
        current = read_position_deg(ser, args.id)
        target = current + args.degrees
        print(f"[INFO] 현재 {current:.1f}deg + delta {args.degrees:+.1f}deg -> 목표 {target:.1f}deg")
    write_pos_ex(ser, args.id, target, speed=args.speed, acc=args.acc)
    print(f"[OK] ID={args.id} -> {target:.1f}deg 이동 명령 전송")
    time.sleep(1.5)
    print(f"     현재 위치: {read_position_deg(ser, args.id):.1f}deg")


def cmd_set_id(ser, args):
    set_id(ser, args.id, args.new_id)
    print(f"[OK] ID {args.id} -> {args.new_id} 기록 완료.")
    print(f"     서보 전원을 껐다 켠 뒤(power-cycle) --id {args.new_id} 로 ping 해서 확인하세요.")


def cmd_sweep(ser, args):
    for deg in (90, 60, 120, 90):
        write_pos_ex(ser, args.id, deg, speed=args.speed, acc=args.acc)
        print(f"-> {deg}deg 지시, 도착 대기...")
        time.sleep(2.0)
        print(f"   현재 위치: {read_position_deg(ser, args.id):.1f}deg")


def cmd_dual_spin(ser, args):
    id_a, id_b = args.id_a, args.id_b
    try:
        set_mode(ser, id_a, MODE_WHEEL)
        set_mode(ser, id_b, MODE_WHEEL)
        print(f"[OK] ID={id_a}, ID={id_b} 휠 모드(연속 회전) 전환")

        write_wheel_speed(ser, id_a, args.speed, args.acc)
        write_wheel_speed(ser, id_b, -args.speed, args.acc)  # 데이지체인 반대편이라 반대 부호 = 반대 방향
        print(f"[OK] {args.seconds:.1f}초간 반대 방향 회전 중 (speed={args.speed})...")
        time.sleep(args.seconds)
    finally:
        # 실패하더라도 반드시 정지 + 포지션 모드 복귀 (그대로 두면 PTZ 정상 동작 불가)
        write_wheel_speed(ser, id_a, 0, args.acc)
        write_wheel_speed(ser, id_b, 0, args.acc)
        set_mode(ser, id_a, MODE_POSITION)
        set_mode(ser, id_b, MODE_POSITION)
        print(f"[OK] 정지 + 포지션 모드 복귀 완료")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True, help="예: COM5 (Windows) / /dev/ttyUSB0 (Linux)")
    parser.add_argument("--baud", type=int, default=1_000_000, help="ST3215 공장 기본값")
    parser.add_argument("--id", type=int, default=1)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping")
    sub.add_parser("read")

    p_move = sub.add_parser("move")
    p_move.add_argument("degrees", type=float, help="--relative 없으면 절대각(0~360), 있으면 현재각 기준 delta")
    p_move.add_argument("--relative", action="store_true", help="현재 위치를 먼저 read해서 그 기준으로 delta만큼 이동")
    p_move.add_argument("--speed", type=int, default=569)
    p_move.add_argument("--acc", type=int, default=20)

    p_sweep = sub.add_parser("sweep")
    p_sweep.add_argument("--speed", type=int, default=569)
    p_sweep.add_argument("--acc", type=int, default=20)

    p_set_id = sub.add_parser("set-id")
    p_set_id.add_argument("new_id", type=int)

    p_dual = sub.add_parser("dual-spin")
    p_dual.add_argument("--id-a", type=int, required=True, dest="id_a")
    p_dual.add_argument("--id-b", type=int, required=True, dest="id_b")
    p_dual.add_argument("--speed", type=int, default=1000)
    p_dual.add_argument("--acc", type=int, default=50)
    p_dual.add_argument("--seconds", type=float, default=10.0)

    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.3)
    except Exception as e:
        print(f"[FAIL] 포트 열기 실패: {e}")
        sys.exit(1)

    try:
        {
            "ping": cmd_ping,
            "read": cmd_read,
            "move": cmd_move,
            "sweep": cmd_sweep,
            "set-id": cmd_set_id,
            "dual-spin": cmd_dual_spin,
        }[args.cmd](ser, args)
    except ServoError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
