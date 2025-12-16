from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import get_db
from app.core.auth import get_current_user, get_current_admin_user
from app.models import Setting, BankPrice, RevaluationParam, IntegrationSetting, User
from app.utils.cache import config_cache, cached_function, invalidate_cache
from app.api.schemas import (
    ParametersResponse,
    ParametersUpdateRequest,
    BankPriceResponse,
    BankPriceCreateRequest,
    BankPriceUpdateRequest,
    RevaluationParamsResponse,
    RevaluationParamsUpdateRequest,
    IntegrationSettingResponse,
    IntegrationSettingUpdateRequest,
    IntegrationTestResponse,
    SERPAPI_BRAZIL_LOCATIONS,
    SerpApiLocationOption,
    ANTHROPIC_MODELS,
    AnthropicModelOption,
    OPENAI_MODELS,
    OpenAIModelOption,
    AI_PROVIDERS,
    AIProviderOption
)
from app.core.security import encrypt_value, decrypt_value, mask_api_key
from typing import List
import httpx
import anthropic
import openai

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/serpapi-locations", response_model=List[SerpApiLocationOption])
def get_serpapi_locations():
    """Return available SerpAPI locations for Brazil"""
    return [SerpApiLocationOption(**loc) for loc in SERPAPI_BRAZIL_LOCATIONS]


@router.get("/anthropic-models", response_model=List[AnthropicModelOption])
def get_anthropic_models():
    """Return available Anthropic Claude models"""
    return [AnthropicModelOption(**model) for model in ANTHROPIC_MODELS]


@router.get("/openai-models", response_model=List[OpenAIModelOption])
def get_openai_models():
    """Return available OpenAI GPT models"""
    return [OpenAIModelOption(**model) for model in OPENAI_MODELS]


@router.get("/ai-providers", response_model=List[AIProviderOption])
def get_ai_providers():
    """Return available AI providers"""
    return [AIProviderOption(**provider) for provider in AI_PROVIDERS]


@router.get("/parameters", response_model=ParametersResponse)
@cached_function(config_cache, key_func=lambda db: "parameters")
def get_parameters(db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == "parameters").first()

    defaults = {
        "numero_cotacoes_por_pesquisa": 3,
        "variacao_maxima_percent": 25.0,
        "pesquisador_padrao": "Sistema",
        "local_padrao": "Online",
        "serpapi_location": "Sao Paulo,State of Sao Paulo,Brazil"  # Use city-level for better results
    }

    if not setting:
        setting = Setting(key="parameters", value_json=defaults)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    else:
        # Ensure new fields have defaults if missing
        current = dict(setting.value_json)  # Make a copy to ensure change detection
        updated = False
        for key, value in defaults.items():
            if key not in current:
                current[key] = value
                updated = True
        if updated:
            setting.value_json = current
            flag_modified(setting, "value_json")
            db.commit()
            db.refresh(setting)

    return ParametersResponse(**setting.value_json)


