# Gerenciamento de Secrets

Este projeto suporta múltiplos provedores de secrets para maior flexibilidade e segurança.

## Provedores Suportados

### 1. Variáveis de Ambiente (Padrão)

Mais simples, adequado para desenvolvimento local.

```python
from app.core.secrets_manager import SecretsManager

secrets = SecretsManager(provider="env")
api_key = secrets.get_secret("ANTHROPIC_API_KEY")
```

### 2. AWS Secrets Manager

Recomendado para ambientes AWS (EC2, ECS, Lambda).

**Instalação:**
```bash
pip install boto3
```

**Configuração:**
```python
secrets = SecretsManager(
    provider="aws",
    region_name="us-east-1"
)
api_key = secrets.get_secret("prod/anthropic_api_key")
```

**IAM Permissions necessárias:**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:*"
        }
    ]
}
```

### 3. Azure Key Vault

Recomendado para ambientes Azure.

**Instalação:**
```bash
pip install azure-keyvault-secrets azure-identity
```

**Configuração:**
```python
secrets = SecretsManager(
    provider="azure",
    vault_url="https://myvault.vault.azure.net/"
)
api_key = secrets.get_secret("anthropic-api-key")
```

**Permissões necessárias:**
- Managed Identity ou Service Principal com permissão "Get" em secrets

### 4. GCP Secret Manager

Recomendado para ambientes Google Cloud.

**Instalação:**
```bash
pip install google-cloud-secret-manager
```

**Configuração:**
```python
secrets = SecretsManager(
    provider="gcp",
    project_id="my-project-id"
)
api_key = secrets.get_secret("anthropic-api-key")
```

**Permissões necessárias:**
- Service Account com role `roles/secretmanager.secretAccessor`

## Uso no Projeto

### Atualizar config.py

```python
from app.core.secrets_manager import SecretsManager
import os

# Determinar provedor baseado em variável de ambiente
SECRETS_PROVIDER = os.getenv("SECRETS_PROVIDER", "env")

if SECRETS_PROVIDER == "aws":
    secrets = SecretsManager(
        provider="aws",
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
elif SECRETS_PROVIDER == "azure":
    secrets = SecretsManager(
        provider="azure",
        vault_url=os.getenv("AZURE_VAULT_URL")
    )
elif SECRETS_PROVIDER == "gcp":
    secrets = SecretsManager(
        provider="gcp",
        project_id=os.getenv("GCP_PROJECT_ID")
    )
else:
    secrets = SecretsManager(provider="env")

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = secrets.get_secret("ANTHROPIC_API_KEY")
    SERPAPI_API_KEY: str = secrets.get_secret("SERPAPI_API_KEY")
    SECRET_KEY: str = secrets.get_secret("SECRET_KEY")
```

## Migração de .env para Secrets Manager

### AWS Secrets Manager

```bash
# Criar secret
aws secretsmanager create-secret \
    --name prod/app-secrets \
    --secret-string '{
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "SERPAPI_API_KEY": "...",
        "SECRET_KEY": "..."
    }'

# Recuperar secret (teste)
aws secretsmanager get-secret-value --secret-id prod/app-secrets
```

### Azure Key Vault

```bash
# Criar secrets individuais
az keyvault secret set --vault-name myvault --name anthropic-api-key --value "sk-ant-..."
az keyvault secret set --vault-name myvault --name serpapi-api-key --value "..."
az keyvault secret set --vault-name myvault --name secret-key --value "..."
```

### GCP Secret Manager

```bash
# Criar secrets
echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-
echo -n "..." | gcloud secrets create serpapi-api-key --data-file=-
echo -n "..." | gcloud secrets create secret-key --data-file=-
```

## Variáveis de Ambiente para Produção

```bash
# .env (produção)
SECRETS_PROVIDER=aws  # ou azure, gcp
AWS_REGION=us-east-1
# ou
# AZURE_VAULT_URL=https://myvault.vault.azure.net/
# ou
# GCP_PROJECT_ID=my-project-id
```

## Rotação de Secrets

### AWS
- Habilitar rotação automática no console
- Lambda function para rotação

### Azure
- Usar Event Grid para notificações
- Automation Account para rotação

### GCP
- Cloud Scheduler + Cloud Function
- Secret Manager Rotation

## Auditoria

Todos os provedores mantêm logs de acesso:
- **AWS**: CloudTrail
- **Azure**: Activity Log
- **GCP**: Cloud Audit Logs

## Recomendações de Segurança

1. **Nunca commitar .env com secrets reais**
2. **Usar secrets manager em produção**
3. **Rotacionar secrets regularmente** (trimestral mínimo)
4. **Aplicar princípio de menor privilégio** (IAM/RBAC)
5. **Monitorar acessos** (alertas para acessos suspeitos)
6. **Criptografar secrets em trânsito e em repouso**
7. **Usar secrets diferentes por ambiente** (dev/staging/prod)

## Troubleshooting

### Erro: "Secret not found"
- Verificar nome do secret (case-sensitive)
- Verificar permissões (IAM/RBAC)
- Verificar região/projeto correto

### Erro: "Access denied"
- Verificar credenciais (AWS_ACCESS_KEY, Azure Managed Identity, GCP Service Account)
- Verificar policies/roles
- Verificar firewall/network access

### Performance
- Secrets são cached automaticamente pelos SDKs
- Evitar chamadas excessivas (usar cache local se necessário)
