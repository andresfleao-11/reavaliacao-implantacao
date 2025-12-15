from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.models.project_config import ProjectConfigVersion, ProjectBankPrice
from app.models.project import Project

router = APIRouter(prefix="/api/projects/{project_id}/config", tags=["project-config"])


# ==================== SCHEMAS ====================

class BankPriceItem(BaseModel):
    codigo: str
    material: str
    caracteristicas: Optional[str] = None
    vl_mercado: Optional[float] = None
    update_mode: str = "MARKET"


class ConfigVersionCreate(BaseModel):
    descricao_alteracao: Optional[str] = None
    criado_por: Optional[str] = None

    # Parâmetros de cotação
    numero_cotacoes_por_pesquisa: Optional[int] = None
    variacao_maxima_percent: Optional[float] = None
    pesquisador_padrao: Optional[str] = None
    local_padrao: Optional[str] = None

    # Parâmetros de busca
    serpapi_location: Optional[str] = None
    serpapi_gl: str = "br"
    serpapi_hl: str = "pt"
    serpapi_num_results: int = 10
    search_timeout: int = 30
    max_sources: int = 10

    # Banco de preços
    banco_precos: Optional[List[BankPriceItem]] = None

    # Fator de reavaliação
    ec_map: Optional[Dict[str, float]] = None
    pu_map: Optional[Dict[str, float]] = None
    vuf_map: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None


class ConfigVersionUpdate(BaseModel):
    descricao_alteracao: Optional[str] = None

    # Parâmetros de cotação
    numero_cotacoes_por_pesquisa: Optional[int] = None
    variacao_maxima_percent: Optional[float] = None
    pesquisador_padrao: Optional[str] = None
    local_padrao: Optional[str] = None

    # Parâmetros de busca
    serpapi_location: Optional[str] = None
    serpapi_gl: Optional[str] = None
    serpapi_hl: Optional[str] = None
    serpapi_num_results: Optional[int] = None
    search_timeout: Optional[int] = None
    max_sources: Optional[int] = None

    # Banco de preços
    banco_precos: Optional[List[BankPriceItem]] = None

    # Fator de reavaliação
    ec_map: Optional[Dict[str, float]] = None
    pu_map: Optional[Dict[str, float]] = None
    vuf_map: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None


class BankPriceResponse(BaseModel):
    id: int
    codigo: str
    material: str
    caracteristicas: Optional[str] = None
    vl_mercado: Optional[float] = None
    update_mode: str

    class Config:
        from_attributes = True


class ConfigVersionResponse(BaseModel):
    id: int
    project_id: int
    versao: int
    descricao_alteracao: Optional[str] = None
    criado_por: Optional[str] = None
    ativo: bool
    created_at: datetime

    # Parâmetros de cotação
    numero_cotacoes_por_pesquisa: Optional[int] = None
    variacao_maxima_percent: Optional[float] = None
    pesquisador_padrao: Optional[str] = None
    local_padrao: Optional[str] = None

    # Parâmetros de busca
    serpapi_location: Optional[str] = None
    serpapi_gl: Optional[str] = None
    serpapi_hl: Optional[str] = None
    serpapi_num_results: Optional[int] = None
    search_timeout: Optional[int] = None
    max_sources: Optional[int] = None

    # Fator de reavaliação
    ec_map: Optional[Dict[str, float]] = None
    pu_map: Optional[Dict[str, float]] = None
    vuf_map: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None

    # Banco de preços
    banco_precos: List[BankPriceResponse] = []

    # Estatísticas
    total_cotacoes: int = 0

    # Resumo de mudanças (calculado)
    resumo_mudancas: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ConfigVersionListResponse(BaseModel):
    items: List[ConfigVersionResponse]
    total: int


# ==================== HELPER FUNCTIONS ====================

def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


def get_next_version_number(project_id: int, db: Session) -> int:
    max_version = db.query(func.max(ProjectConfigVersion.versao)).filter(
        ProjectConfigVersion.project_id == project_id
    ).scalar()
    return (max_version or 0) + 1


