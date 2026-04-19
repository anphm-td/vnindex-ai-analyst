# Seed data: Danh sách mã cổ phiếu phổ biến trên HOSE
HOSE_TICKERS = [
    ("VNM", "CTCP Sữa Việt Nam", "Thực phẩm", "HOSE"),
    ("HPG", "CTCP Tập đoàn Hòa Phát", "Thép", "HOSE"),
    ("FPT", "CTCP FPT", "Công nghệ", "HOSE"),
    ("VCB", "NH TMCP Ngoại thương Việt Nam", "Ngân hàng", "HOSE"),
    ("BID", "NH TMCP Đầu tư và Phát triển Việt Nam", "Ngân hàng", "HOSE"),
    ("VHM", "CTCP Vinhomes", "Bất động sản", "HOSE"),
    ("VIC", "Tập đoàn Vingroup", "Bất động sản", "HOSE"),
    ("MSN", "CTCP Tập đoàn Masan", "Thực phẩm", "HOSE"),
    ("MWG", "CTCP Đầu tư Thế Giới Di Động", "Bán lẻ", "HOSE"),
    ("SSI", "CTCP Chứng khoán SSI", "Chứng khoán", "HOSE"),
    ("VND", "CTCP Chứng khoán VNDirect", "Chứng khoán", "HOSE"),
    ("TCB", "NH TMCP Kỹ Thương Việt Nam", "Ngân hàng", "HOSE"),
    ("MBB", "NH TMCP Quân Đội", "Ngân hàng", "HOSE"),
    ("ACB", "NH TMCP Á Châu", "Ngân hàng", "HOSE"),
    ("CTG", "NH TMCP Công Thương Việt Nam", "Ngân hàng", "HOSE"),
    ("STB", "NH TMCP Sài Gòn Thương Tín", "Ngân hàng", "HOSE"),
    ("GAS", "Tổng Công ty Khí Việt Nam", "Dầu khí", "HOSE"),
    ("PLX", "Tập đoàn Xăng Dầu Việt Nam", "Dầu khí", "HOSE"),
    ("SAB", "Tổng Công ty CP Bia - Rượu - NGK Sài Gòn", "Đồ uống", "HOSE"),
    ("VRE", "CTCP Vincom Retail", "Bất động sản", "HOSE"),
    ("NVL", "CTCP Tập đoàn Đầu tư Địa ốc No Va", "Bất động sản", "HOSE"),
    ("DIG", "CTCP Đầu tư Phát triển Xây dựng", "Bất động sản", "HOSE"),
    ("KDH", "CTCP Đầu tư Kinh Doanh Nhà Khang Điền", "Bất động sản", "HOSE"),
    ("PDR", "CTCP Phát Đạt", "Bất động sản", "HOSE"),
    ("POW", "Tổng Công ty Điện lực Dầu khí Việt Nam", "Điện", "HOSE"),
    ("REE", "CTCP Cơ Điện Lạnh", "Công nghiệp", "HOSE"),
    ("PNJ", "CTCP Vàng Bạc Đá Quý Phú Nhuận", "Bán lẻ", "HOSE"),
    ("DGC", "CTCP Tập đoàn Hóa chất Đức Giang", "Hóa chất", "HOSE"),
    ("GMD", "CTCP Gemadept", "Vận tải", "HOSE"),
    ("VNINDEX", "Chỉ số VN-Index", "Chỉ số", "HOSE"),
]


def seed_tickers():
    """Thêm danh sách mã cổ phiếu mẫu vào database."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from database.models import init_db
    from database.db_manager import DatabaseManager

    init_db()
    db = DatabaseManager()

    for symbol, name, industry, exchange in HOSE_TICKERS:
        db.upsert_ticker(symbol, name, industry, exchange)
        print(f"  ✅ {symbol}: {name}")

    print(f"\n🎉 Seeded {len(HOSE_TICKERS)} tickers!")


if __name__ == "__main__":
    seed_tickers()
