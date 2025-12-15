import csv
from pathlib import Path


CSV_PATH = Path("./downloads/shopee_affiliate_links.csv")


def parse_percent(percent_str: str) -> float:
    """
    Chuyển '3,3%' -> 3.3
    """
    if not percent_str:
        return 0.0
    return float(
        percent_str
        .replace("%", "")
        .replace(",", ".")
        .strip()
    )


def read_and_sort_affiliate_links(csv_path: Path):
    items = []

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            commission_rate = parse_percent(row.get("Tỉ lệ hoa hồng"))

            items.append({
                "title": row.get("Tên sản phẩm", "").strip(),
                "link": row.get("Link ưu đãi", "").strip(),
                "commission_rate": commission_rate
            })

    # Sort giảm dần theo % hoa hồng
    items.sort(key=lambda x: x["commission_rate"], reverse=True)

    # Trả về đúng format yêu cầu
    result = [
        {
            "title": item["title"],
            "link": item["link"]
        }
        for item in items
    ]

    return result


if __name__ == "__main__":
    result = read_and_sort_affiliate_links(CSV_PATH)

    # In ra kiểm tra
    for i, item in enumerate(result, 1):
        print(f"{i}. {item['title']}")
        print(f"   {item['link']}")
