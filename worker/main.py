import time

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.scanner import run_scanner


def main() -> None:
    settings = get_settings()
    while True:
        with SessionLocal() as db:
            processed, generated = run_scanner(
                db,
                seed_demo_data=settings.seed_demo_data,
                use_real_market_data=settings.use_real_market_data,
                scan_all_b3=settings.scan_all_b3,
                b3_universe_limit=settings.b3_universe_limit,
                b3_min_volume=settings.b3_min_volume,
                b3_recent_trading_days=max(30, settings.b3_recent_trading_days),
                include_smallcaps=settings.include_smallcaps,
                b3_smallcap_tickers=settings.b3_smallcap_tickers,
            )
            print(f"scanner_run processed={processed} generated={generated}", flush=True)
        time.sleep(60 * 60 * 24)


if __name__ == "__main__":
    main()
