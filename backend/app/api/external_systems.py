"""
API para gerenciamento de Sistemas Externos (Integração ASI e outros)
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import httpx
import json
import time
import base64
from cryptography.fernet import Fernet
from app.core.database import get_db
from app.core.config import settings
from app.models import (
    ExternalSystem,
    InventoryMasterUG,
    InventoryMasterUL,
    InventoryMasterUA,
    InventoryMasterPhysicalStatus,
    InventoryMasterCharacteristic,
    InventoryMasterSyncLog,
)

router = APIRouter(prefix="/api/inventory/systems", tags=["external-systems"])


# =====================================================
# SERVIÇO DE CRIPTOGRAFIA
# =====================================================

def get_encryption_key() -> bytes:
    """Obtém ou gera chave de criptografia"""
    # Usar uma chave derivada do SECRET_KEY do sistema
    key = getattr(settings, 'SECRET_KEY', 'default-secret-key-change-me')
    # Criar chave Fernet válida (32 bytes base64)
    key_bytes = key.encode()[:32].ljust(32, b'0')
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_value(value: str) -> str:
    """Criptografa um valor"""
    if not value:
        return None
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Descriptografa um valor"""
    if not encrypted:
        return None
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return None


# =====================================================
# SCHEMAS
# =====================================================

class ExternalSystemBase(BaseModel):
    name: str = Field(..., max_length=100)
    system_type: str = Field(default="asi", max_length=50)
    host: str = Field(..., max_length=255)
    port: Optional[int] = None
    context_path: Optional[str] = Field(None, max_length=100)
    auth_type: str = Field(default="basic", max_length=30)
    auth_username: Optional[str] = Field(None, max_length=100)
    timeout_seconds: int = Field(default=60)
    retry_attempts: int = Field(default=3)
    double_json_encoding: bool = Field(default=True)


class ExternalSystemCreate(ExternalSystemBase):
    auth_password: Optional[str] = None  # Senha em texto plano (será criptografada)
    auth_token: Optional[str] = None  # Token em texto plano (será criptografado)
    auth_header_name: Optional[str] = None


class ExternalSystemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    system_type: Optional[str] = Field(None, max_length=50)
    host: Optional[str] = Field(None, max_length=255)
    port: Optional[int] = None
    context_path: Optional[str] = Field(None, max_length=100)
    auth_type: Optional[str] = Field(None, max_length=30)
    auth_username: Optional[str] = Field(None, max_length=100)
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header_name: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_attempts: Optional[int] = None
    double_json_encoding: Optional[bool] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ExternalSystemResponse(BaseModel):
    id: int
    name: str
    system_type: str
    host: str
    port: Optional[int]
    context_path: Optional[str]
    full_url: Optional[str]
    auth_type: str
    auth_username: Optional[str]
    timeout_seconds: int
    retry_attempts: int
    double_json_encoding: bool
    is_active: bool
    is_default: bool
    last_test_at: Optional[datetime]
    last_test_success: Optional[bool]
    last_test_message: Optional[str]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    # Contagens
    total_ugs: int = 0
    total_uls: int = 0
    total_uas: int = 0

    class Config:
        from_attributes = True


class ExternalSystemListResponse(BaseModel):
    items: List[ExternalSystemResponse]
    total: int


class ConnectionTestRequest(BaseModel):
    host: str
    port: Optional[int] = None
    context_path: Optional[str] = None
    auth_type: str = "basic"
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header_name: Optional[str] = None
    timeout_seconds: int = 60
    endpoint_test: str = "/coletorweb/servicecoletor/atualizar"


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    response_time_ms: Optional[int] = None
    server_version: Optional[str] = None
    error_type: Optional[str] = None
    technical_details: Optional[str] = None


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def build_full_url(host: str, port: Optional[int], context_path: Optional[str]) -> str:
    """Monta a URL completa do sistema"""
    url = host.rstrip('/')
    if port:
        url += f":{port}"
    if context_path:
        url += '/' + context_path.strip('/')
    return url


def get_auth_headers(system: ExternalSystem) -> dict:
    """Monta headers de autenticação baseado no tipo"""
    headers = {}

    if system.auth_type == "basic":
        if system.auth_username and system.auth_password_encrypted:
            password = decrypt_value(system.auth_password_encrypted)
            if password:
                credentials = f"{system.auth_username}:{password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

    elif system.auth_type == "bearer":
        if system.auth_token_encrypted:
            token = decrypt_value(system.auth_token_encrypted)
            if token:
                headers["Authorization"] = f"Bearer {token}"

    elif system.auth_type == "api_key":
        if system.auth_token_encrypted and system.auth_header_name:
            token = decrypt_value(system.auth_token_encrypted)
            if token:
                headers[system.auth_header_name] = token

    return headers