def calculate_resumo_mudancas(config: ProjectConfigVersion, prev_config: Optional[ProjectConfigVersion], db: Session) -> Dict[str, Any]:
    """Calcula resumo das mudanças entre esta versão e a anterior"""
    if not prev_config:
        return {
            "tipo": "criacao",
            "mensagem": "Primeira versão criada"
        }

    mudancas = []

    # Comparar parâmetros
    params_labels = {
        "numero_cotacoes_por_pesquisa": "Número de cotações por pesquisa",
        "variacao_maxima_percent": "Variação máxima"
    }

    for field, label in params_labels.items():
        old_val = getattr(prev_config, field)
        new_val = getattr(config, field)
        if old_val != new_val:
            mudancas.append(f"{label}: {old_val} → {new_val}")

    # Comparar fatores de reavaliação
    if config.ec_map_json != prev_config.ec_map_json:
        mudancas.append("Fator EC alterado")
    if config.pu_map_json != prev_config.pu_map_json:
        mudancas.append("Fator PU alterado")
    if config.vuf_map_json != prev_config.vuf_map_json:
        mudancas.append("Fator VUF alterado")
    if config.weights_json != prev_config.weights_json:
        mudancas.append("Pesos alterados")

    # Comparar banco de preços
    curr_bank = db.query(ProjectBankPrice).filter(ProjectBankPrice.config_version_id == config.id).count()
    prev_bank = db.query(ProjectBankPrice).filter(ProjectBankPrice.config_version_id == prev_config.id).count()
    if curr_bank != prev_bank:
        mudancas.append(f"Banco de preços: {prev_bank} → {curr_bank} itens")

    return {
        "tipo": "atualizacao",
        "total_mudancas": len(mudancas),
        "mudancas": mudancas
    }


def config_to_response(config: ProjectConfigVersion, db: Session, include_changes: bool = False) -> ConfigVersionResponse:
    # Contar cotações vinculadas
    total_cotacoes = len(config.cotacoes) if config.cotacoes else 0

    # Buscar itens do banco de preços
    bank_prices = db.query(ProjectBankPrice).filter(
        ProjectBankPrice.config_version_id == config.id
    ).all()

    # Calcular resumo de mudanças se solicitado
    resumo_mudancas = None
    if include_changes:
        prev_config = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.project_id == config.project_id,
            ProjectConfigVersion.versao == config.versao - 1
        ).first()
        resumo_mudancas = calculate_resumo_mudancas(config, prev_config, db)

    return ConfigVersionResponse(
        id=config.id,
        project_id=config.project_id,
        versao=config.versao,
        descricao_alteracao=config.descricao_alteracao,
        criado_por=config.criado_por,
        ativo=config.ativo,
        created_at=config.created_at,
        # Parâmetros de cotação
        numero_cotacoes_por_pesquisa=config.numero_cotacoes_por_pesquisa,
        variacao_maxima_percent=float(config.variacao_maxima_percent) if config.variacao_maxima_percent else None,
        pesquisador_padrao=config.pesquisador_padrao,
        local_padrao=config.local_padrao,
        # Parâmetros de busca
        serpapi_location=config.serpapi_location,
        serpapi_gl=config.serpapi_gl,
        serpapi_hl=config.serpapi_hl,
        serpapi_num_results=config.serpapi_num_results,
        search_timeout=config.search_timeout,
        max_sources=config.max_sources,
        ec_map=config.ec_map_json,
        pu_map=config.pu_map_json,
        vuf_map=config.vuf_map_json,
        weights=config.weights_json,
        banco_precos=[
            BankPriceResponse(
                id=bp.id,
                codigo=bp.codigo,
                material=bp.material,
                caracteristicas=bp.caracteristicas,
                vl_mercado=float(bp.vl_mercado) if bp.vl_mercado else None,
                update_mode=bp.update_mode
            ) for bp in bank_prices
        ],
        total_cotacoes=total_cotacoes,
        resumo_mudancas=resumo_mudancas
    )


# ==================== ENDPOINTS ====================

@router.get("/versions", response_model=ConfigVersionListResponse)
def list_config_versions(project_id: int, db: Session = Depends(get_db)):
    """Lista todas as versões de configuração de um projeto"""
    get_project_or_404(project_id, db)

    configs = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.project_id == project_id
    ).order_by(ProjectConfigVersion.versao.desc()).all()

    return ConfigVersionListResponse(
        items=[config_to_response(c, db, include_changes=True) for c in configs],
        total=len(configs)
    )


@router.get("/versions/active", response_model=Optional[ConfigVersionResponse])
def get_active_config_version(project_id: int, db: Session = Depends(get_db)):
    """Obtém a versão ativa de configuração do projeto"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.project_id == project_id,
        ProjectConfigVersion.ativo == True
    ).first()

    if not config:
        return None

    return config_to_response(config, db)


@router.get("/versions/{version_id}", response_model=ConfigVersionResponse)
def get_config_version(project_id: int, version_id: int, db: Session = Depends(get_db)):
    """Obtém uma versão específica de configuração"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    return config_to_response(config, db)


