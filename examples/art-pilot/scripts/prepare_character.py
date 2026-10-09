"""Create character directories for one pilot subject."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "characters"
CHARACTERS = {
    "stone-relic": "低饱和石片遗物，暖色刻痕；验证轮廓/键色/150px",
    "stick-runner": "火柴人奔跑；验证多姿态选项→选定单条再生",
    "energy-token": "圆形能量符石，冷色核心；验证同载体换色配对",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare art-pilot character folders")
    parser.add_argument("character", choices=sorted(CHARACTERS))
    args = parser.parse_args()
    root = ROOT / args.character
    for name in ("records", "records/transitions", "raw", "prepared", "candidates"):
        (root / name).mkdir(parents=True, exist_ok=True)
    intent = root / "intent.md"
    if not intent.exists():
        intent.write_text(
            f"# {args.character}\n\n{CHARACTERS[args.character]}\n\n"
            f"## 禁止\n\n- 数字/文字水印当构图\n- 依赖平台角标\n- 多主体抢读\n",
            encoding="utf-8",
        )
    print(f"ready: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