async def test_connection(
    url: str,
    endpoint: str,
    auth_headers: dict,
    timeout: int,
    double_json: bool = True
) -> ConnectionTestResponse:
    """Testa conexão com o servidor externo"""
    full_url = url + endpoint
    start_time = time.time()

    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            response = await client.get(full_url, headers=auth_headers)
            response_time = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                # Tentar extrair versão do servidor
                server_version = None
                try:
                    body = response.text
                    if double_json:
                        body = json.loads(body)
                    if body and body != "0":
                        server_version = str(body)[:50]
                except Exception:
                    pass

                return ConnectionTestResponse(
                    success=True,
                    message="Conexão efetuada com sucesso",
                    response_time_ms=response_time,
                    server_version=server_version
                )

            elif response.status_code == 401 or response.status_code == 403:
                return ConnectionTestResponse(
                    success=False,
                    message="Falha na autenticação",
                    error_type="auth_failed",
                    technical_details=f"HTTP {response.status_code}: {response.text[:200]}"
                )

            elif response.status_code == 404:
                return ConnectionTestResponse(
                    success=False,
                    message="Endpoint não encontrado no servidor",
                    error_type="not_found",
                    technical_details=f"URL: {full_url}"
                )

            else:
                return ConnectionTestResponse(
                    success=False,
                    message=f"Erro HTTP {response.status_code}",
                    error_type="http_error",
                    technical_details=response.text[:500]
                )

    except httpx.TimeoutException:
        return ConnectionTestResponse(
            success=False,
            message="Tempo de conexão esgotado (timeout)",
            error_type="timeout",
            technical_details=f"Timeout após {timeout} segundos"
        )

    except httpx.ConnectError as e:
        error_msg = str(e).lower()

        if "ssl" in error_msg or "certificate" in error_msg:
            return ConnectionTestResponse(
                success=False,
                message="Erro de certificado SSL",
                error_type="ssl_error",
                technical_details=str(e)
            )

        if "refused" in error_msg:
            return ConnectionTestResponse(
                success=False,
                message="Conexão recusada pelo servidor",
                error_type="connection_refused",
                technical_details=str(e)
            )

        if "name or service not known" in error_msg or "getaddrinfo" in error_msg:
            return ConnectionTestResponse(
                success=False,
                message="Servidor não encontrado (erro DNS)",
                error_type="dns_error",
                technical_details=str(e)
            )

        return ConnectionTestResponse(
            success=False,
            message="Não foi possível conectar ao servidor",
            error_type="connection_error",
            technical_details=str(e)
        )

    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message="Erro desconhecido",
            error_type="unknown",
            technical_details=str(e)
        )


def system_to_response(system: ExternalSystem, db: Session) -> ExternalSystemResponse:
    """Converte model para response com contagens"""
    total_ugs = db.query(func.count(InventoryMasterUG.id)).filter(
        InventoryMasterUG.external_system_id == system.id
    ).scalar() or 0

    total_uls = db.query(func.count(InventoryMasterUL.id)).filter(
        InventoryMasterUL.external_system_id == system.id
    ).scalar() or 0

    total_uas = db.query(func.count(InventoryMasterUA.id)).filter(
        InventoryMasterUA.external_system_id == system.id
    ).scalar() or 0

    return ExternalSystemResponse(
        id=system.id,
        name=system.name,
        system_type=system.system_type,
        host=system.host,
        port=system.port,
        context_path=system.context_path,
        full_url=system.full_url,
        auth_type=system.auth_type,
        auth_username=system.auth_username,
        timeout_seconds=system.timeout_seconds,
        retry_attempts=system.retry_attempts,
        double_json_encoding=system.double_json_encoding,
        is_active=system.is_active,
        is_default=system.is_default or False,
        last_test_at=system.last_test_at,
        last_test_success=system.last_test_success,
        last_test_message=system.last_test_message,
        last_sync_at=system.last_sync_at,
        created_at=system.created_at,
        updated_at=system.updated_at,
        total_ugs=total_ugs,
        total_uls=total_uls,
        total_uas=total_uas,
    )


# =====================================================
# ENDPOINTS CRUD
# =====================================================

