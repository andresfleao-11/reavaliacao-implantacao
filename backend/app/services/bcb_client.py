"""
Cliente para API do Banco Central do Brasil (BCB) - PTAX
Busca taxa de câmbio USD -> BRL
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

BCB_PTAX_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"


class BCBClient:
    """Cliente para buscar cotação do dólar na API PTAX do Banco Central"""

    def __init__(self):
        self.base_url = BCB_PTAX_BASE_URL

    async def get_exchange_rate(self, date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Busca a cotação do dólar (PTAX) para uma data específica.
        Se não informar data, busca a cotação mais recente disponível.

        Args:
            date: Data da cotação (opcional). Se não informada, tenta hoje e dias anteriores.

        Returns:
            Dict com rate (taxa de venda), date (data da cotação), raw_response
        """
        # Se não informou data, tenta hoje e até 5 dias úteis anteriores
        if date is None:
            for days_back in range(6):
                check_date = datetime.now() - timedelta(days=days_back)
                result = await self._fetch_rate_for_date(check_date)
                if result:
                    return result
            logger.warning("Não foi possível obter cotação do BCB para os últimos 6 dias")
            return None
        else:
            return await self._fetch_rate_for_date(date)

    async def _fetch_rate_for_date(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Busca cotação para uma data específica"""
        # Formato da data: MM-DD-YYYY
        date_str = date.strftime("%m-%d-%Y")

        url = f"{self.base_url}/CotacaoDolarDia(dataCotacao=@dataCotacao)"
        params = {
            "@dataCotacao": f"'{date_str}'",
            "$format": "json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # A resposta vem em data["value"] que é uma lista
                values = data.get("value", [])

                if not values:
                    logger.debug(f"Sem cotação disponível para {date_str}")
                    return None

                # Pega a última cotação do dia (cotação de fechamento)
                last_quote = values[-1]

                # cotacaoVenda = taxa de venda (USD -> BRL)
                rate = last_quote.get("cotacaoVenda")
                quote_date = last_quote.get("dataHoraCotacao")

                if rate:
                    logger.info(f"Cotação BCB obtida: USD 1 = BRL {rate} (data: {quote_date})")
                    return {
                        "rate": float(rate),
                        "date": quote_date,
                        "date_requested": date_str,
                        "raw_response": last_quote
                    }

                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao buscar cotação BCB: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Erro de conexão com BCB: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar cotação BCB: {str(e)}")
            return None


async def fetch_current_exchange_rate() -> Optional[Dict[str, Any]]:
    """
    Função auxiliar para buscar a cotação atual do dólar.
    Retorna dict com 'rate' e 'date' ou None se falhar.
    """
    client = BCBClient()
    return await client.get_exchange_rate()


# Para uso síncrono (em tasks Celery)
def fetch_exchange_rate_sync() -> Optional[Dict[str, Any]]:
    """Versão síncrona para uso em tasks Celery"""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(fetch_current_exchange_rate())
