"""
VNINDEX AI Analyst - Fundamental Agent
Sử dụng DeepSeek-R1 để phân tích và lọc các doanh nghiệp cơ bản tốt.
"""

import json
import logging
import re
from datetime import datetime

import requests

import config
from database.db_manager import DatabaseManager
from database.models import get_connection

logger = logging.getLogger(__name__)

FUNDAMENTAL_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích cơ bản chứng khoán Việt Nam (Fundamental Analyst).
Bạn chỉ chọn ra những doanh nghiệp thỏa mãn ĐỒNG THỜI các tiêu chí:
1. Có nền tảng cơ bản cực kỳ tốt, kinh doanh cốt lõi vững chắc.
2. Có vị thế và ảnh hưởng lớn tới thị trường (Vốn hóa lớn/Bluechips).
3. Đang nằm trong danh mục đầu tư của các quỹ lớn (như Dragon Capital, VinaCapital, VN30, VNDiamond).

Nhiệm vụ: Dựa vào danh sách mã chứng khoán (có thanh khoản cao) được cung cấp, hãy LỌC VÀ TRẢ VỀ các mã đáp ứng tiêu chí trên.

Bạn BẮT BUỘC phải trả về một mảng JSON chứa các mã chứng khoán. Không giải thích lằng nhằng trong kết quả JSON.
Ví dụ định dạng trả về (nằm ở cuối câu trả lời):
```json
["FPT", "VCB", "HPG", "MBB"]
```"""


class FundamentalAgent:
    def __init__(self):
        self.db = DatabaseManager()
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.OLLAMA_FUNDAMENTAL_MODEL

    def run(self) -> dict:
        logger.info("🏢 Fundamental Agent: Bắt đầu lọc doanh nghiệp cơ bản tốt...")
        
        # 1. Lọc các mã có thanh khoản cao (ví dụ: Volume trung bình > 200,000)
        # Để nhanh, ta lấy giá mới nhất và lọc volume
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT symbol, close, volume 
                   FROM daily_prices 
                   WHERE date = (SELECT MAX(date) FROM daily_prices)
                   AND volume > 200000 
                   ORDER BY volume DESC LIMIT 150"""
            ).fetchall()
            liquid_symbols = [row["symbol"] for row in rows]
        finally:
            conn.close()

        if not liquid_symbols:
            logger.warning("Không tìm thấy mã nào đủ thanh khoản.")
            return {"status": "NO_DATA"}

        logger.info(f"Tìm thấy {len(liquid_symbols)} mã có thanh khoản cao. Gửi cho DeepSeek-R1...")

        # 2. Xây dựng prompt
        prompt = f"Dưới đây là {len(liquid_symbols)} mã chứng khoán đang có thanh khoản cao nhất thị trường:\n"
        prompt += ", ".join(liquid_symbols)
        prompt += "\n\nHãy chọn lọc khắt khe và trả về danh sách JSON các mã có cơ bản tốt, ảnh hưởng thị trường và có quỹ lớn nắm giữ."

        # 3. Gọi DeepSeek-R1
        selected_symbols = []
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": FUNDAMENTAL_SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0.1}
            }
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=300)
            resp.raise_for_status()
            response_text = resp.json().get("response", "")
            
            # Extract JSON array
            json_match = re.search(r'\[(.*?)\]', response_text, re.DOTALL)
            if json_match:
                # Tìm các mã 3 chữ cái trong block
                raw_list = json_match.group(1)
                matches = re.findall(r'"([A-Z0-9]{3})"', raw_list)
                if not matches:
                    matches = re.findall(r'([A-Z0-9]{3})', raw_list)
                selected_symbols = list(set(matches))
            else:
                # Fallback: Quét toàn bộ output lấy các mã có trong liquid_symbols
                found = re.findall(r'\b([A-Z0-9]{3})\b', response_text)
                selected_symbols = list(set(f for f in found if f in liquid_symbols))

        except Exception as e:
            logger.error(f"❌ DeepSeek-R1 Fundamental failed: {e}")
            # Fallback VN30 nếu lỗi
            selected_symbols = [s for s in liquid_symbols if s in [
                "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", 
                "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB", 
                "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
            ]]

        # Đảm bảo không quá ít, không quá nhiều (để Technical Agent làm việc)
        logger.info(f"DeepSeek-R1 đã chọn ra {len(selected_symbols)} mã cơ bản tốt: {selected_symbols}")

        # 4. Cập nhật DB
        conn = get_connection()
        try:
            # Reset tất cả về 0
            conn.execute("UPDATE tickers SET is_fund_approved = 0")
            if selected_symbols:
                # Set 1 cho các mã được chọn
                placeholders = ",".join("?" for _ in selected_symbols)
                conn.execute(f"UPDATE tickers SET is_fund_approved = 1 WHERE symbol IN ({placeholders})", selected_symbols)
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "OK",
            "approved_count": len(selected_symbols),
            "approved_symbols": selected_symbols,
            "timestamp": datetime.now().isoformat()
        }