@router.get("", response_model=ExternalSystemListResponse)
def list_external_systems(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """Lista todos os sistemas externos configurados"""
    query = db.query(ExternalSystem)

    if active_only:
        query = query.filter(ExternalSystem.is_active == True)

    systems = query.order_by(ExternalSystem.name).all()

    items = [system_to_response(s, db) for s in systems]

    return ExternalSystemListResponse(items=items, total=len(items))


@router.get("/{system_id}", response_model=ExternalSystemResponse)
def get_external_system(system_id: int, db: Session = Depends(get_db)):
    """Obtém detalhes de um sistema externo"""
    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    return system_to_response(system, db)


@router.post("", response_model=ExternalSystemResponse)
def create_external_system(
    data: ExternalSystemCreate,
    db: Session = Depends(get_db)
):
    """Cria configuração de sistema externo"""
    # Montar URL completa
    full_url = build_full_url(data.host, data.port, data.context_path)

    # Criptografar senha/token
    password_encrypted = encrypt_value(data.auth_password) if data.auth_password else None
    token_encrypted = encrypt_value(data.auth_token) if data.auth_token else None

    system = ExternalSystem(
        name=data.name,
        system_type=data.system_type,
        host=data.host,
        port=data.port,
        context_path=data.context_path,
        full_url=full_url,
        auth_type=data.auth_type,
        auth_username=data.auth_username,
        auth_password_encrypted=password_encrypted,
        auth_token_encrypted=token_encrypted,
        auth_header_name=data.auth_header_name,
        timeout_seconds=data.timeout_seconds,
        retry_attempts=data.retry_attempts,
        double_json_encoding=data.double_json_encoding,
    )

    db.add(system)
    db.commit()
    db.refresh(system)

    return system_to_response(system, db)


@router.put("/{system_id}", response_model=ExternalSystemResponse)
def update_external_system(
    system_id: int,
    data: ExternalSystemUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza configuração de sistema externo"""
    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Tratar senha/token separadamente
    if "auth_password" in update_data:
        password = update_data.pop("auth_password")
        if password:
            system.auth_password_encrypted = encrypt_value(password)

    if "auth_token" in update_data:
        token = update_data.pop("auth_token")
        if token:
            system.auth_token_encrypted = encrypt_value(token)

    # Atualizar demais campos
    for field, value in update_data.items():
        setattr(system, field, value)

    # Se is_default=True, desmarcar outros
    if data.is_default:
        db.query(ExternalSystem).filter(
            ExternalSystem.id != system_id
        ).update({"is_default": False})

    # Recalcular URL completa
    system.full_url = build_full_url(
        system.host,
        system.port,
        system.context_path
    )

    db.commit()
    db.refresh(system)

    return system_to_response(system, db)


@router.delete("/{system_id}")
def delete_external_system(system_id: int, db: Session = Depends(get_db)):
    """Remove sistema externo"""
    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    # Verificar se há dados mestres vinculados
    total_data = (
        db.query(func.count(InventoryMasterUG.id)).filter(
            InventoryMasterUG.external_system_id == system_id
        ).scalar() or 0
    )

    if total_data > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Sistema possui {total_data} registros de dados mestres. Remova os dados antes de excluir."
        )

    db.delete(system)
    db.commit()

    return {"message": "Sistema removido com sucesso"}


# =====================================================
# ENDPOINTS DE TESTE DE CONEXÃO
# =====================================================

@router.post("/{system_id}/test", response_model=ConnectionTestResponse)
async def test_system_connection(system_id: int, db: Session = Depends(get_db)):
    """Testa conexão com um sistema externo já cadastrado"""
    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    # Montar headers de autenticação
    auth_headers = get_auth_headers(system)

    # Testar conexão
    result = await test_connection(
        url=system.full_url or build_full_url(system.host, system.port, system.context_path),
        endpoint=system.endpoint_test,
        auth_headers=auth_headers,
        timeout=system.timeout_seconds,
        double_json=system.double_json_encoding
    )

    # Atualizar status do sistema
    system.last_test_at = datetime.utcnow()
    system.last_test_success = result.success
    system.last_test_message = result.message
    db.commit()

    return result


@router.post("/test-url", response_model=ConnectionTestResponse)
async def test_url_connection(data: ConnectionTestRequest):
    """Testa conexão com uma URL sem salvar (para validar antes de criar)"""
    # Montar URL
    url = build_full_url(data.host, data.port, data.context_path)

    # Montar headers de autenticação
    auth_headers = {}
    if data.auth_type == "basic" and data.auth_username and data.auth_password:
        credentials = f"{data.auth_username}:{data.auth_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        auth_headers["Authorization"] = f"Basic {encoded}"
    elif data.auth_type == "bearer" and data.auth_token:
        auth_headers["Authorization"] = f"Bearer {data.auth_token}"
    elif data.auth_type == "api_key" and data.auth_token and data.auth_header_name:
        auth_headers[data.auth_header_name] = data.auth_token

    # Testar conexão
    result = await test_connection(
        url=url,
        endpoint=data.endpoint_test,
        auth_headers=auth_headers,
        timeout=data.timeout_seconds
    )

    return result


# =====================================================
# ENDPOINTS DE SINCRONIZAÇÃO
# =====================================================

class SyncRequest(BaseModel):
    sync_types: List[str] = Field(default=["all"])  # all, ug, ul, characteristics, physical_status


class SyncResult(BaseModel):
    sync_type: str
    success: bool
    received: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    error: Optional[str] = None


class SyncResponse(BaseModel):
    success: bool
    message: str
    results: List[SyncResult]


@router.post("/{system_id}/sync", response_model=SyncResponse)
async def sync_external_system(
    system_id: int,
    data: SyncRequest,
    db: Session = Depends(get_db)
):
    """Sincroniza dados mestres do sistema externo"""
    from app.services.external_system_sync import ExternalSystemSyncService

    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    if not system.is_active:
        raise HTTPException(status_code=400, detail="Sistema está inativo")

    sync_service = ExternalSystemSyncService(db, system)
    results = []
    has_errors = False

    sync_types = data.sync_types
    if "all" in sync_types:
        sync_types = ["ug", "ul", "physical_status", "characteristics"]

    for sync_type in sync_types:
        try:
            if sync_type == "ug":
                result = await sync_service.sync_ugs()
            elif sync_type == "ul":
                result = await sync_service.sync_uls()
            elif sync_type == "physical_status":
                result = await sync_service.sync_physical_status()
            elif sync_type == "characteristics":
                result = await sync_service.sync_characteristics()
            else:
                results.append(SyncResult(
                    sync_type=sync_type,
                    success=False,
                    error=f"Tipo de sincronização desconhecido: {sync_type}"
                ))
                has_errors = True
                continue

            results.append(SyncResult(
                sync_type=sync_type,
                success=True,
                received=result.get("received", 0),
                created=result.get("created", 0),
                updated=result.get("updated", 0),
                failed=result.get("failed", 0)
            ))

            if result.get("failed", 0) > 0:
                has_errors = True

        except Exception as e:
            results.append(SyncResult(
                sync_type=sync_type,
                success=False,
                error=str(e)
            ))
            has_errors = True

    return SyncResponse(
        success=not has_errors,
        message="Sincronização concluída com sucesso" if not has_errors else "Sincronização concluída com erros",
        results=results
    )


@router.post("/{system_id}/sync/ug")
async def sync_ugs(system_id: int, db: Session = Depends(get_db)):
    """Sincroniza apenas UGs"""
    from app.services.external_system_sync import ExternalSystemSyncService

    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    sync_service = ExternalSystemSyncService(db, system)
    result = await sync_service.sync_ugs()
    return result


@router.post("/{system_id}/sync/ul")
async def sync_uls(system_id: int, db: Session = Depends(get_db)):
    """Sincroniza apenas ULs"""
    from app.services.external_system_sync import ExternalSystemSyncService

    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    sync_service = ExternalSystemSyncService(db, system)
    result = await sync_service.sync_uls()
    return result


@router.post("/{system_id}/sync/physical-status")
async def sync_physical_status(system_id: int, db: Session = Depends(get_db)):
    """Sincroniza apenas situações físicas"""
    from app.services.external_system_sync import ExternalSystemSyncService

    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    sync_service = ExternalSystemSyncService(db, system)
    result = await sync_service.sync_physical_status()
    return result


@router.post("/{system_id}/sync/characteristics")
async def sync_characteristics(system_id: int, db: Session = Depends(get_db)):
    """Sincroniza apenas características"""
    from app.services.external_system_sync import ExternalSystemSyncService

    system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado")

    sync_service = ExternalSystemSyncService(db, system)
    result = await sync_service.sync_characteristics()
    return result


# =====================================================
# ENDPOINTS DE DADOS MESTRES
# =====================================================

@router.get("/{system_id}/ug")
def list_system_ugs(
    system_id: int,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista UGs sincronizadas do sistema"""
    query = db.query(InventoryMasterUG).filter(
        InventoryMasterUG.external_system_id == system_id
    )

    if search:
        query = query.filter(
            InventoryMasterUG.name.ilike(f"%{search}%") |
            InventoryMasterUG.code.ilike(f"%{search}%")
        )

    ugs = query.order_by(InventoryMasterUG.name).all()

    return [
        {
            "id": ug.id,
            "code": ug.code,
            "name": ug.name,
            "synced_at": ug.synced_at
        }
        for ug in ugs
    ]


@router.get("/{system_id}/ul")
def list_system_uls(
    system_id: int,
    ug_code: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista ULs sincronizadas do sistema"""
    query = db.query(InventoryMasterUL).filter(
        InventoryMasterUL.external_system_id == system_id
    )

    if ug_code:
        ug = db.query(InventoryMasterUG).filter(
            InventoryMasterUG.external_system_id == system_id,
            InventoryMasterUG.code == ug_code
        ).first()
        if ug:
            query = query.filter(InventoryMasterUL.ug_id == ug.id)

    if search:
        query = query.filter(
            InventoryMasterUL.name.ilike(f"%{search}%") |
            InventoryMasterUL.code.ilike(f"%{search}%")
        )

    uls = query.order_by(InventoryMasterUL.name).all()

    return [
        {
            "id": ul.id,
            "code": ul.code,
            "name": ul.name,
            "ug_id": ul.ug_id,
            "latitude": float(ul.latitude) if ul.latitude else None,
            "longitude": float(ul.longitude) if ul.longitude else None,
            "radius_meters": ul.radius_meters,
            "synced_at": ul.synced_at
        }
        for ul in uls
    ]


@router.get("/{system_id}/physical-status")
def list_physical_statuses(system_id: int, db: Session = Depends(get_db)):
    """Lista situações físicas sincronizadas do sistema"""
    statuses = db.query(InventoryMasterPhysicalStatus).filter(
        InventoryMasterPhysicalStatus.external_system_id == system_id
    ).order_by(InventoryMasterPhysicalStatus.name).all()

    return [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "description": s.description,
            "synced_at": s.synced_at
        }
        for s in statuses
    ]


@router.get("/{system_id}/characteristics")
def list_characteristics(system_id: int, db: Session = Depends(get_db)):
    """Lista características de bens sincronizadas do sistema"""
    chars = db.query(InventoryMasterCharacteristic).filter(
        InventoryMasterCharacteristic.external_system_id == system_id
    ).order_by(InventoryMasterCharacteristic.name).all()

    return [
        {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "type": c.type,
            "required": c.required,
            "options": c.options,
            "synced_at": c.synced_at
        }
        for c in chars
    ]


@router.get("/{system_id}/sync/logs")
def list_sync_logs(
    system_id: int,
    sync_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Lista histórico de sincronizações do sistema"""
    query = db.query(InventoryMasterSyncLog).filter(
        InventoryMasterSyncLog.external_system_id == system_id
    )

    if sync_type:
        query = query.filter(InventoryMasterSyncLog.sync_type == sync_type)

    logs = query.order_by(InventoryMasterSyncLog.started_at.desc()).limit(limit).all()

    return [
        {
            "id": log.id,
            "sync_type": log.sync_type,
            "status": log.status,
            "items_received": log.items_received,
            "items_created": log.items_created,
            "items_updated": log.items_updated,
            "items_failed": log.items_failed,
            "error_message": log.error_message,
            "started_at": log.started_at,
            "completed_at": log.completed_at
        }
        for log in logs
    ]


# =====================================================
# ENDPOINT PADRÃO (GET DEFAULT SYSTEM)
# =====================================================

@router.get("/default/info")
def get_default_system(db: Session = Depends(get_db)):
    """Obtém o sistema externo padrão do sistema"""
    system = db.query(ExternalSystem).filter(
        ExternalSystem.is_default == True,
        ExternalSystem.is_active == True
    ).first()

    if not system:
        # Tentar pegar o primeiro ativo
        system = db.query(ExternalSystem).filter(
            ExternalSystem.is_active == True
        ).first()

    if not system:
        return {"configured": False, "system": None}

    return {
        "configured": True,
        "system": system_to_response(system, db)
    }
