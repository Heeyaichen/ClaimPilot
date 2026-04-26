"""Central configuration for ClaimPilot using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure AI Document Intelligence
    azure_doc_intelligence_endpoint: str = ""
    azure_doc_intelligence_model_id: str = "prebuilt-document"

    # Azure Speech
    azure_speech_endpoint: str = ""

    # Azure Content Understanding (REST)
    azure_content_understanding_endpoint: str = ""

    # Azure Translator
    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com/"
    azure_translator_region: str = "eastus2"

    # Azure AI Search / Foundry IQ
    azure_search_endpoint: str = ""

    # Azure Cosmos DB
    azure_cosmos_endpoint: str = ""

    # Azure Blob Storage
    azure_storage_endpoint: str = ""

    # Azure SignalR
    azure_signalr_connection: str = ""

    # Azure Service Bus
    azure_service_bus_namespace: str = ""
    azure_service_bus_queue: str = "claims-pipeline"

    # Azure Key Vault
    azure_key_vault_endpoint: str = ""

    # Azure AI Foundry (Phase 2+)
    azure_foundry_project_endpoint: str = ""
    foundry_model_deployment: str = "gpt-5-4"

    # Agent IDs (Phase 2+)
    classifier_agent_id: str = ""
    extractor_agent_id: str = ""
    fraud_agent_id: str = ""
    decision_agent_id: str = ""


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
