from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import anthropic
import logging

from app.core.database import get_db
from app.models import BlockedDomain
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["blocked-domains"])


class BlockedDomainCreate(BaseModel):
    domain: str
    display_name: str | None = None
    reason: str | None = None


class BlockedDomainUpdate(BaseModel):
    domain: str | None = None
    display_name: str | None = None
    reason: str | None = None


class BlockedDomainResponse(BaseModel):
    id: int
    domain: str
    display_name: Optional[str]
    reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class GenerateNameRequest(BaseModel):
    domain: str


class GenerateNameResponse(BaseModel):
    domain: str
    display_name: str


def generate_display_name_from_domain(domain: str) -> str:
    """Gera um display_name a partir do domínio usando Anthropic Claude"""
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""Dado o domínio "{domain}", gere um nome de exibição apropriado para este site.

Exemplos:
- mercadolivre.com.br → Mercado Livre
- amazon.com.br → Amazon Brasil
- casasbahia.com.br → Casas Bahia
- magazineluiza.com.br → Magazine Luiza

Retorne APENAS o nome de exibição, sem explicações adicionais."""

        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        display_name = response.content[0].text.strip()
        logger.info(f"Generated display name for {domain}: {display_name}")
        return display_name

    except Exception as e:
        logger.error(f"Error generating display name for {domain}: {e}")
        # Fallback: capitalizar domínio sem TLD
        fallback = domain.split('.')[0].capitalize()
        return fallback


@router.get("/blocked-domains", response_model=List[BlockedDomainResponse])
def list_blocked_domains(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Lista todos os domínios bloqueados"""
    domains = db.query(BlockedDomain).order_by(BlockedDomain.domain).offset(skip).limit(limit).all()
    return domains


@router.get("/blocked-domains/{domain_id}", response_model=BlockedDomainResponse)
def get_blocked_domain(
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Obtém um domínio bloqueado específico"""
    domain = db.query(BlockedDomain).filter(BlockedDomain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domínio bloqueado não encontrado")
    return domain


@router.post("/blocked-domains", response_model=BlockedDomainResponse)
def create_blocked_domain(
    domain_data: BlockedDomainCreate,
    db: Session = Depends(get_db)
):
    """Cria um novo domínio bloqueado"""
    # Verificar se domínio já existe
    existing = db.query(BlockedDomain).filter(BlockedDomain.domain == domain_data.domain).first()
    if existing:
        raise HTTPException(status_code=400, detail="Domínio já existe na lista de bloqueados")

    # Gerar display_name automaticamente se não fornecido
    display_name = domain_data.display_name
    if not display_name:
        display_name = generate_display_name_from_domain(domain_data.domain)

    # Criar novo domínio bloqueado
    new_domain = BlockedDomain(
        domain=domain_data.domain,
        display_name=display_name,
        reason=domain_data.reason
    )

    db.add(new_domain)
    db.commit()
    db.refresh(new_domain)

    logger.info(f"Created blocked domain: {new_domain.domain} ({new_domain.display_name})")
    return new_domain


@router.put("/blocked-domains/{domain_id}", response_model=BlockedDomainResponse)
def update_blocked_domain(
    domain_id: int,
    domain_data: BlockedDomainUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza um domínio bloqueado existente"""
    domain = db.query(BlockedDomain).filter(BlockedDomain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domínio bloqueado não encontrado")

    # Verificar se novo domínio já existe (se estiver mudando o domínio)
    if domain_data.domain and domain_data.domain != domain.domain:
        existing = db.query(BlockedDomain).filter(BlockedDomain.domain == domain_data.domain).first()
        if existing:
            raise HTTPException(status_code=400, detail="Domínio já existe na lista de bloqueados")
        domain.domain = domain_data.domain

    # Atualizar campos
    if domain_data.display_name is not None:
        domain.display_name = domain_data.display_name

    if domain_data.reason is not None:
        domain.reason = domain_data.reason

    db.commit()
    db.refresh(domain)

    logger.info(f"Updated blocked domain: {domain.domain}")
    return domain


@router.delete("/blocked-domains/{domain_id}")
def delete_blocked_domain(
    domain_id: int,
    db: Session = Depends(get_db)
):
    """Deleta um domínio bloqueado"""
    domain = db.query(BlockedDomain).filter(BlockedDomain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domínio bloqueado não encontrado")

    domain_name = domain.domain
    db.delete(domain)
    db.commit()

    logger.info(f"Deleted blocked domain: {domain_name}")
    return {"message": "Domínio bloqueado removido com sucesso"}


@router.post("/blocked-domains/generate-name", response_model=GenerateNameResponse)
def generate_name(request: GenerateNameRequest):
    """Gera um display_name a partir de um domínio usando Anthropic"""
    display_name = generate_display_name_from_domain(request.domain)
    return GenerateNameResponse(domain=request.domain, display_name=display_name)
