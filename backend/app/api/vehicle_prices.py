from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional, Literal
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import logging

from app.core.database import get_db
from app.models import VehiclePriceBank, Setting
from app.services.fipe_client import FipeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vehicle-prices", tags=["vehicle-prices"])


def _get_vigencia_meses(db: Session) -> int:
    """Retorna o parametro de vigencia de cotacao em meses (default: 6)"""
    setting = db.query(Setting).filter(Setting.key == "parameters").first()
    if setting and setting.value_json:
        return setting.value_json.get("vigencia_cotacao_veiculos", 6)
    return 6


def _calculate_status(updated_at: datetime, vigencia_meses: int) -> str:
    """Calcula o status da cotacao baseado na vigencia"""
    if updated_at is None:
        return "Expirada"

    # Normalizar para datetime sem timezone para comparacao
    if updated_at.tzinfo is not None:
        updated_at = updated_at.replace(tzinfo=None)

    limite = datetime.now() - relativedelta(months=vigencia_meses)
    return "Vigente" if updated_at >= limite else "Expirada"


# ============= Schemas =============

class VehiclePriceResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime

    # Identificadores FIPE
    codigo_fipe: str
    brand_id: int
    brand_name: str
    model_id: int
    model_name: str
    year_id: str
    year_model: int
    fuel_type: str
    fuel_code: int

    # Dados do Veículo
    vehicle_type: str
    vehicle_name: str

    # Preço e Referência
    price_value: Decimal
    reference_month: str
    reference_date: date

    # Status de vigência (calculado)
    status: str = "Vigente"  # "Vigente" ou "Expirada"

    # Rastreabilidade
    quote_request_id: Optional[int] = None
    last_api_call: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class VehiclePriceListResponse(BaseModel):
    items: List[VehiclePriceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RefreshPriceResponse(BaseModel):
    success: bool
    message: str
    vehicle: Optional[VehiclePriceResponse] = None
    new_price: Optional[Decimal] = None
    old_price: Optional[Decimal] = None
    reference_month: Optional[str] = None


class BulkRefreshResponse(BaseModel):
    total: int
    success_count: int
    error_count: int
    errors: List[str] = []


# ============= Endpoints =============

@router.get("", response_model=VehiclePriceListResponse)
def list_vehicle_prices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_name: Optional[str] = None,
    model_name: Optional[str] = None,
    year_model: Optional[int] = None,
    codigo_fipe: Optional[str] = None,
    reference_month: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    status: Optional[str] = Query(None, regex="^(Vigente|Expirada)$"),
    sort_by: str = Query("updated_at", regex="^(updated_at|price_value|brand_name|year_model|codigo_fipe)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """
    Lista todos os veículos no banco de preços com filtros e paginação.

    Filtros disponíveis:
    - brand_name: Filtro parcial por nome da marca
    - model_name: Filtro parcial por nome do modelo
    - year_model: Ano exato do modelo
    - codigo_fipe: Código FIPE exato
    - reference_month: Mês de referência (ex: "dezembro de 2024")
    - vehicle_type: Tipo de veículo (cars, motorcycles, trucks)
    - status: Status de vigência (Vigente ou Expirada)
    """
    # Obter vigencia para calculo de status
    vigencia_meses = _get_vigencia_meses(db)

    query = db.query(VehiclePriceBank)

    # Aplicar filtros
    if brand_name:
        query = query.filter(VehiclePriceBank.brand_name.ilike(f"%{brand_name}%"))

    if model_name:
        query = query.filter(VehiclePriceBank.model_name.ilike(f"%{model_name}%"))

    if year_model:
        query = query.filter(VehiclePriceBank.year_model == year_model)

    if codigo_fipe:
        query = query.filter(VehiclePriceBank.codigo_fipe == codigo_fipe)

    if reference_month:
        query = query.filter(VehiclePriceBank.reference_month.ilike(f"%{reference_month}%"))

    if vehicle_type:
        query = query.filter(VehiclePriceBank.vehicle_type == vehicle_type)

    # Filtro por status (calculado baseado em vigencia)
    if status:
        from sqlalchemy import func
        limite = datetime.now() - relativedelta(months=vigencia_meses)
        if status == "Vigente":
            query = query.filter(VehiclePriceBank.updated_at >= limite)
        else:  # Expirada
            query = query.filter(VehiclePriceBank.updated_at < limite)

    # Contagem total
    total = query.count()

    # Ordenação
    sort_column = getattr(VehiclePriceBank, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    # Paginação
    offset = (page - 1) * page_size
    db_items = query.offset(offset).limit(page_size).all()

    # Converter para response com status calculado
    items = []
    for item in db_items:
        item_dict = {
            "id": item.id,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "codigo_fipe": item.codigo_fipe,
            "brand_id": item.brand_id,
            "brand_name": item.brand_name,
            "model_id": item.model_id,
            "model_name": item.model_name,
            "year_id": item.year_id,
            "year_model": item.year_model,
            "fuel_type": item.fuel_type,
            "fuel_code": item.fuel_code,
            "vehicle_type": item.vehicle_type,
            "vehicle_name": item.vehicle_name,
            "price_value": item.price_value,
            "reference_month": item.reference_month,
            "reference_date": item.reference_date,
            "status": _calculate_status(item.updated_at, vigencia_meses),
            "quote_request_id": item.quote_request_id,
            "last_api_call": item.last_api_call
        }
        items.append(VehiclePriceResponse(**item_dict))

    total_pages = (total + page_size - 1) // page_size

    return VehiclePriceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{vehicle_id}", response_model=VehiclePriceResponse)
def get_vehicle_price(
    vehicle_id: int,
    db: Session = Depends(get_db)
):
    """Obtém um veículo específico do banco de preços"""
    vehicle = db.query(VehiclePriceBank).filter(VehiclePriceBank.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado no banco de preços")

    vigencia_meses = _get_vigencia_meses(db)
    return VehiclePriceResponse(
        id=vehicle.id,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
        codigo_fipe=vehicle.codigo_fipe,
        brand_id=vehicle.brand_id,
        brand_name=vehicle.brand_name,
        model_id=vehicle.model_id,
        model_name=vehicle.model_name,
        year_id=vehicle.year_id,
        year_model=vehicle.year_model,
        fuel_type=vehicle.fuel_type,
        fuel_code=vehicle.fuel_code,
        vehicle_type=vehicle.vehicle_type,
        vehicle_name=vehicle.vehicle_name,
        price_value=vehicle.price_value,
        reference_month=vehicle.reference_month,
        reference_date=vehicle.reference_date,
        status=_calculate_status(vehicle.updated_at, vigencia_meses),
        quote_request_id=vehicle.quote_request_id,
        last_api_call=vehicle.last_api_call
    )


@router.post("/{vehicle_id}/refresh", response_model=RefreshPriceResponse)
async def refresh_vehicle_price(
    vehicle_id: int,
    db: Session = Depends(get_db)
):
    """
    Atualiza o preço de um veículo específico consultando a API FIPE.

    Faz uma nova chamada à API FIPE usando os IDs já conhecidos
    (brand_id, model_id, year_id) e atualiza o registro no banco.
    """
    vehicle = db.query(VehiclePriceBank).filter(VehiclePriceBank.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado no banco de preços")

    old_price = vehicle.price_value
    old_reference = vehicle.reference_month

    try:
        fipe_client = FipeClient()
        result = await fipe_client.refresh_price(
            vehicle_type=vehicle.vehicle_type,
            brand_id=str(vehicle.brand_id),
            model_id=str(vehicle.model_id),
            year_id=vehicle.year_id
        )

        if not result.success:
            return RefreshPriceResponse(
                success=False,
                message=f"Falha ao atualizar preço: {result.error_message}"
            )

        # Atualizar registro
        price_data = result.price

        # Extrair valor numérico do preço
        price_str = price_data.price.replace("R$", "").replace(".", "").replace(",", ".").strip()
        new_price = Decimal(price_str)

        # Converter referenceMonth para date (ex: "dezembro de 2024" -> 2024-12-01)
        ref_date = _parse_reference_month(price_data.referenceMonth)

        vehicle.price_value = new_price
        vehicle.reference_month = price_data.referenceMonth
        vehicle.reference_date = ref_date
        vehicle.last_api_call = datetime.utcnow()
        vehicle.api_response_json = {
            "price": price_data.price,
            "brand": price_data.brand,
            "model": price_data.model,
            "modelYear": price_data.modelYear,
            "fuel": price_data.fuel,
            "codeFipe": price_data.codeFipe,
            "referenceMonth": price_data.referenceMonth,
            "vehicleType": price_data.vehicleType
        }

        db.commit()
        db.refresh(vehicle)

        logger.info(f"Preço atualizado: {vehicle.vehicle_name} de R$ {old_price} para R$ {new_price}")

        return RefreshPriceResponse(
            success=True,
            message=f"Preço atualizado com sucesso. Referência: {price_data.referenceMonth}",
            vehicle=vehicle,
            new_price=new_price,
            old_price=old_price,
            reference_month=price_data.referenceMonth
        )

    except Exception as e:
        logger.error(f"Erro ao atualizar preço do veículo {vehicle_id}: {e}")
        return RefreshPriceResponse(
            success=False,
            message=f"Erro ao consultar API FIPE: {str(e)}"
        )


@router.post("/refresh-all", response_model=BulkRefreshResponse)
async def refresh_all_prices(
    vehicle_type: Optional[str] = None,
    brand_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Atualiza o preço de todos os veículos (ou filtrados) no banco de preços.

    ATENÇÃO: Esta operação pode demorar e consumir muitas chamadas API.
    Recomenda-se usar filtros para limitar o escopo.
    """
    query = db.query(VehiclePriceBank)

    if vehicle_type:
        query = query.filter(VehiclePriceBank.vehicle_type == vehicle_type)

    if brand_name:
        query = query.filter(VehiclePriceBank.brand_name.ilike(f"%{brand_name}%"))

    vehicles = query.all()
    total = len(vehicles)

    if total == 0:
        return BulkRefreshResponse(
            total=0,
            success_count=0,
            error_count=0
        )

    if total > 50:
        raise HTTPException(
            status_code=400,
            detail=f"Muitos veículos para atualizar ({total}). Use filtros para reduzir para no máximo 50."
        )

    success_count = 0
    error_count = 0
    errors = []

    fipe_client = FipeClient()

    for vehicle in vehicles:
        try:
            result = await fipe_client.refresh_price(
                vehicle_type=vehicle.vehicle_type,
                brand_id=str(vehicle.brand_id),
                model_id=str(vehicle.model_id),
                year_id=vehicle.year_id
            )

            if result.success:
                price_data = result.price
                price_str = price_data.price.replace("R$", "").replace(".", "").replace(",", ".").strip()
                new_price = Decimal(price_str)
                ref_date = _parse_reference_month(price_data.referenceMonth)

                vehicle.price_value = new_price
                vehicle.reference_month = price_data.referenceMonth
                vehicle.reference_date = ref_date
                vehicle.last_api_call = datetime.utcnow()
                vehicle.api_response_json = {
                    "price": price_data.price,
                    "brand": price_data.brand,
                    "model": price_data.model,
                    "modelYear": price_data.modelYear,
                    "fuel": price_data.fuel,
                    "codeFipe": price_data.codeFipe,
                    "referenceMonth": price_data.referenceMonth,
                    "vehicleType": price_data.vehicleType
                }
                success_count += 1
            else:
                error_count += 1
                errors.append(f"{vehicle.vehicle_name}: {result.error_message}")

        except Exception as e:
            error_count += 1
            errors.append(f"{vehicle.vehicle_name}: {str(e)}")

    db.commit()

    logger.info(f"Atualização em lote: {success_count}/{total} veículos atualizados, {error_count} erros")

    return BulkRefreshResponse(
        total=total,
        success_count=success_count,
        error_count=error_count,
        errors=errors[:10]  # Limitar a 10 erros no response
    )


@router.get("/filters/brands", response_model=List[str])
def get_available_brands(db: Session = Depends(get_db)):
    """Lista todas as marcas disponíveis no banco de preços"""
    brands = db.query(VehiclePriceBank.brand_name).distinct().order_by(VehiclePriceBank.brand_name).all()
    return [b[0] for b in brands]


@router.get("/filters/years", response_model=List[int])
def get_available_years(db: Session = Depends(get_db)):
    """Lista todos os anos disponíveis no banco de preços"""
    years = db.query(VehiclePriceBank.year_model).distinct().order_by(desc(VehiclePriceBank.year_model)).all()
    return [y[0] for y in years]


@router.get("/filters/reference-months", response_model=List[str])
def get_available_reference_months(db: Session = Depends(get_db)):
    """Lista todos os meses de referência disponíveis no banco de preços"""
    months = db.query(VehiclePriceBank.reference_month).distinct().order_by(desc(VehiclePriceBank.reference_date)).all()
    return [m[0] for m in months]


# ============= Helpers =============

def _parse_reference_month(reference_month: str) -> date:
    """
    Converte string de mês de referência para date.
    Ex: "dezembro de 2024" -> date(2024, 12, 1)
    """
    months_map = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12
    }

    try:
        parts = reference_month.lower().replace(" de ", " ").split()
        month_name = parts[0]
        year = int(parts[1])
        month = months_map.get(month_name, 1)
        return date(year, month, 1)
    except Exception:
        return date.today().replace(day=1)
