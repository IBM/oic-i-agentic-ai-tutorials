"""Centralized configuration for BeeAI Service"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_prefix="BEEAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server Configuration
    wxo_port: int = Field(default=8080, description="WXO HTTP server port")
    wxo_host: str = Field(default="0.0.0.0", description="WXO HTTP server host")
    api_key: str = Field(default="beeai-maintenance-key-2024", description="API key for WXO")
    
    # LLM Configuration
    llm_model: str = Field(default="watsonx:ibm/granite-3-8b-instruct", description="LLM model")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_intermediate_steps: bool = Field(default=False, description="Log agent steps")


class WatsonxSettings(BaseSettings):
    """IBM watsonx.ai-specific settings"""
    
    model_config = SettingsConfigDict(
        env_prefix="WATSONX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    api_key: str = Field(
        default="",
        description="IBM watsonx.ai API key"
    )
    url: str = Field(
        default="https://us-south.ml.cloud.ibm.com",
        description="IBM watsonx.ai URL"
    )
    project_id: str = Field(
        default="",
        description="IBM watsonx.ai Project ID"
    )
    model_id: str = Field(
        default="ibm/granite-3-8b-instruct",
        description="Model ID to use"
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum tokens for response"
    )
    temperature: float = Field(
        default=0.7,
        description="Model temperature"
    )


# Singleton instances
app_settings = Settings()
watsonx_settings = WatsonxSettings()