"""
VNINDEX AI Analyst - Main Entry Point
Scheduler tự động chạy pipeline phân tích hàng ngày.
"""

import sys
import time
import logging
from datetime import datetime

import schedule

from database.models import init_db
from agents.macro_agent import MacroAgent
from agents.news_agent import NewsAgent
from agents.technical_agent import TechnicalAgent
from agents.risk_manager import RiskManager
from brain.cio_engine import CIOEngine
from reports.pdf_generator import PDFReportGenerator
import config

# ─── Logging Setup ─────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.DATA_DIR / "vnindex.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("VNINDEX")

# ─── Global state cho pipeline ─────────────────────────────────────────────────
pipeline_state = {
    "macro_result": None,
    "news_result": None,
    "tech_result": None,
    "risk_result": None,
    "cio_result": None,
    "last_report": None,
}


def run_macro():
    """08:00 - Chạy Macro Agent."""
    logger.info("=" * 60)
    logger.info("STEP 1/5: MACRO ANALYSIS")
    try:
        agent = MacroAgent()
        pipeline_state["macro_result"] = agent.run()
        logger.info("✅ Macro Agent completed.")
    except Exception as e:
        logger.error(f"❌ Macro Agent failed: {e}", exc_info=True)
        pipeline_state["macro_result"] = {"status": "ERROR", "alerts": []}


def run_news():
    """08:10 - Chạy News Agent."""
    logger.info("=" * 60)
    logger.info("STEP 2/5: NEWS ANALYSIS")
    try:
        agent = NewsAgent()
        pipeline_state["news_result"] = agent.run()
        logger.info("✅ News Agent completed.")
    except Exception as e:
        logger.error(f"❌ News Agent failed: {e}", exc_info=True)
        pipeline_state["news_result"] = {"market_sentiment": 0, "symbol_sentiments": {}}


def run_technical():
    """08:20 - Chạy Technical Agent."""
    logger.info("=" * 60)
    logger.info("STEP 3/5: TECHNICAL ANALYSIS")
    try:
        agent = TechnicalAgent()
        pipeline_state["tech_result"] = agent.run()
        logger.info("✅ Technical Agent completed.")
    except Exception as e:
        logger.error(f"❌ Technical Agent failed: {e}", exc_info=True)
        pipeline_state["tech_result"] = {"indicators": {}, "market_breadth": {}}


def run_cio():
    """08:30 - Chạy CEO Agent (Gemma 4)."""
    logger.info("=" * 60)
    logger.info("STEP 4/5: CEO DECISION ENGINE")
    try:
        # Chạy Risk Manager trước
        risk_mgr = RiskManager()
        pipeline_state["risk_result"] = risk_mgr.run(
            macro_result=pipeline_state.get("macro_result", {}),
            tech_result=pipeline_state.get("tech_result", {}),
        )

        # Chạy CEO
        cio = CIOEngine()
        pipeline_state["cio_result"] = cio.analyze(
            macro_data=pipeline_state.get("macro_result", {}),
            tech_data=pipeline_state.get("tech_result", {}),
            news_data=pipeline_state.get("news_result", {}),
            risk_data=pipeline_state.get("risk_result", {}),
        )
        logger.info("✅ CEO Agent completed.")
    except Exception as e:
        logger.error(f"❌ CEO Agent failed: {e}", exc_info=True)
        pipeline_state["cio_result"] = {"decisions": [], "risk_level": "N/A"}


def run_report():
    """08:45 - Tạo PDF Report."""
    logger.info("=" * 60)
    logger.info("STEP 5/5: PDF REPORT GENERATION")
    try:
        generator = PDFReportGenerator()
        filepath = generator.generate(
            macro_data=pipeline_state.get("macro_result", {}),
            tech_data=pipeline_state.get("tech_result", {}),
            news_data=pipeline_state.get("news_result", {}),
            risk_data=pipeline_state.get("risk_result", {}),
            cio_decisions=pipeline_state.get("cio_result", {}),
        )
        pipeline_state["last_report"] = filepath
        logger.info(f"✅ Report generated: {filepath}")
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info("🏁 Daily pipeline completed!")
    logger.info("=" * 60)


def run_full_pipeline():
    """Chạy toàn bộ pipeline ngay lập tức (cho testing)."""
    logger.info("🚀 Running FULL pipeline immediately...")
    run_macro()
    run_news()
    run_technical()
    run_cio()
    run_report()
    return pipeline_state


def setup_scheduler():
    """Thiết lập lịch chạy hàng ngày."""
    schedule.every().day.at(config.SCHEDULE_MACRO).do(run_macro)
    schedule.every().day.at(config.SCHEDULE_NEWS).do(run_news)
    schedule.every().day.at(config.SCHEDULE_TECHNICAL).do(run_technical)
    schedule.every().day.at(config.SCHEDULE_CIO).do(run_cio)
    schedule.every().day.at(config.SCHEDULE_REPORT).do(run_report)

    logger.info("📅 Scheduler configured:")
    logger.info(f"  {config.SCHEDULE_MACRO} - Macro Agent")
    logger.info(f"  {config.SCHEDULE_NEWS} - News Agent")
    logger.info(f"  {config.SCHEDULE_TECHNICAL} - Technical Agent")
    logger.info(f"  {config.SCHEDULE_CIO} - CIO Engine")
    logger.info(f"  {config.SCHEDULE_REPORT} - PDF Report")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════╗
    ║       VNINDEX AI ANALYST v1.0                ║
    ║       Powered by Gemma + Multi-Agent         ║
    ╚══════════════════════════════════════════════╝
    """)

    # Khởi tạo database
    init_db()

    if "--now" in sys.argv:
        # Chạy ngay lập tức
        run_full_pipeline()
    else:
        # Chạy theo lịch
        setup_scheduler()
        logger.info("⏰ Scheduler started. Waiting for scheduled tasks...")
        while True:
            schedule.run_pending()
            time.sleep(30)
