import json
import secrets
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.scanner.generator import generate_qr


OUTPUT_DIR = PROJECT_ROOT / "user_savings" / "接口"
COMPANIES = ("顺丰速运", "京东物流", "中通快递", "圆通速递", "申通快递")


def make_tracking_no(location: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"QR{timestamp}{secrets.randbelow(10000):04d}{location}"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parcels = []

    for location in ("A", "B"):
        parcel = {
            "tracking_no": make_tracking_no(location),
            "company": secrets.choice(COMPANIES),
            "receiver_name": "我不想上学",
            "receiver_phone": "13800000000",
            "target_location": location,
        }
        output_path = OUTPUT_DIR / f"parcel_{parcel['tracking_no']}_{location}.png"
        if not generate_qr(parcel, str(output_path)):
            raise RuntimeError(f"二维码生成失败: {output_path}")
        parcels.append({**parcel, "file": output_path.name})

    manifest_path = OUTPUT_DIR / "generated_parcels.json"
    manifest_path.write_text(
        json.dumps(parcels, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for parcel in parcels:
        print(f"{parcel['target_location']}: {parcel['file']}")
    print(f"Manifest: {manifest_path.name}")


if __name__ == "__main__":
    main()
