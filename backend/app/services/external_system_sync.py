"""
Serviço de Sincronização com Sistemas Externos (ASI)
Responsável por baixar dados mestres (UGs, ULs, características, etc.)
"""
import httpx
import json
import logging
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    ExternalSystem,
    InventoryMasterUG,
    InventoryMasterUL,
    InventoryMasterUA,
    InventoryMasterPhysicalStatus,
    InventoryMasterCharacteristic,
    InventoryMasterSyncLog,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class ExternalSystemSyncService:
    """Serviço para sincronização de dados com sistemas externos"""

    def __init__(self, db: Session, system: ExternalSystem):
        self.db = db
        self.system = system
        self.base_url = system.full_url or self._build_url()

    def _build_url(self) -> str:
        """Monta URL base do sistema"""
        url = self.system.host.rstrip('/')
        if self.system.port:
            url += f":{self.system.port}"
        if self.system.context_path:
            url += '/' + self.system.context_path.strip('/')
        return url

    def _get_auth_headers(self) -> dict:
        """Monta headers de autenticação"""
        headers = {"Content-Type": "application/json"}

        if self.system.auth_type == "basic":
            if self.system.auth_username and self.system.auth_password_encrypted:
                from app.api.external_systems import decrypt_value
                password = decrypt_value(self.system.auth_password_encrypted)
                if password:
                    credentials = f"{self.system.auth_username}:{password}"
                    encoded = base64.b64encode(credentials.encode()).decode()
                    headers["Authorization"] = f"Basic {encoded}"

        elif self.system.auth_type == "bearer":
            if self.system.auth_token_encrypted:
                from app.api.external_systems import decrypt_value
                token = decrypt_value(self.system.auth_token_encrypted)
                if token:
                    headers["Authorization"] = f"Bearer {token}"

        elif self.system.auth_type == "api_key":
            if self.system.auth_token_encrypted and self.system.auth_header_name:
                from app.api.external_systems import decrypt_value
                token = decrypt_value(self.system.auth_token_encrypted)
                if token:
                    headers[self.system.auth_header_name] = token

        return headers

    def _parse_response(self, response_text: str) -> Any:
        """
        Parse da resposta do servidor ASI.
        O ASI usa double JSON encoding: JSON.stringify(JSON.stringify(obj))
        """
        try:
            if self.system.double_json_encoding:
                # Primeiro parse retorna uma string JSON
                first_parse = json.loads(response_text)
                if isinstance(first_parse, str):
                    # Segundo parse retorna o objeto real
                    return json.loads(first_parse)
                return first_parse
            else:
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse da resposta: {e}")
            # Tentar limpar caracteres especiais e fazer parse novamente
            try:
                cleaned = response_text.replace('\\n', ' ').replace('\\r', ' ')
                return json.loads(cleaned)
            except Exception:
                raise ValueError(f"Resposta inválida do servidor: {response_text[:200]}")

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[dict] = None
    ) -> Any:
        """Faz requisição ao sistema externo"""
        url = self.base_url + endpoint
        headers = self._get_auth_headers()

        async with httpx.AsyncClient(
            verify=False,
            timeout=self.system.timeout_seconds
        ) as client:
            for attempt in range(self.system.retry_attempts):
                try:
                    if method == "GET":
                        response = await client.get(url, headers=headers)
                    else:
                        response = await client.post(url, headers=headers, json=data)

                    if response.status_code == 200:
                        return self._parse_response(response.text)

                    elif response.status_code in (401, 403):
                        raise PermissionError("Falha na autenticação")

                    elif response.status_code == 404:
                        raise FileNotFoundError(f"Endpoint não encontrado: {endpoint}")

                    else:
                        raise Exception(f"Erro HTTP {response.status_code}: {response.text[:200]}")

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    if attempt < self.system.retry_attempts - 1:
                        logger.warning(f"Tentativa {attempt + 1} falhou, tentando novamente...")
                        continue
                    raise ConnectionError(f"Falha na conexão após {self.system.retry_attempts} tentativas: {e}")

    def _create_sync_log(self, sync_type: str) -> InventoryMasterSyncLog:
        """Cria registro de log de sincronização"""
        log = InventoryMasterSyncLog(
            external_system_id=self.system.id,
            sync_type=sync_type,
            status=SyncStatus.RUNNING.value,
            started_at=datetime.utcnow()
        )
        self.db.add(log)
        self.db.commit()
        return log

    def _complete_sync_log(
        self,
        log: InventoryMasterSyncLog,
        status: str,
        items_received: int = 0,
        items_created: int = 0,
        items_updated: int = 0,
        items_failed: int = 0,
        error_message: Optional[str] = None,
        details: Optional[dict] = None
    ):
        """Atualiza log de sincronização"""
        log.status = status
        log.items_received = items_received
        log.items_created = items_created
        log.items_updated = items_updated
        log.items_failed = items_failed
        log.error_message = error_message
        log.details = details
        log.completed_at = datetime.utcnow()
        self.db.commit()

    async def sync_ugs(self) -> Dict[str, int]:
        """Sincroniza Unidades Gestoras"""
        sync_log = self._create_sync_log("ug")

        try:
            # Fazer requisição ao endpoint de UGs
            data = await self._make_request(self.system.endpoint_download_ug)

            # Processar itens
            items = data if isinstance(data, list) else data.get("itens", [])
            items_received = len(items)
            items_created = 0
            items_updated = 0
            items_failed = 0

            for item in items:
                try:
                    code = item.get("C01") or item.get("codigo") or item.get("code")
                    name = item.get("C02") or item.get("nome") or item.get("name")

                    if not code or not name:
                        items_failed += 1
                        continue

                    # Verificar se já existe
                    existing = self.db.query(InventoryMasterUG).filter(
                        InventoryMasterUG.external_system_id == self.system.id,
                        InventoryMasterUG.code == code
                    ).first()

                    if existing:
                        existing.name = name
                        existing.extra_data = item
                        existing.synced_at = datetime.utcnow()
                        items_updated += 1
                    else:
                        ug = InventoryMasterUG(
                            external_system_id=self.system.id,
                            code=code,
                            name=name,
                            extra_data=item
                        )
                        self.db.add(ug)
                        items_created += 1

                except Exception as e:
                    logger.error(f"Erro ao processar UG: {e}")
                    items_failed += 1

            self.db.commit()

            self._complete_sync_log(
                sync_log,
                SyncStatus.SUCCESS.value if items_failed == 0 else SyncStatus.PARTIAL.value,
                items_received=items_received,
                items_created=items_created,
                items_updated=items_updated,
                items_failed=items_failed
            )

            return {
                "received": items_received,
                "created": items_created,
                "updated": items_updated,
                "failed": items_failed
            }

        except Exception as e:
            self._complete_sync_log(
                sync_log,
                SyncStatus.FAILED.value,
                error_message=str(e)
            )
            raise

    async def sync_uls(self) -> Dict[str, int]:
        """Sincroniza Unidades Locais"""
        sync_log = self._create_sync_log("ul")

        try:
            data = await self._make_request(self.system.endpoint_download_ul)

            items = data if isinstance(data, list) else data.get("itens", [])
            items_received = len(items)
            items_created = 0
            items_updated = 0
            items_failed = 0

            for item in items:
                try:
                    code = item.get("C01") or item.get("codigo") or item.get("code")
                    name = item.get("C02") or item.get("nome") or item.get("name")
                    ug_code = item.get("C03") or item.get("ug_code")

                    if not code or not name:
                        items_failed += 1
                        continue

                    # Buscar UG pai
                    ug_id = None
                    if ug_code:
                        ug = self.db.query(InventoryMasterUG).filter(
                            InventoryMasterUG.external_system_id == self.system.id,
                            InventoryMasterUG.code == ug_code
                        ).first()
                        if ug:
                            ug_id = ug.id

                    # Extrair geolocalização se disponível
                    latitude = item.get("latitude") or item.get("lat")
                    longitude = item.get("longitude") or item.get("lng") or item.get("lon")

                    existing = self.db.query(InventoryMasterUL).filter(
                        InventoryMasterUL.external_system_id == self.system.id,
                        InventoryMasterUL.code == code
                    ).first()

                    if existing:
                        existing.name = name
                        existing.ug_id = ug_id
                        existing.latitude = latitude
                        existing.longitude = longitude
                        existing.extra_data = item
                        existing.synced_at = datetime.utcnow()
                        items_updated += 1
                    else:
                        ul = InventoryMasterUL(
                            external_system_id=self.system.id,
                            ug_id=ug_id,
                            code=code,
                            name=name,
                            latitude=latitude,
                            longitude=longitude,
                            extra_data=item
                        )
                        self.db.add(ul)
                        items_created += 1

                except Exception as e:
                    logger.error(f"Erro ao processar UL: {e}")
                    items_failed += 1

            self.db.commit()

            self._complete_sync_log(
                sync_log,
                SyncStatus.SUCCESS.value if items_failed == 0 else SyncStatus.PARTIAL.value,
                items_received=items_received,
                items_created=items_created,
                items_updated=items_updated,
                items_failed=items_failed
            )

            return {
                "received": items_received,
                "created": items_created,
                "updated": items_updated,
                "failed": items_failed
            }

        except Exception as e:
            self._complete_sync_log(
                sync_log,
                SyncStatus.FAILED.value,
                error_message=str(e)
            )
            raise

    async def sync_physical_status(self) -> Dict[str, int]:
        """Sincroniza Situações Físicas"""
        sync_log = self._create_sync_log("physical_status")

        try:
            data = await self._make_request(self.system.endpoint_download_physical_status)

            items = data if isinstance(data, list) else data.get("itens", [])
            items_received = len(items)
            items_created = 0
            items_updated = 0
            items_failed = 0

            for item in items:
                try:
                    code = item.get("C01") or item.get("codigo") or item.get("code")
                    name = item.get("C02") or item.get("nome") or item.get("name")
                    description = item.get("C03") or item.get("descricao") or item.get("description")

                    if not code or not name:
                        items_failed += 1
                        continue

                    existing = self.db.query(InventoryMasterPhysicalStatus).filter(
                        InventoryMasterPhysicalStatus.external_system_id == self.system.id,
                        InventoryMasterPhysicalStatus.code == code
                    ).first()

                    if existing:
                        existing.name = name
                        existing.description = description
                        existing.synced_at = datetime.utcnow()
                        items_updated += 1
                    else:
                        status = InventoryMasterPhysicalStatus(
                            external_system_id=self.system.id,
                            code=code,
                            name=name,
                            description=description
                        )
                        self.db.add(status)
                        items_created += 1

                except Exception as e:
                    logger.error(f"Erro ao processar situação física: {e}")
                    items_failed += 1

            self.db.commit()

            self._complete_sync_log(
                sync_log,
                SyncStatus.SUCCESS.value if items_failed == 0 else SyncStatus.PARTIAL.value,
                items_received=items_received,
                items_created=items_created,
                items_updated=items_updated,
                items_failed=items_failed
            )

            return {
                "received": items_received,
                "created": items_created,
                "updated": items_updated,
                "failed": items_failed
            }

        except Exception as e:
            self._complete_sync_log(
                sync_log,
                SyncStatus.FAILED.value,
                error_message=str(e)
            )
            raise

    async def sync_characteristics(self) -> Dict[str, int]:
        """Sincroniza Características de Bens"""
        sync_log = self._create_sync_log("characteristics")

        try:
            data = await self._make_request(self.system.endpoint_download_characteristics)

            items = data if isinstance(data, list) else data.get("itens", [])
            items_received = len(items)
            items_created = 0
            items_updated = 0
            items_failed = 0

            for item in items:
                try:
                    code = item.get("C01") or item.get("codigo") or item.get("code")
                    name = item.get("C02") or item.get("nome") or item.get("name")
                    char_type = item.get("C03") or item.get("tipo") or item.get("type")
                    required = item.get("obrigatorio") or item.get("required") or False

                    if not code or not name:
                        items_failed += 1
                        continue

                    existing = self.db.query(InventoryMasterCharacteristic).filter(
                        InventoryMasterCharacteristic.external_system_id == self.system.id,
                        InventoryMasterCharacteristic.code == code
                    ).first()

                    if existing:
                        existing.name = name
                        existing.type = char_type
                        existing.required = required
                        existing.synced_at = datetime.utcnow()
                        items_updated += 1
                    else:
                        char = InventoryMasterCharacteristic(
                            external_system_id=self.system.id,
                            code=code,
                            name=name,
                            type=char_type,
                            required=required
                        )
                        self.db.add(char)
                        items_created += 1

                except Exception as e:
                    logger.error(f"Erro ao processar característica: {e}")
                    items_failed += 1

            self.db.commit()

            self._complete_sync_log(
                sync_log,
                SyncStatus.SUCCESS.value if items_failed == 0 else SyncStatus.PARTIAL.value,
                items_received=items_received,
                items_created=items_created,
                items_updated=items_updated,
                items_failed=items_failed
            )

            return {
                "received": items_received,
                "created": items_created,
                "updated": items_updated,
                "failed": items_failed
            }

        except Exception as e:
            self._complete_sync_log(
                sync_log,
                SyncStatus.FAILED.value,
                error_message=str(e)
            )
            raise

    async def sync_all(self) -> Dict[str, Dict[str, int]]:
        """Sincroniza todos os dados mestres"""
        results = {}

        # Sincronizar na ordem correta (UGs primeiro, depois ULs)
        try:
            results["ug"] = await self.sync_ugs()
        except Exception as e:
            results["ug"] = {"error": str(e)}

        try:
            results["ul"] = await self.sync_uls()
        except Exception as e:
            results["ul"] = {"error": str(e)}

        try:
            results["physical_status"] = await self.sync_physical_status()
        except Exception as e:
            results["physical_status"] = {"error": str(e)}

        try:
            results["characteristics"] = await self.sync_characteristics()
        except Exception as e:
            results["characteristics"] = {"error": str(e)}

        # Atualizar data da última sincronização
        self.system.last_sync_at = datetime.utcnow()
        self.db.commit()

        return results

    async def download_assets_for_session(
        self,
        session_code: str,
        ul_code: Optional[str] = None,
        ug_code: Optional[str] = None,
        limit: int = 5000
    ) -> Dict[str, Any]:
        """
        Baixa bens do sistema externo para uma sessão de inventário.

        O ASI usa o endpoint /coletorweb/storages/create/{codigo_levantamento}
        que retorna os bens esperados para aquele levantamento.

        Args:
            session_code: Código da sessão/levantamento
            ul_code: Código da UL (opcional, para filtro)
            ug_code: Código da UG (opcional, para filtro)
            limit: Limite de registros a baixar

        Returns:
            Dict com lista de bens e estatísticas
        """
        try:
            # Montar endpoint - baseado no app de referência
            endpoint = self.system.endpoint_load_assets or "/coletorweb/storages/create"
            url_endpoint = f"{endpoint}/{session_code}"

            # Payload para filtrar/limitar
            payload = {"$limit": limit}
            if ul_code:
                payload["ul_code"] = ul_code
            if ug_code:
                payload["ug_code"] = ug_code

            logger.info(f"Baixando bens do ASI: {url_endpoint}")

            # Fazer requisição
            data = await self._make_request(url_endpoint, method="POST", data=payload)

            # Processar resposta
            # O ASI pode retornar em diferentes formatos:
            # - {"itens": [...]}
            # - Lista direta [...]
            # - {"bens": [...]}
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("itens") or data.get("bens") or data.get("items") or []

            # Mapear campos do ASI para nosso formato
            # Campos esperados do ASI:
            # CD_BEM_PERM - Código do bem (plaqueta)
            # SQ_BEM_PERM - Sequência do bem
            # DS_BEM - Descrição
            # CD_RFID - Código RFID
            # CD_BARRA - Código de barras
            # CD_UL_ATUAL - Código da UL atual
            # CD_UA_ATUAL - Código da UA atual
            # ST_BAIXADO - Se está baixado (S/N ou 1/0)
            # DS_CATEGORIA - Categoria do bem

            mapped_items = []
            for item in items:
                mapped = {
                    "asset_code": item.get("CD_BEM_PERM") or item.get("codigo") or item.get("code"),
                    "asset_sequence": item.get("SQ_BEM_PERM") or item.get("sequencia"),
                    "description": item.get("DS_BEM") or item.get("descricao") or item.get("description"),
                    "rfid_code": item.get("CD_RFID") or item.get("rfid"),
                    "barcode": item.get("CD_BARRA") or item.get("codigo_barras") or item.get("barcode"),
                    "expected_ul_code": item.get("CD_UL_ATUAL") or item.get("ul_code"),
                    "expected_ua_code": item.get("CD_UA_ATUAL") or item.get("ua_code"),
                    "category": item.get("DS_CATEGORIA") or item.get("categoria"),
                    "is_written_off": self._parse_boolean(
                        item.get("ST_BAIXADO") or item.get("baixado") or item.get("written_off")
                    ),
                    "extra_data": item  # Guardar dados originais para referência
                }

                # Só adicionar se tiver código do bem
                if mapped["asset_code"]:
                    mapped_items.append(mapped)

            return {
                "success": True,
                "total_received": len(items),
                "total_mapped": len(mapped_items),
                "items": mapped_items
            }

        except Exception as e:
            logger.error(f"Erro ao baixar bens: {e}")
            return {
                "success": False,
                "error": str(e),
                "items": []
            }

    def _parse_boolean(self, value: Any) -> bool:
        """Converte valor para boolean"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.upper() in ('S', 'SIM', 'Y', 'YES', 'TRUE', '1')
        return False

    async def upload_inventory_results(
        self,
        session: Any,  # InventorySession
        include_photos: bool = False,
        user_login: str = "sistema"
    ) -> Dict[str, Any]:
        """
        Envia resultados do inventário para o sistema externo ASI.

        O ASI usa o endpoint /coletorweb/service/atualizarColetaLevantamento
        com double encoding: o JSON é stringificado, aspas duplas substituídas
        por aspas simples, e encapsulado em aspas duplas.

        Args:
            session: Sessão de inventário com leituras
            include_photos: Se deve incluir fotos base64
            user_login: Login do usuário para registro

        Returns:
            Dict com resultado do upload (num_transmissao, id_levantamento, etc.)
        """
        from app.models import InventoryReading, InventoryExpectedAsset

        try:
            # Buscar leituras da sessão
            readings = self.db.query(InventoryReading).filter(
                InventoryReading.session_id == session.id
            ).all()

            # Buscar bens esperados
            expected_assets = self.db.query(InventoryExpectedAsset).filter(
                InventoryExpectedAsset.session_id == session.id
            ).all()

            # Criar mapa de bens esperados por código
            expected_map = {a.asset_code: a for a in expected_assets}

            # Montar payload no formato ASI
            now_ts = int(datetime.utcnow().timestamp() * 1000)
            start_ts = int(session.started_at.timestamp() * 1000) if session.started_at else now_ts
            end_ts = int(session.completed_at.timestamp() * 1000) if session.completed_at else now_ts

            # Lista de bens (C12)
            items_c12 = []

            for reading in readings:
                item = {}

                # Buscar bem esperado correspondente
                expected = expected_map.get(reading.matched_asset_code)

                if reading.category == "found" and expected:
                    # Bem encontrado - formato completo
                    item = {
                        "C01": reading.matched_asset_code,  # codBem
                        "C02": expected.asset_sequence or "1",  # sequencial
                        "C03": reading.found_ul_code or expected.expected_ul_code or "",  # ulAtual
                        "C04": reading.rfid_code or "",  # codRFID
                        "C05": "",  # codBemServico (não temos)
                        "C06": self._map_physical_condition(reading.physical_condition),  # codSituacaoFisica
                        "C07": int(reading.read_at.timestamp() * 1000),  # dataRegistro
                        "C09": "01"  # codStatus (encontrado)
                    }

                    # Adicionar foto se disponível e solicitado
                    if include_photos and reading.photo_file_id:
                        # TODO: Buscar foto do storage e converter para base64
                        pass

                elif reading.category == "unregistered":
                    # Bem não cadastrado - formato reduzido
                    item = {
                        "C01": reading.rfid_code or reading.barcode or "",  # código (decimal do RFID)
                        "C04": reading.rfid_code or "",  # codRfid
                        "C07": int(reading.read_at.timestamp() * 1000)  # dataRegistro
                    }

                if item:
                    items_c12.append(item)

            # Montar payload completo
            payload = {
                "C01": session.id,  # id
                "C02": session.collector_id or "1",  # idColetor
                "C04": session.org_code or "001",  # codOrgao
                "C05": session.ug_code or "000000",  # codUG
                "C08": user_login,  # login
                "C10": start_ts,  # dataInicio
                "C11": end_ts,  # dataFim
                "C12": items_c12,  # bens
                "C13": session.objective_code or "01",  # codObjetivo
                "C15": now_ts  # dataTransmissao
            }

            # Campos opcionais
            if session.ua_code:
                payload["C06"] = session.ua_code
            if session.ul_code:
                payload["C07"] = session.ul_code
            if session.responsible_code:
                payload["C16"] = session.responsible_code

            # Endpoint de upload
            endpoint = self.system.endpoint_upload or "/coletorweb/service/atualizarColetaLevantamento"

            logger.info(f"Enviando inventário para ASI: {endpoint}, {len(items_c12)} bens")

            # Fazer requisição com encoding especial
            result = await self._make_upload_request(endpoint, payload)

            # Verificar resposta
            if not result.get("C03") or not result.get("C14"):
                raise ValueError(f"Resposta incompleta do servidor: {result}")

            return {
                "success": True,
                "transmission_number": result.get("C03"),
                "inventory_id": result.get("C14"),
                "items_sent": len(items_c12),
                "raw_response": result
            }

        except Exception as e:
            logger.error(f"Erro ao enviar inventário: {e}")
            return {
                "success": False,
                "error": str(e),
                "items_sent": 0
            }

    async def _make_upload_request(self, endpoint: str, data: dict) -> Any:
        """
        Faz requisição de upload com encoding especial do ASI.
        O ASI espera: "{'campo1': 'valor1', ...}"
        """
        url = self.base_url + endpoint
        headers = self._get_auth_headers()

        # Encoding especial do ASI:
        # 1. Converter dict para JSON string
        # 2. Substituir aspas duplas por aspas simples
        # 3. Encapsular em aspas duplas
        body_str = json.dumps(data)
        body_str = body_str.replace('"', "'")
        body_str = '"' + body_str + '"'

        async with httpx.AsyncClient(
            verify=False,
            timeout=self.system.timeout_seconds * 2  # Timeout maior para upload
        ) as client:
            for attempt in range(self.system.retry_attempts):
                try:
                    response = await client.post(
                        url,
                        headers=headers,
                        content=body_str
                    )

                    if response.status_code == 200:
                        return self._parse_response(response.text)

                    elif response.status_code in (401, 403):
                        raise PermissionError("Falha na autenticação")

                    else:
                        raise Exception(f"Erro HTTP {response.status_code}: {response.text[:200]}")

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    if attempt < self.system.retry_attempts - 1:
                        logger.warning(f"Tentativa {attempt + 1} falhou, tentando novamente...")
                        continue
                    raise ConnectionError(f"Falha na conexão após {self.system.retry_attempts} tentativas: {e}")

    def _map_physical_condition(self, condition: Optional[str]) -> str:
        """Mapeia condição física para código ASI"""
        mapping = {
            "BOM": "01",
            "REGULAR": "02",
            "RUIM": "03",
            "INSERVIVEL": "04",
            "INSERVÍVEL": "04"
        }
        if condition:
            return mapping.get(condition.upper(), "01")
        return "01"  # Default: Bom
