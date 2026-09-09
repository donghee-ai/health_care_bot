# models/

추론 모델 자산. **`movenet_thunder_int8.tflite`는 git에 포함되어 있다** — clone하면
바로 쓸 수 있다. 출처·라이선스 표기는 [`../THIRD_PARTY.md`](../THIRD_PARTY.md) §2.

자매 리포에서 모델을 갱신할 때만 아래를 쓴다:

```bash
bash scripts/copy_model.sh
# → models/movenet_thunder_int8.tflite (6.8 MB)
```

## 모델

| 파일 | 용도 | 입력 | 출력 |
|---|---|---|---|
| `movenet_thunder_int8.tflite` | Pose 17 keypoint | uint8 [1,256,256,3] | float32 [1,1,17,3] (y_norm, x_norm, conf) |

원본 자산: `../../unoq-companion-robot/pose/models/movenet_thunder_int8.tflite`.
