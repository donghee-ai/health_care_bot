# models/

추론 모델 자산. 본 폴더는 git에 모델 바이너리를 포함하지 않음 (용량/라이센스).
실행 전 `scripts/copy_model.sh`로 복사:

```bash
bash scripts/copy_model.sh
# → models/movenet_thunder_int8.tflite (6.8 MB)
```

## 모델

| 파일 | 용도 | 입력 | 출력 |
|---|---|---|---|
| `movenet_thunder_int8.tflite` | Pose 17 keypoint | uint8 [1,256,256,3] | float32 [1,1,17,3] (y_norm, x_norm, conf) |

원본 자산: `../../unoq-companion-robot/pose/models/movenet_thunder_int8.tflite`.
