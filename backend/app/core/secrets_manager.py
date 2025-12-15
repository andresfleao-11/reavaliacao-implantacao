"""
Abstração para gerenciamento de secrets
Suporta variáveis de ambiente, AWS Secrets Manager, Azure Key Vault, e GCP Secret Manager
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretsProvider(ABC):
    """Interface abstrata para provedores de secrets"""

    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Obtém um secret pelo nome"""
        pass

    @abstractmethod
    def get_secret_dict(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Obtém um secret em formato de dicionário"""
        pass


class EnvironmentSecretsProvider(SecretsProvider):
    """Provedor que lê secrets de variáveis de ambiente"""

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Obtém secret de variável de ambiente"""
        return os.getenv(secret_name)

    def get_secret_dict(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Obtém secret em formato JSON de variável de ambiente"""
        value = self.get_secret(secret_name)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse secret {secret_name} as JSON")
                return None
        return None


class AWSSecretsManagerProvider(SecretsProvider):
    """Provedor para AWS Secrets Manager"""

    def __init__(self, region_name: str = "us-east-1"):
        try:
            import boto3
            from botocore.exceptions import ClientError
            self.client = boto3.client('secretsmanager', region_name=region_name)
            self.ClientError = ClientError
            logger.info(f"AWS Secrets Manager initialized for region {region_name}")
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Obtém secret do AWS Secrets Manager"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response.get('SecretString')
        except self.ClientError as e:
            logger.error(f"Error getting secret {secret_name} from AWS: {e}")
            return None

    def get_secret_dict(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Obtém secret em formato JSON do AWS Secrets Manager"""
        value = self.get_secret(secret_name)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AWS secret {secret_name} as JSON")
                return None
        return None


class AzureKeyVaultProvider(SecretsProvider):
    """Provedor para Azure Key Vault"""

    def __init__(self, vault_url: str):
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=vault_url, credential=credential)
            logger.info(f"Azure Key Vault initialized for {vault_url}")
        except ImportError:
            logger.error("azure-keyvault-secrets not installed. Install with: pip install azure-keyvault-secrets azure-identity")
            raise

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Obtém secret do Azure Key Vault"""
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.error(f"Error getting secret {secret_name} from Azure: {e}")
            return None

    def get_secret_dict(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """Obtém secret em formato JSON do Azure Key Vault"""
        value = self.get_secret(secret_name)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Azure secret {secret_name} as JSON")
                return None
        return None


class GCPSecretManagerProvider(SecretsProvider):
    """Provedor para GCP Secret Manager"""

    def __init__(self, project_id: str):
        try:
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
            self.project_id = project_id
            logger.info(f"GCP Secret Manager initialized for project {project_id}")
        except ImportError:
            logger.error("google-cloud-secret-manager not installed. Install with: pip install google-cloud-secret-manager")
            raise

    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """Obtém secret do GCP Secret Manager"""
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"Error getting secret {secret_name} from GCP: {e}")
            return None

    def get_secret_dict(self, secret_name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Obtém secret em formato JSON do GCP Secret Manager"""
        value = self.get_secret(secret_name, version)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse GCP secret {secret_name} as JSON")
                return None
        return None


class SecretsManager:
    """
    Gerenciador de secrets com suporte a múltiplos provedores

    Exemplo de uso:

    # Usando variáveis de ambiente (padrão)
    secrets = SecretsManager()
    api_key = secrets.get_secret("ANTHROPIC_API_KEY")

    # Usando AWS Secrets Manager
    secrets = SecretsManager(provider="aws", region_name="us-east-1")
    api_key = secrets.get_secret("prod/anthropic_api_key")

    # Usando Azure Key Vault
    secrets = SecretsManager(provider="azure", vault_url="https://myvault.vault.azure.net/")
    api_key = secrets.get_secret("anthropic-api-key")

    # Usando GCP Secret Manager
    secrets = SecretsManager(provider="gcp", project_id="my-project")
    api_key = secrets.get_secret("anthropic-api-key")
    """

    def __init__(self, provider: str = "env", **kwargs):
        """
        Inicializa o gerenciador de secrets

        Args:
            provider: Tipo de provedor ("env", "aws", "azure", "gcp")
            **kwargs: Argumentos específicos do provedor
        """
        self.provider_type = provider.lower()

        if self.provider_type == "env":
            self.provider = EnvironmentSecretsProvider()

        elif self.provider_type == "aws":
            region_name = kwargs.get("region_name", "us-east-1")
            self.provider = AWSSecretsManagerProvider(region_name=region_name)

        elif self.provider_type == "azure":
            vault_url = kwargs.get("vault_url")
            if not vault_url:
                raise ValueError("vault_url is required for Azure Key Vault")
            self.provider = AzureKeyVaultProvider(vault_url=vault_url)

        elif self.provider_type == "gcp":
            project_id = kwargs.get("project_id")
            if not project_id:
                raise ValueError("project_id is required for GCP Secret Manager")
            self.provider = GCPSecretManagerProvider(project_id=project_id)

        else:
            raise ValueError(f"Unknown provider: {provider}")

        logger.info(f"SecretsManager initialized with provider: {self.provider_type}")

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> str:
        """
        Obtém um secret

        Args:
            secret_name: Nome do secret
            default: Valor padrão se secret não for encontrado

        Returns:
            Valor do secret ou default
        """
        value = self.provider.get_secret(secret_name)
        if value is None:
            if default is not None:
                logger.warning(f"Secret {secret_name} not found, using default value")
                return default
            logger.error(f"Secret {secret_name} not found and no default provided")
            raise ValueError(f"Secret {secret_name} not found")
        return value

    def get_secret_dict(self, secret_name: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Obtém um secret em formato de dicionário

        Args:
            secret_name: Nome do secret
            default: Valor padrão se secret não for encontrado

        Returns:
            Dicionário com valores do secret ou default
        """
        value = self.provider.get_secret_dict(secret_name)
        if value is None:
            if default is not None:
                logger.warning(f"Secret {secret_name} not found, using default value")
                return default
            logger.error(f"Secret {secret_name} not found and no default provided")
            raise ValueError(f"Secret {secret_name} not found")
        return value
