/*
 * health_care_ptz.ino — UNO Q (STM32U585) PTZ yaw/pitch 제어 (ST3215 버스 서보).
 *
 * 하드웨어 (2026-07 변경, PWM 직결 → 시리얼 버스 서보):
 *
 *   [Bus Servo Adapter] --daisy--> [Yaw 서보 ID=1] --daisy--> [Pitch 서보 ID=2]
 *        (전원+제어회로 통합 어댑터, ST3215용)
 *
 *   어댑터 ↔ UNO Q MCU: TTL UART 2선 (TX/RX). Python 브릿지가 이미 USB Serial
 *   (Serial)을 점유하므로, 버스 서보는 별도 하드웨어 UART(BUS_SERVO_SERIAL,
 *   기본 Serial1)를 사용. ⚠ UNO Q 실제 보드에서 TX1/RX1 핀 번호를 실크스크린/
 *   핀맵으로 확인하고 배선할 것 — 여기서는 심볼(Serial1)만 지정.
 *
 *   서보 전원은 어댑터 쪽 전용 커넥터로 공급 (ST3215 정격 6~12.6V, GND는
 *   UNO Q와 공통 필수). MCU 로직 전원과 서보 구동 전원은 분리 추천.
 *
 * ⚠ 배선 전 필수 — ID 사전 설정:
 *   ST3215는 공장 출하 시 모든 서보의 ID가 1. 체인으로 묶기 전에 서보를
 *   하나씩 어댑터에 연결해 SCServo 설정 툴(또는 st.unLockEprom/writeByte)로
 *   yaw=1, pitch=2 로 미리 나눠 기록해야 함. 그대로 체인에 물리면 ID 충돌로
 *   버스가 응답하지 않음.
 *
 * Linux 측 src/ptz_controller.py 가 보내는 텍스트 명령 프로토콜은 기존과 동일
 * (1줄=1명령, '\n' 종결, USB Serial 그대로 사용):
 *   PAN <delta_deg>\n     # yaw(ID=1, 체인 첫 번째) 각도에 delta_deg 더함
 *   TILT <delta_deg>\n    # pitch(ID=2, yaw에서 데이지체인) 각도에 delta_deg 더함
 *   CENTER\n              # yaw/pitch 중심(90°/90°) 복귀
 *   PING\n                # 응답 "PONG" (USB 헬스체크, 버스 서보 상태와 무관)
 *
 * 응답 (디버그):
 *   OK PAN=<deg> TILT=<deg>
 *   ERR <reason>
 *   PONG
 *
 * 필요 라이브러리: Feetech "SCServo" Arduino 라이브러리 (SMS_STS 클래스,
 * ST/SM/STS 시리즈 공용). Library Manager에 없으면 zip 설치.
 * ⚠ 실제 설치된 라이브러리 버전의 API(WritePosEx/Ping 시그니처)를
 * 컴파일 전에 반드시 대조할 것.
 *
 * 회전 속도:
 *   기존 PWM 버전의 STEP_DELAY=20ms/° (손가락 끼임 방지 취지)를 서보 네이티브
 *   speed 파라미터로 환산해 유지 (BUS_SPEED, 아래 매크로). 다만 실제 체감
 *   속도는 서보 가감속(ACC) 프로파일에 따라 달라지므로 실기에서 재검증 필요.
 *
 * 동작 차이 (PWM 버전 대비):
 *   이전 slew_servo()는 목표각까지 delay()로 블로킹 이동 — 명령 처리 중
 *   새 시리얼 명령을 못 받았음. 버스 서보는 WritePosEx가 논블로킹 — 목표
 *   위치만 서보에 지시하고 즉시 loop()로 복귀, 서보 자체 펌웨어가 speed/acc
 *   프로파일로 이동. 이동 중 새 명령이 오면 목표가 갱신됨 (더 반응적).
 *
 * 캘리브레이션:
 *   YAW_CENTER_TICK / PITCH_CENTER_TICK 은 "서보 자체 기계 중앙(2048)==논리
 *   90°" 가정. 실제 짐벌 조립 각도가 다르면 벤치 테스트 후 조정.
 */

#include <SCServo.h>

SMS_STS st;

#define BUS_SERVO_SERIAL   Serial1     // ⚠ UNO Q 실제 UART1 핀(TX1/RX1) 확인 후 배선
#define BUS_SERVO_BAUD     1000000     // ST3215 공장 기본 baud (변경 이력 없으면 유지)

#define YAW_ID              1          // 체인 첫 번째 서보 (어댑터 직결)
#define PITCH_ID            2          // yaw 에서 데이지체인된 두 번째 서보

#define YAW_MIN             0          // 중앙 ±90°, 실기 좌/우 90° 실측 확인(2026-07-17)
#define YAW_MAX             180
#define YAW_CENTER          90
#define PITCH_MIN           60         // 중앙 ±30°, 실기 위/아래 30° 실측 확인(2026-07-17,
#define PITCH_MAX           120        // 케이블 여유가 처음 추정한 ±20°보다 더 있었음)
#define PITCH_CENTER        90