@router.post("/versions", response_model=ConfigVersionResponse)
def create_config_version(
    project_id: int,
    data: ConfigVersionCreate,
    db: Session = Depends(get_db)
):
    """Cria uma nova versão de configuração do projeto"""
    get_project_or_404(project_id, db)

    # Desativar versões anteriores
    db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.project_id == project_id,
        ProjectConfigVersion.ativo == True
    ).update({"ativo": False})

    # Criar nova versão
    next_version = get_next_version_number(project_id, db)

    config = ProjectConfigVersion(
        project_id=project_id,
        versao=next_version,
        descricao_alteracao=data.descricao_alteracao,
        criado_por=data.criado_por,
        ativo=True,
        # Parâmetros de cotação
        numero_cotacoes_por_pesquisa=data.numero_cotacoes_por_pesquisa,
        variacao_maxima_percent=data.variacao_maxima_percent,
        pesquisador_padrao=data.pesquisador_padrao,
        local_padrao=data.local_padrao,
        # Parâmetros de busca
        serpapi_location=data.serpapi_location,
        serpapi_gl=data.serpapi_gl,
        serpapi_hl=data.serpapi_hl,
        serpapi_num_results=data.serpapi_num_results,
        search_timeout=data.search_timeout,
        max_sources=data.max_sources,
        ec_map_json=data.ec_map,
        pu_map_json=data.pu_map,
        vuf_map_json=data.vuf_map,
        weights_json=data.weights
    )
    db.add(config)
    db.flush()  # Para obter o ID

    # Adicionar itens do banco de preços
    if data.banco_precos:
        for item in data.banco_precos:
            bp = ProjectBankPrice(
                config_version_id=config.id,
                codigo=item.codigo,
                material=item.material,
                caracteristicas=item.caracteristicas,
                vl_mercado=item.vl_mercado,
                update_mode=item.update_mode
            )
            db.add(bp)

    db.commit()
    db.refresh(config)

    return config_to_response(config, db)


@router.put("/versions/{version_id}", response_model=ConfigVersionResponse)
def update_config_version(
    project_id: int,
    version_id: int,
    data: ConfigVersionUpdate,
    db: Session = Depends(get_db)
):
    """
    Atualiza uma versão de configuração.
    Se a versão tem cotações vinculadas, cria uma nova versão ao invés de modificar.
    """
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    # Se tem cotações vinculadas, criar nova versão
    has_quotes = len(config.cotacoes) > 0 if config.cotacoes else False

    if has_quotes:
        # Criar nova versão baseada na atual
        return create_config_version(project_id, ConfigVersionCreate(
            descricao_alteracao=data.descricao_alteracao or f"Atualização da versão {config.versao}",
            # Parâmetros de cotação
            numero_cotacoes_por_pesquisa=data.numero_cotacoes_por_pesquisa if data.numero_cotacoes_por_pesquisa is not None else config.numero_cotacoes_por_pesquisa,
            variacao_maxima_percent=data.variacao_maxima_percent if data.variacao_maxima_percent is not None else (float(config.variacao_maxima_percent) if config.variacao_maxima_percent else None),
            pesquisador_padrao=data.pesquisador_padrao or config.pesquisador_padrao,
            local_padrao=data.local_padrao or config.local_padrao,
            # Parâmetros de busca
            serpapi_location=data.serpapi_location or config.serpapi_location,
            serpapi_gl=data.serpapi_gl or config.serpapi_gl,
            serpapi_hl=data.serpapi_hl or config.serpapi_hl,
            serpapi_num_results=data.serpapi_num_results if data.serpapi_num_results is not None else config.serpapi_num_results,
            search_timeout=data.search_timeout if data.search_timeout is not None else config.search_timeout,
            max_sources=data.max_sources if data.max_sources is not None else config.max_sources,
            banco_precos=data.banco_precos,
            ec_map=data.ec_map or config.ec_map_json,
            pu_map=data.pu_map or config.pu_map_json,
            vuf_map=data.vuf_map or config.vuf_map_json,
            weights=data.weights or config.weights_json
        ), db)

    # Atualizar versão existente
    if data.descricao_alteracao is not None:
        config.descricao_alteracao = data.descricao_alteracao
    # Parâmetros de cotação
    if data.numero_cotacoes_por_pesquisa is not None:
        config.numero_cotacoes_por_pesquisa = data.numero_cotacoes_por_pesquisa
    if data.variacao_maxima_percent is not None:
        config.variacao_maxima_percent = data.variacao_maxima_percent
    if data.pesquisador_padrao is not None:
        config.pesquisador_padrao = data.pesquisador_padrao
    if data.local_padrao is not None:
        config.local_padrao = data.local_padrao
    # Parâmetros de busca
    if data.serpapi_location is not None:
        config.serpapi_location = data.serpapi_location
    if data.serpapi_gl is not None:
        config.serpapi_gl = data.serpapi_gl
    if data.serpapi_hl is not None:
        config.serpapi_hl = data.serpapi_hl
    if data.serpapi_num_results is not None:
        config.serpapi_num_results = data.serpapi_num_results
    if data.search_timeout is not None:
        config.search_timeout = data.search_timeout
    if data.max_sources is not None:
        config.max_sources = data.max_sources
    if data.ec_map is not None:
        config.ec_map_json = data.ec_map
    if data.pu_map is not None:
        config.pu_map_json = data.pu_map
    if data.vuf_map is not None:
        config.vuf_map_json = data.vuf_map
    if data.weights is not None:
        config.weights_json = data.weights

    # Atualizar banco de preços
    if data.banco_precos is not None:
        # Remover itens antigos
        db.query(ProjectBankPrice).filter(
            ProjectBankPrice.config_version_id == config.id
        ).delete()

        # Adicionar novos itens
        for item in data.banco_precos:
            bp = ProjectBankPrice(
                config_version_id=config.id,
                codigo=item.codigo,
                material=item.material,
                caracteristicas=item.caracteristicas,
                vl_mercado=item.vl_mercado,
                update_mode=item.update_mode
            )
            db.add(bp)

    db.commit()
    db.refresh(config)

    return config_to_response(config, db)


