from azure.identity import AzureCliCredential
from azure.keyvault.secrets import SecretClient


VAULT_NAME = "kv-eversys-gold"
VAULT_URL = f"https://{VAULT_NAME}.vault.azure.net/"


credential = AzureCliCredential()

client = SecretClient(
    vault_url=VAULT_URL,
    credential=credential
)


def get_secret(name: str) -> str:
    return client.get_secret(name).value


DB_CONFIG = {
    "server": get_secret("gold-db-server"),
    "database": get_secret("gold-db-database"),
    "username": get_secret("gold-db-username"),
    "password": get_secret("gold-db-password"),
    "driver": get_secret("gold-db-driver"),
}