// 서보 물리 장착 기준 틱 — 서보 EEPROM의 Homing_Offset(addr 31~32, STS3215은
// 부호비트가 bit11, ±2047 범위 — huggingface/lerobot의 feetech 구현으로 검증됨)을
// 실측 조정해서 "지금 이 물리 자세"가 PRESENT_POSITION에서 정확히 tick 2047(≈2048,
// 0~4095 정중앙)로 읽히도록 캘리브레이션 완료(2026-07-17,
// scripts/test_st3215_serial.py set-center, torque off 상태에서 실행해 물리적으로는
// 전혀 안 움직임). 정중앙이라 ±180° 여유가 양쪽에 다 확보되어 yaw ±90° / pitch ±20°
// 전부 0/4095 경계 없이 들어감.
// ⚠ 캘리브레이션 후 torque를 다시 켤 때는 반드시 먼저 Goal_Position을 현재
// Present_Position(2048)에 맞춰 동기화한 뒤 켤 것 — 안 그러면 서보가 예전 goal
// position으로 갑자기 회전할 수 있음(실기 사고 이력 있음, docs/issues/ 참고).
// 재조립 시 서보 EEPROM 쪽을 다시 맞추면 이 상수는 2048 그대로 둬도 됨.
#define YAW_CENTER_TICK      2048      // ID=1 (yaw)
#define PITCH_CENTER_TICK    2048      // ID=2 (pitch)
#define TICKS_PER_DEG        (4095.0f / 360.0f)   // ST3215: 12bit(0~4095) = 0~360°

#define STEP_DELAY_MS_EQUIV  20        // 기존 PWM 버전 기준 속도 (20ms/°) — 손가락 끼임 방지
#define BUS_SPEED   ((uint16_t)((1000.0f / STEP_DELAY_MS_EQUIV) * TICKS_PER_DEG))  // ≈569 tick/s
#define BUS_ACC     20                 // 가감속 (0~254, 클수록 급하게 붙음) — 실기 튜닝 필요

#define SERIAL_BAUD          115200    // USB(Python 브릿지) — 기존과 동일
#define LINE_BUF_SIZE        64

int current_yaw   = YAW_CENTER;
int current_pitch = PITCH_CENTER;

char line_buf[LINE_BUF_SIZE];
uint8_t line_len = 0;

int16_t deg_to_tick(int deg, int center_deg, int center_tick) {
    long tick = center_tick + lround((deg - center_deg) * TICKS_PER_DEG);
    if (tick < 0) tick = 0;
    if (tick > 4095) tick = 4095;
    return (int16_t)tick;
}

void move_yaw(int target_deg) {
    if (target_deg < YAW_MIN) target_deg = YAW_MIN;
    if (target_deg > YAW_MAX) target_deg = YAW_MAX;
    current_yaw = target_deg;
    st.WritePosEx(YAW_ID, deg_to_tick(current_yaw, YAW_CENTER, YAW_CENTER_TICK), BUS_SPEED, BUS_ACC);
}

void move_pitch(int target_deg) {
    if (target_deg < PITCH_MIN) target_deg = PITCH_MIN;
    if (target_deg > PITCH_MAX) target_deg = PITCH_MAX;
    current_pitch = target_deg;
    st.WritePosEx(PITCH_ID, deg_to_tick(current_pitch, PITCH_CENTER, PITCH_CENTER_TICK), BUS_SPEED, BUS_ACC);
}

void send_status(const char *prefix) {
    Serial.print(prefix);
    Serial.print(" PAN=");
    Serial.print(current_yaw);
    Serial.print(" TILT=");
    Serial.println(current_pitch);
}

// "PAN +8.5" / "TILT -5" 형태 파싱
bool parse_delta(const char *args, float *out_delta) {
    if (*args == '\0') return false;
    char *endp = nullptr;
    float v = strtod(args, &endp);
    if (endp == args) return false;
    *out_delta = v;
    return true;
}

void handle_line(char *buf) {
    // 토큰 분리 — 첫 공백까지가 cmd
    char *sp = strchr(buf, ' ');
    const char *args = "";
    if (sp != nullptr) {
        *sp = '\0';
        args = sp + 1;
    }

    if (strcmp(buf, "PING") == 0) {
        Serial.println("PONG");
        return;
    }

    if (strcmp(buf, "CENTER") == 0) {
        move_yaw(YAW_CENTER);
        move_pitch(PITCH_CENTER);
        send_status("OK");
        return;
    }

    if (strcmp(buf, "PAN") == 0) {
        float delta = 0.0;
        if (!parse_delta(args, &delta)) { Serial.println("ERR pan_delta"); return; }
        move_yaw(current_yaw + (int)delta);
        send_status("OK");
        return;
    }

    if (strcmp(buf, "TILT") == 0) {
        float delta = 0.0;
        if (!parse_delta(args, &delta)) { Serial.println("ERR tilt_delta"); return; }
        move_pitch(current_pitch + (int)delta);
        send_status("OK");
        return;
    }

    Serial.print("ERR unknown_cmd ");
    Serial.println(buf);
}

void setup() {
    Serial.begin(SERIAL_BAUD);
    BUS_SERVO_SERIAL.begin(BUS_SERVO_BAUD);
    st.pSerial = &BUS_SERVO_SERIAL;

    delay(500);

    // 부팅 시 두 서보 응답 확인 — 배선/ID 설정 누락을 조기에 발견하기 위함
    bool yaw_ok   = (st.Ping(YAW_ID)   != -1);
    bool pitch_ok = (st.Ping(PITCH_ID) != -1);
    if (!yaw_ok)   Serial.println("ERR yaw_servo_not_found (ID=1)");
    if (!pitch_ok) Serial.println("ERR pitch_servo_not_found (ID=2)");

    move_yaw(YAW_CENTER);
    move_pitch(PITCH_CENTER);
    delay(500);
    Serial.println("READY health_care_ptz (bus)");
    send_status("OK");
}

void loop() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r') continue;
        if (c == '\n') {
            line_buf[line_len] = '\0';
            if (line_len > 0) handle_line(line_buf);
            line_len = 0;
            continue;
        }
        if (line_len < LINE_BUF_SIZE - 1) {
            line_buf[line_len++] = c;
        } else {
            // overflow 방어 — 명령 길이 64자 한계
            line_len = 0;
            Serial.println("ERR line_overflow");
        }
    }
}
