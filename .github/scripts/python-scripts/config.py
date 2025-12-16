from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    GOOGLE_CLOUD_PROJECT: str = Field("alloflo-staging", description="Google Cloud Project ID.")
    GOOGLE_CLOUD_REGION: str = Field(
        "northamerica-northeast1",
        description="Region for the Google Cloud Project in which resources & data are located in.",
    )

    CONTENT_API_URL: str = Field("http://localhost:8081")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


app = ApplicationSettings()