@router.put("/parameters", response_model=ParametersResponse)
def update_parameters(
    params: ParametersUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    setting = db.query(Setting).filter(Setting.key == "parameters").first()

    if not setting:
        setting = Setting(key="parameters", value_json={})
        db.add(setting)

    current_values = dict(setting.value_json)  # Make a copy to ensure change detection

    update_data = params.dict(exclude_unset=True)
    current_values.update(update_data)

    setting.value_json = current_values
    flag_modified(setting, "value_json")
    db.commit()
    db.refresh(setting)

    # Invalidar cache após atualização
    invalidate_cache(config_cache, "parameters")

    return ParametersResponse(**setting.value_json)


@router.get("/bank-prices", response_model=List[BankPriceResponse])
def list_bank_prices(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(BankPrice)

    if search:
        query = query.filter(
            (BankPrice.codigo.ilike(f"%{search}%")) |
            (BankPrice.material.ilike(f"%{search}%"))
        )

    prices = query.offset(skip).limit(limit).all()
    return prices


@router.post("/bank-prices", response_model=BankPriceResponse)
def create_bank_price(
    price: BankPriceCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    existing = db.query(BankPrice).filter(BankPrice.codigo == price.codigo).first()
    if existing:
        raise HTTPException(status_code=400, detail="Código already exists")

    bank_price = BankPrice(**price.dict())
    db.add(bank_price)
    db.commit()
    db.refresh(bank_price)
    return bank_price


@router.put("/bank-prices/{codigo}", response_model=BankPriceResponse)
def update_bank_price(
    codigo: str,
    price: BankPriceUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    bank_price = db.query(BankPrice).filter(BankPrice.codigo == codigo).first()

    if not bank_price:
        raise HTTPException(status_code=404, detail="Bank price not found")

    update_data = price.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bank_price, field, value)

    db.commit()
    db.refresh(bank_price)
    return bank_price


@router.delete("/bank-prices/{codigo}")
def delete_bank_price(
    codigo: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    bank_price = db.query(BankPrice).filter(BankPrice.codigo == codigo).first()

    if not bank_price:
        raise HTTPException(status_code=404, detail="Bank price not found")

    db.delete(bank_price)
    db.commit()
    return {"message": "Bank price deleted successfully"}


@router.get("/revaluation", response_model=RevaluationParamsResponse)
def get_revaluation_params(db: Session = Depends(get_db)):
    param = db.query(RevaluationParam).first()

    if not param:
        defaults = {
            "ec_map": {"BOM": 8.0, "REGULAR": 5.0, "RUIM": 2.0},
            "pu_map": {"1": 10.0, "2": 9.0, "3": 8.0, "4": 7.0, "5": 6.0, "6": 5.0, "7": 4.0, "8": 3.0, "9": 2.0, "10": 1.0},
            "vuf_map": {"1": 10.0, "2": 9.0, "3": 8.0, "4": 7.0, "5": 6.0, "6": 5.0, "7": 4.0, "8": 3.0, "9": 2.0, "10": 1.0},
            "weights": {"EC": 4.0, "PU": 6.0, "VUF": -3.0}
        }
        param = RevaluationParam(
            ec_map_json=defaults["ec_map"],
            pu_map_json=defaults["pu_map"],
            vuf_map_json=defaults["vuf_map"],
            weights_json=defaults["weights"]
        )
        db.add(param)
        db.commit()
        db.refresh(param)

    return RevaluationParamsResponse(
        ec_map=param.ec_map_json,
        pu_map=param.pu_map_json,
        vuf_map=param.vuf_map_json,
        weights=param.weights_json
    )


@router.put("/revaluation", response_model=RevaluationParamsResponse)
def update_revaluation_params(
    params: RevaluationParamsUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    param = db.query(RevaluationParam).first()

    if not param:
        param = RevaluationParam(
            ec_map_json={},
            pu_map_json={},
            vuf_map_json={},
            weights_json={}
        )
        db.add(param)

    if params.ec_map is not None:
        param.ec_map_json = params.ec_map
    if params.pu_map is not None:
        param.pu_map_json = params.pu_map
    if params.vuf_map is not None:
        param.vuf_map_json = params.vuf_map
    if params.weights is not None:
        param.weights_json = params.weights

    db.commit()
    db.refresh(param)

    return RevaluationParamsResponse(
        ec_map=param.ec_map_json,
        pu_map=param.pu_map_json,
        vuf_map=param.vuf_map_json,
        weights=param.weights_json
    )


@router.get("/integrations/{provider}", response_model=IntegrationSettingResponse)
def get_integration_setting(provider: str, db: Session = Depends(get_db)):
    from app.core.config import settings as app_settings

    provider = provider.upper()

    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()

    # Check environment variables as fallback
    env_key = None
    if provider == "SERPAPI":
        env_key = app_settings.SERPAPI_API_KEY
    elif provider == "ANTHROPIC":
        env_key = app_settings.ANTHROPIC_API_KEY
    elif provider == "OPENAI":
        env_key = app_settings.OPENAI_API_KEY

    if integration and integration.settings_json.get("api_key"):
        api_key_encrypted = integration.settings_json.get("api_key", "")
        api_key_masked = mask_api_key(decrypt_value(api_key_encrypted)) if api_key_encrypted else "Not configured"
        other_settings = {k: v for k, v in integration.settings_json.items() if k != "api_key"}
        return IntegrationSettingResponse(
            provider=provider,
            api_key_masked=api_key_masked,
            other_settings=other_settings,
            is_configured=True,
            source="database"
        )
    elif env_key:
        # Key exists in environment
        return IntegrationSettingResponse(
            provider=provider,
            api_key_masked=mask_api_key(env_key),
            other_settings={},
            is_configured=True,
            source="environment"
        )
    else:
        return IntegrationSettingResponse(
            provider=provider,
            api_key_masked="Not configured",
            other_settings={},
            is_configured=False,
            source=None
        )


@router.put("/integrations/{provider}", response_model=IntegrationSettingResponse)
def update_integration_setting(
    provider: str,
    settings_update: IntegrationSettingUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    provider = provider.upper()

    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()

    if not integration:
        integration = IntegrationSetting(
            provider=provider,
            settings_json={}
        )
        db.add(integration)

    if settings_update.api_key:
        encrypted_key = encrypt_value(settings_update.api_key)
        integration.settings_json["api_key"] = encrypted_key

    if settings_update.other_settings:
        for key, value in settings_update.other_settings.items():
            integration.settings_json[key] = value

    # Marcar o campo JSON como modificado para que o SQLAlchemy detecte a mudança
    flag_modified(integration, "settings_json")

    db.commit()
    db.refresh(integration)

    api_key_masked = mask_api_key(integration.settings_json.get("api_key", ""))
    other_settings = {k: v for k, v in integration.settings_json.items() if k != "api_key"}

    return IntegrationSettingResponse(
        provider=integration.provider,
        api_key_masked=api_key_masked,
        other_settings=other_settings
    )


@router.post("/integrations/{provider}/test", response_model=IntegrationTestResponse)
async def test_integration(provider: str, db: Session = Depends(get_db)):
    from app.core.config import settings as app_settings

    provider = provider.upper()

    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()

    api_key = None

    # First try to get from database
    if integration:
        encrypted_key = integration.settings_json.get("api_key")
        if encrypted_key:
            api_key = decrypt_value(encrypted_key)

    # Fallback to environment variables
    if not api_key:
        if provider == "SERPAPI":
            api_key = app_settings.SERPAPI_API_KEY
        elif provider == "ANTHROPIC":
            api_key = app_settings.ANTHROPIC_API_KEY
        elif provider == "OPENAI":
            api_key = app_settings.OPENAI_API_KEY

    # FIPE API doesn't require API key
    if not api_key and provider not in ["FIPE"]:
        return IntegrationTestResponse(
            success=False,
            message="API key not configured"
        )

    try:
        if provider == "SERPAPI":
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://serpapi.com/search",
                    params={"q": "test", "api_key": api_key, "engine": "google"}
                )
                if response.status_code == 200:
                    return IntegrationTestResponse(success=True, message="SerpAPI connection successful")
                else:
                    return IntegrationTestResponse(success=False, message=f"SerpAPI error: {response.status_code}")

        elif provider == "ANTHROPIC":
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return IntegrationTestResponse(success=True, message="Anthropic API connection successful")

        elif provider == "OPENAI":
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return IntegrationTestResponse(success=True, message="OpenAI API connection successful")

        elif provider == "IMGBB":
            # Test imgbb API by checking account info
            async with httpx.AsyncClient() as client:
                # Just check if the API key format is valid by making a simple request
                response = await client.get(
                    f"https://api.imgbb.com/1/upload?key={api_key}"
                )
                # imgbb returns 400 when no image provided, but validates key
                if response.status_code in [200, 400]:
                    data = response.json()
                    # If key is invalid, it returns error.code 100
                    if data.get("error", {}).get("code") == 100:
                        return IntegrationTestResponse(success=False, message="Invalid imgbb API key")
                    return IntegrationTestResponse(success=True, message="imgbb API key is valid")
                else:
                    return IntegrationTestResponse(success=False, message=f"imgbb error: {response.status_code}")

        elif provider == "FIPE":
            # Test FIPE API by fetching brands (API doesn't require key)
            async with httpx.AsyncClient() as client:
                # Get base URL from settings or use default
                base_url = "https://fipe.parallelum.com.br/api/v2"
                if integration and integration.settings_json:
                    base_url = integration.settings_json.get("base_url", base_url)

                response = await client.get(f"{base_url}/cars/brands")
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        return IntegrationTestResponse(
                            success=True,
                            message=f"API FIPE conectada com sucesso. {len(data)} marcas de carros encontradas."
                        )
                    else:
                        return IntegrationTestResponse(success=False, message="API FIPE retornou dados vazios")
                else:
                    return IntegrationTestResponse(success=False, message=f"Erro na API FIPE: {response.status_code}")

        else:
            return IntegrationTestResponse(success=False, message="Unknown provider")

    except Exception as e:
        return IntegrationTestResponse(success=False, message=f"Connection failed: {str(e)}")


@router.get("/cost-config")
def get_cost_config(db: Session = Depends(get_db)):
    """Retorna configurações de custo (SerpAPI e taxa de câmbio)"""
    setting = db.query(Setting).filter(Setting.key == "cost_config").first()

    defaults = {
        "serpapi_cost_per_call": None,
        "usd_to_brl_rate": None,
        "updated_at": None
    }

    if setting and setting.value_json:
        return setting.value_json
    return defaults


@router.put("/cost-config")
def update_cost_config(
    config: dict,
    db: Session = Depends(get_db)
):
    """Atualiza configurações de custo"""
    from datetime import datetime

    setting = db.query(Setting).filter(Setting.key == "cost_config").first()

    if not setting:
        setting = Setting(key="cost_config", value_json={})
        db.add(setting)

    current = dict(setting.value_json) if setting.value_json else {}

    if "serpapi_cost_per_call" in config:
        current["serpapi_cost_per_call"] = config["serpapi_cost_per_call"]
        current["serpapi_updated_at"] = datetime.now().isoformat()

    if "usd_to_brl_rate" in config:
        current["usd_to_brl_rate"] = config["usd_to_brl_rate"]
        current["exchange_updated_at"] = datetime.now().isoformat()

    setting.value_json = current
    flag_modified(setting, "value_json")
    db.commit()
    db.refresh(setting)

    return setting.value_json
