import secrets
import hashlib
import csv
from datetime import datetime

PREFIX = "MSPGV3"  # 고정

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def make_code() -> str:
    # MSPGV3-XXXX-XXXX-XXXX (대문자/숫자)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    a, b, c = raw[:4], raw[4:8], raw[8:12]
    return f"{PREFIX}-{a}-{b}-{c}"

def main():
    print("\n=== Access Code Generator (MSPGV3-XXXX-XXXX-XXXX) ===")
    n = int(input("몇 개 생성할까요? (예: 5) : ").strip() or "5")
    label_base = input("라벨 베이스 (예: staff / md / cs / order_20260209) : ").strip() or "staff"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_name = f"access_codes_{ts}.csv"

    rows = []
    secrets_lines = []

    for i in range(1, n + 1):
        label = f"{label_base}{i:02d}"
        code = make_code()
        h = sha256(code)
        rows.append([label, code, h])
        secrets_lines.append(f'  "{label}:{h}",')

    with open(csv_name, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label", "access_code_plain", "sha256_hash"])
        w.writerows(rows)

    print("\n✅ CSV 저장:", csv_name)
    print("\n--- Streamlit Secrets에 붙여넣기 ---")
    print("ACCESS_CODE_HASHES = [")
    for line in secrets_lines:
        print(line)
    print("]")
    print("\nREVOKED_LABELS = []  # 차단할 label이 생기면 여기에 추가")

    print("\n[직원에게 줄 것]")
    print("- CSV의 access_code_plain(원문 코드)만 전달하세요.")

    print("\n[차단(삭제) 방법]")
    print('- Secrets에서 REVOKED_LABELS = ["staff02"] 처럼 label만 추가하면 즉시 차단됩니다.')

if __name__ == "__main__":
    main()