@router.post("/versions/{version_id}/activate", response_model=ConfigVersionResponse)
def activate_config_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Ativa uma versão específica de configuração"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    # Desativar todas as outras versões
    db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.project_id == project_id,
        ProjectConfigVersion.id != version_id
    ).update({"ativo": False})

    # Ativar esta versão
    config.ativo = True
    db.commit()
    db.refresh(config)

    return config_to_response(config, db)


@router.delete("/versions/{version_id}")
def delete_config_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Remove uma versão de configuração (se não tiver cotações vinculadas)"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    # Verificar se tem cotações vinculadas
    if config.cotacoes and len(config.cotacoes) > 0:
        raise HTTPException(
            status_code=400,
            detail="Não é possível remover versão com cotações vinculadas"
        )

    # Remover itens do banco de preços
    db.query(ProjectBankPrice).filter(
        ProjectBankPrice.config_version_id == config.id
    ).delete()

    # Remover versão
    db.delete(config)
    db.commit()

    return {"message": "Versão de configuração removida"}


# ==================== BANK PRICE ENDPOINTS ====================

@router.get("/versions/{version_id}/bank-prices", response_model=List[BankPriceResponse])
def list_bank_prices(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Lista itens do banco de preços de uma versão"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    prices = db.query(ProjectBankPrice).filter(
        ProjectBankPrice.config_version_id == version_id
    ).all()

    return [
        BankPriceResponse(
            id=bp.id,
            codigo=bp.codigo,
            material=bp.material,
            caracteristicas=bp.caracteristicas,
            vl_mercado=float(bp.vl_mercado) if bp.vl_mercado else None,
            update_mode=bp.update_mode
        ) for bp in prices
    ]


@router.post("/versions/{version_id}/bank-prices", response_model=BankPriceResponse)
def add_bank_price(
    project_id: int,
    version_id: int,
    data: BankPriceItem,
    db: Session = Depends(get_db)
):
    """Adiciona um item ao banco de preços"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    # Verificar se tem cotações vinculadas
    if config.cotacoes and len(config.cotacoes) > 0:
        raise HTTPException(
            status_code=400,
            detail="Não é possível modificar versão com cotações. Crie uma nova versão."
        )

    bp = ProjectBankPrice(
        config_version_id=version_id,
        codigo=data.codigo,
        material=data.material,
        caracteristicas=data.caracteristicas,
        vl_mercado=data.vl_mercado,
        update_mode=data.update_mode
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)

    return BankPriceResponse(
        id=bp.id,
        codigo=bp.codigo,
        material=bp.material,
        caracteristicas=bp.caracteristicas,
        vl_mercado=float(bp.vl_mercado) if bp.vl_mercado else None,
        update_mode=bp.update_mode
    )


@router.delete("/versions/{version_id}/bank-prices/{price_id}")
def delete_bank_price(
    project_id: int,
    version_id: int,
    price_id: int,
    db: Session = Depends(get_db)
):
    """Remove um item do banco de preços"""
    get_project_or_404(project_id, db)

    config = db.query(ProjectConfigVersion).filter(
        ProjectConfigVersion.id == version_id,
        ProjectConfigVersion.project_id == project_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Versão de configuração não encontrada")

    # Verificar se tem cotações vinculadas
    if config.cotacoes and len(config.cotacoes) > 0:
        raise HTTPException(
            status_code=400,
            detail="Não é possível modificar versão com cotações. Crie uma nova versão."
        )

    bp = db.query(ProjectBankPrice).filter(
        ProjectBankPrice.id == price_id,
        ProjectBankPrice.config_version_id == version_id
    ).first()

    if not bp:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    db.delete(bp)
    db.commit()

    return {"message": "Item removido"}
