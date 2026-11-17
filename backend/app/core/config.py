from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "B3 AI Stock Scanner"
    api_v1_prefix: str = ""
    database_url: str = "postgresql+psycopg://scanner:scanner@localhost:5432/scanner"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: str | None = None
    agent_model: str = "gpt-4.1-mini"
    seed_demo_data: bool = True
    use_real_market_data: bool = True
    scan_all_b3: bool = True
    b3_universe_limit: int = 0
    b3_min_volume: float = 1
    b3_recent_trading_days: int = 30
    b3_refresh_batch_size: int = 40
    include_smallcaps: bool = True
    b3_smallcap_tickers: str = (
        "ALPA4,ANIM3,AZUL4,BEEF3,BMOB3,BRAP4,CAML3,CEAB3,COGN3,CVCB3,"
        "CYRE3,DIRR3,ECOR3,EVEN3,EZTC3,GFSA3,GUAR3,HBSA3,LAVV3,LWSA3,"
        "MDIA3,MELK3,MILS3,MOVI3,MRVE3,ODPV3,PETZ3,PNVL3,POMO4,POSI3,"
        "QUAL3,RAPT4,SEER3,SIMH3,SLCE3,SMTO3,TEND3,TUPY3,VLID3,YDUQ3"
    )
    create_db_on_startup: bool = False
    auto_run_scanner: bool = False
    scanner_interval_seconds: int = 180
    scanner_initial_delay_seconds: int = 30
    scanner_refresh_universe: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
