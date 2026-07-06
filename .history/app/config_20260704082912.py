from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # AI gateway (OpenAI-compatible)
    AI_BASE_URL: str = "https://api.deepseek.com/v1"
    AI_API_KEY: str = ""
    AI_MODEL: str = "deepseek-chat"
    AI_ENABLED: bool = True

    DATABASE_URL: str = "sqlite:///./scholarpulse.db"
    SEMANTIC_SCHOLAR_KEY: str = ""
    GITHUB_TOKEN: str = ""   # optional; raises GitHub API rate limit 10→30 req/min

    # optional push channels (read by app/services/push.py)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SLACK_WEBHOOK_URL: str = ""
    WECHAT_WEBHOOK: str = ""    # WeChat via 企业微信群机器人 (recommended)
    SERVERCHAN_KEY: str = ""    # WeChat via Server酱 (personal WeChat)

    # email (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    EMAIL_FROM: str = ""
    EMAIL_TO: str = ""

    # scheduling
    REFRESH_TIMES: str = "10:00,22:00"
    TIMEZONE: str = "Asia/Shanghai"
    BACKFILL_N: int = 5

    RSS_FEEDS: str = "http://export.arxiv.org/rss/cs.PL,https://connect.biorxiv.org/biorxiv_xml.php?subject=all,https://chemrxiv.org/engage/rss/chemrxiv"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def refresh_times_list(self):
        return [t.strip() for t in self.REFRESH_TIMES.split(",") if t.strip()]

    @property
    def rss_list(self):
        return [t.strip() for t in self.RSS_FEEDS.split(",") if t.strip()]


settings = Settings()
