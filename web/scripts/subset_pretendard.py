"""Pretendard Variable를 unicode-range 조각으로 쪼갠다.

원본은 2.0MB다. 한글 음절 11,172자를 전부 담고 있어서인데, 한 화면에
실제로 뜨는 글자는 수백 자뿐이다. 시연 목표가 "QR 스캔 후 3초 안에
접속"이라, 첫 로딩에 2MB를 통째로 받는 건 그 목표와 정면으로 부딪힌다.

두 가지 방법이 있었다:

1. 소스에 등장하는 글자만 남기기 — 가장 작지만, 나중에 한국어 문구를
   한 글자라도 바꾸면 두부(□)가 뜬다. 서버가 보내주는 문자열까지
   생각하면 더 위험하다.
2. unicode-range로 조각내기 — 브라우저가 "실제로 그리는 글자가 든
   조각"만 받아간다. 모든 글자가 어딘가에는 있으므로 두부가 원천적으로
   불가능하고, 문구를 바꿔도 안전하다.

2번을 택했다. 조각을 여러 개 만들지만 전부 정적 파일이라 서버
부담은 없고, 한국어 웹폰트에서는 표준적으로 쓰는 방식이다.

실행:  python scripts/subset_pretendard.py
결과:  public/fonts/pretendard/*.woff2 + src/pretendard.css
"""
import sys
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fonts-src" / "pretendard-var.woff2"
OUT_DIR = ROOT / "public" / "fonts" / "pretendard"
CSS_OUT = ROOT / "src" / "pretendard.css"

HANGUL_START, HANGUL_END = 0xAC00, 0xD7A3
CHUNK = 256  # 조각 하나당 음절 수

# 항상 받는 조각: 라틴·숫자·구두점·기호·한글 자모.
# UI 골격이 이 범위에 있어서 조각내 봐야 어차피 전부 받는다.
BASE_RANGES = [
    (0x0020, 0x007E), (0x00A0, 0x00FF), (0x0100, 0x017F),
    (0x2000, 0x206F), (0x20A0, 0x20BF), (0x2100, 0x214F),
    (0x2190, 0x21FF), (0x2200, 0x22FF), (0x2460, 0x24FF),
    (0x25A0, 0x25FF), (0x2600, 0x26FF), (0x2700, 0x27BF),
    (0x3000, 0x303F), (0x1100, 0x11FF), (0x3130, 0x318F),
    (0xFF00, 0xFFEF),
]


def fmt_range(lo: int, hi: int) -> str:
    return f"U+{lo:04X}-{hi:04X}" if lo != hi else f"U+{lo:04X}"


def used_hangul() -> set[int]:
    """src/ 안 문구에 실제로 등장하는 한글 음절.

    코드포인트 순서로만 쪼개면, 화면 하나에 쓰이는 글자가 44개 조각에
    골고루 흩어져서 결국 대부분을 받게 된다(실측: 텍스트가 많은 시안이
    37조각 요청). 실제로 쓰는 글자를 한 조각에 모아 맨 앞에 두면
    보통 그 조각 하나로 끝난다. 나머지 조각은 문구를 바꿨을 때를 위한
    안전망으로 남는다.
    """
    out: set[int] = set()
    for path in (ROOT / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css", ".html"}:
            continue
        for ch in path.read_text(encoding="utf-8"):
            if HANGUL_START <= ord(ch) <= HANGUL_END:
                out.add(ord(ch))
    return out


def pack_ranges(cps: list[int]) -> str:
    """연속한 코드포인트를 구간으로 접어 unicode-range 문자열을 짧게."""
    if not cps:
        return ""
    cps = sorted(cps)
    parts, lo, prev = [], cps[0], cps[0]
    for c in cps[1:]:
        if c == prev + 1:
            prev = c
            continue
        parts.append(fmt_range(lo, prev))
        lo = prev = c
    parts.append(fmt_range(lo, prev))
    return ", ".join(parts)


def subset_to(font_path: Path, codepoints: list[int], out: Path) -> int:
    font = TTFont(font_path, fontNumber=0)
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    # 가변 축(wght 100~900)은 반드시 남긴다 — 시안들이 실제로 축을 움직인다.
    opts.recalc_bounds = False

    sub = Subsetter(options=opts)
    sub.populate(unicodes=codepoints)
    sub.subset(font)
    font.flavor = "woff2"
    font.save(out)
    return out.stat().st_size


def main() -> int:
    if not SRC.exists():
        print(f"원본 없음: {SRC}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.woff2"):
        old.unlink()

    faces: list[tuple[str, str, int]] = []  # (파일명, unicode-range, 크기)

    # ---- 조각 0: 라틴 + 기호 ----
    base_cps = [c for lo, hi in BASE_RANGES for c in range(lo, hi + 1)]
    size = subset_to(SRC, base_cps, OUT_DIR / "base.woff2")
    faces.append(("base.woff2", ", ".join(fmt_range(lo, hi) for lo, hi in BASE_RANGES), size))

    # ---- 조각 1: 실제로 쓰는 글자 (우선 조각) ----
    # 이 조각을 나머지보다 먼저 선언한다. 화면에 뜨는 한글은 거의 전부
    # 여기서 해결되고, 아래 안전망 조각들은 받아가지 않는다.
    used = used_hangul()
    if used:
        size = subset_to(SRC, sorted(used), OUT_DIR / "kr-core.woff2")
        faces.append(("kr-core.woff2", pack_ranges(sorted(used)), size))

    # ---- 조각 2..N: 나머지 음절 (안전망) ----
    # 우선 조각에 든 글자는 빼둔다. 같은 코드포인트를 두 face가 함께
    # 주장하면 어느 쪽이 이길지 브라우저 구현에 맡기게 되는데,
    # 그 모호함을 남길 이유가 없다.
    idx = 0
    for start in range(HANGUL_START, HANGUL_END + 1, CHUNK):
        end = min(start + CHUNK - 1, HANGUL_END)
        rest = [c for c in range(start, end + 1) if c not in used]
        if not rest:
            continue
        name = f"kr-{idx:02d}.woff2"
        size = subset_to(SRC, rest, OUT_DIR / name)
        faces.append((name, pack_ranges(rest), size))
        idx += 1

    # ---- CSS 생성 ----
    lines = [
        "/* 이 파일은 scripts/subset_pretendard.py가 생성한다 — 직접 고치지 말 것.",
        "   Pretendard 2.0MB를 unicode-range로 쪼갠 결과.",
        "   브라우저는 화면에 실제로 그리는 글자가 든 조각만 내려받는다. */",
        "",
    ]
    for name, urange, _ in faces:
        lines += [
            "@font-face {",
            "  font-family: 'Pretendard';",
            f"  src: url('/app/fonts/pretendard/{name}') format('woff2-variations');",
            "  font-weight: 45 920;",
            "  font-display: swap;",
            f"  unicode-range: {urange};",
            "}",
            "",
        ]
    CSS_OUT.write_text("\n".join(lines), encoding="utf-8")

    total = sum(s for _, _, s in faces)
    before = SRC.stat().st_size
    print(f"조각 수      : {len(faces)}")
    print(f"원본         : {before/1024:,.0f} KB")
    print(f"조각 합계    : {total/1024:,.0f} KB (전부 받았을 때)")
    print(f"기본 조각    : {faces[0][2]/1024:,.0f} KB (항상 받음)")
    print(f"한글 조각 평균: {sum(s for _, _, s in faces[1:])/max(1, len(faces)-1)/1024:,.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
