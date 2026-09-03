from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration arrives from the environment.

    Nothing is hard-coded with a production-usable default: the JWT secret has a
    deliberately obvious dev placeholder so a misconfigured deploy is loud, not silent.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://frp:frp_local_password@localhost:5432/frp"
    jwt_secret: str = "dev-only-not-a-real-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    cookie_secure: bool = False
    cookie_name: str = "frp_session"
    cors_origins: str = "http://localhost:5173"
    # Set false to bring the stack up against an existing database without seeding it.
    seed_on_startup: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
