from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="POS_", extra="ignore")

    app_name: str = "Indian Retail POS"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://pos:pos@localhost:5432/pos"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 12
    algorithm: str = "HS256"
    default_country: str = "IN"

    # -- Payment gateway (Razorpay) -----------------------------------
    # Sandbox test-mode keys are safe to ship as defaults (they only work
    # against Razorpay's test environment, never move real money); swap
    # for live "rzp_live_..." keys in production via env vars. Get real
    # keys from https://dashboard.razorpay.com/app/keys.
    razorpay_key_id: str = "rzp_test_0000000000000"
    razorpay_key_secret: str = "test_secret_change_me"
    razorpay_webhook_secret: str = "test_webhook_secret_change_me"
    # Feature flag: shows/hides the "Pay via UPI QR" option in the POS
    # billing screen. Safe to leave on with test-mode keys (nothing real
    # can be charged); turn off if you want the QR flow hidden entirely
    # without touching code, e.g. mid-incident or before keys are ready.
    razorpay_upi_enabled: bool = True
    # How long a generated QR stays payable before the till gives up and
    # reports it "expired" (matches the window RazorpayAdapter requests
    # from Razorpay itself -- see close_by in adapters.py).
    razorpay_qr_expiry_minutes: int = 15

    # -- SMS (MSG91) ---------------------------------------------------
    # Leave msg91_auth_key blank to keep notifications on the logging
    # adapter (safe default for dev/CI -- see notifications/adapters.py).
    # Get a real key from https://control.msg91.com/app/dashboard.
    msg91_auth_key: str = ""
    msg91_sender_id: str = "POSAPP"
    msg91_flow_id: str = ""

    # -- Thermal receipt printer (Epson ESC/POS over network) ---------
    # Epson TM-series and most ESC/POS-compatible printers listen on raw
    # TCP port 9100. Point this at the real printer's LAN IP; leave the
    # default and printing will fail closed (logged, never blocks a sale).
    printer_host: str = "192.168.1.100"
    printer_port: int = 9100
    printer_enabled: bool = False

    # -- GST Suvidha Provider (e-filing) -------------------------------
    # "mock" returns deterministic fake acknowledgements so the filing
    # workflow is fully exercisable end-to-end without a real GSP
    # contract; switch to "http" once you have one (ClearTax, Cygnet,
    # MasterGST, or GSTN's own API) and set gsp_base_url/gsp_api_key.
    gsp_provider: str = "mock"
    gsp_base_url: str = "https://sandbox.example-gsp.invalid"
    gsp_api_key: str = "mock-gsp-api-key"

    # -- Offline-first sync (server side) ------------------------------
    # Max change-log rows / offline sales returned or accepted per
    # push/pull call -- keeps a single request bounded regardless of how
    # large a terminal's backlog has grown after an extended outage.
    sync_pull_page_size: int = 500
    sync_push_max_batch_size: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
