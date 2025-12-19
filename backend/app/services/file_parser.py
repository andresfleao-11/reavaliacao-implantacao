"""
Servico de parse de arquivos para cotacao em lote.
Suporta CSV e XLSX com colunas de codigo e descricao de produtos.
"""
import pandas as pd
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import io
import logging

logger = logging.getLogger(__name__)


class BatchFileItem:
    """Representa um item do lote com codigo e descricao"""
    def __init__(self, descricao: str, codigo: Optional[str] = None):
        self.descricao = descricao
        self.codigo = codigo


class BatchFileParser:
    """Parser para arquivos de entrada de lote (CSV, XLSX)"""

    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    MAX_ITEMS = 500  # Maximo de itens por lote

    # Nomes de colunas aceitos para codigo
    CODIGO_COLUMNS = ['codigo (material)', 'codigo', 'código (material)', 'código', 'code', 'material', 'cod']
    # Nomes de colunas aceitos para descricao
    DESCRICAO_COLUMNS = ['descricao', 'descrição', 'descricao do produto', 'description', 'produto', 'item', 'nome']

    @staticmethod
    def parse_file(file_content: bytes, filename: str) -> Tuple[List[str], str]:
        """
        Faz parse de arquivo CSV ou XLSX e extrai descricoes de produtos.
        Metodo de compatibilidade - retorna apenas descricoes.

        Args:
            file_content: Conteudo binario do arquivo
            filename: Nome do arquivo (para detectar extensao)

        Returns:
            Tuple de (lista de descricoes, nome da coluna detectada)

        Raises:
            ValueError: Se formato invalido ou nenhum dado valido encontrado
        """
        items, col_info = BatchFileParser.parse_file_with_codes(file_content, filename)
        descriptions = [item.descricao for item in items]
        return descriptions, col_info

    @staticmethod
    def parse_file_with_codes(file_content: bytes, filename: str) -> Tuple[List[BatchFileItem], str]:
        """
        Faz parse de arquivo CSV ou XLSX e extrai codigos e descricoes.

        Args:
            file_content: Conteudo binario do arquivo
            filename: Nome do arquivo (para detectar extensao)

        Returns:
            Tuple de (lista de BatchFileItem, info sobre colunas)

        Raises:
            ValueError: Se formato invalido ou nenhum dado valido encontrado
        """
        ext = Path(filename).suffix.lower()

        if ext not in BatchFileParser.ALLOWED_EXTENSIONS:
            raise ValueError(f"Formato nao suportado: {ext}. Use CSV ou XLSX.")

        if ext == '.csv':
            return BatchFileParser._parse_csv_with_codes(file_content)
        else:
            return BatchFileParser._parse_excel_with_codes(file_content)

    @staticmethod
    def _read_csv(content: bytes) -> pd.DataFrame:
        """Le arquivo CSV com deteccao de encoding."""
        df = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                logger.info(f"CSV parsed com encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Erro ao tentar encoding {encoding}: {e}")
                continue

        if df is None:
            raise ValueError("Nao foi possivel decodificar o arquivo CSV. Verifique o encoding.")
        return df

    @staticmethod
    def _read_excel(content: bytes) -> pd.DataFrame:
        """Le arquivo Excel."""
        try:
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            logger.info("Excel parsed com sucesso")
            return df
        except Exception as e:
            raise ValueError(f"Erro ao ler arquivo Excel: {str(e)}")

    @staticmethod
    def _parse_csv(content: bytes) -> Tuple[List[str], str]:
        """Metodo de compatibilidade - retorna apenas descricoes."""
        df = BatchFileParser._read_csv(content)
        return BatchFileParser._extract_descriptions(df)

    @staticmethod
    def _parse_excel(content: bytes) -> Tuple[List[str], str]:
        """Metodo de compatibilidade - retorna apenas descricoes."""
        df = BatchFileParser._read_excel(content)
        return BatchFileParser._extract_descriptions(df)

    @staticmethod
    def _parse_csv_with_codes(content: bytes) -> Tuple[List[BatchFileItem], str]:
        """Parse CSV retornando codigo e descricao."""
        df = BatchFileParser._read_csv(content)
        return BatchFileParser._extract_with_codes(df)

    @staticmethod
    def _parse_excel_with_codes(content: bytes) -> Tuple[List[BatchFileItem], str]:
        """Parse Excel retornando codigo e descricao."""
        df = BatchFileParser._read_excel(content)
        return BatchFileParser._extract_with_codes(df)

    @staticmethod
    def _find_column(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Encontra coluna pelo nome (case-insensitive)."""
        columns_lower = {str(col).lower(): col for col in df.columns}
        for name in possible_names:
            if name.lower() in columns_lower:
                return columns_lower[name.lower()]
        return None

    @staticmethod
    def _extract_with_codes(df: pd.DataFrame) -> Tuple[List[BatchFileItem], str]:
        """
        Extrai codigos e descricoes do DataFrame.
        Suporta arquivos com 1 coluna (descricao) ou 2 colunas (codigo, descricao).
        """
        if df.empty:
            raise ValueError("Arquivo vazio ou sem dados validos")

        if len(df.columns) == 0:
            raise ValueError("Arquivo nao contem colunas")

        # Tentar encontrar coluna de descricao
        desc_col = BatchFileParser._find_column(df, BatchFileParser.DESCRICAO_COLUMNS)
        codigo_col = BatchFileParser._find_column(df, BatchFileParser.CODIGO_COLUMNS)

        # Se nao encontrou coluna de descricao, usa a segunda coluna (se houver 2) ou a primeira
        if not desc_col:
            if len(df.columns) >= 2:
                desc_col = df.columns[1]  # Segunda coluna
            else:
                desc_col = df.columns[0]  # Primeira coluna

        # Se nao encontrou coluna de codigo mas tem 2 colunas, usa a primeira
        if not codigo_col and len(df.columns) >= 2:
            # Se a descricao esta na segunda coluna, codigo esta na primeira
            if desc_col == df.columns[1]:
                codigo_col = df.columns[0]

        col_info = f"Descricao: '{desc_col}'"
        if codigo_col:
            col_info = f"Codigo: '{codigo_col}', {col_info}"

        items = []
        for idx, row in df.iterrows():
            # Pegar descricao
            desc_value = row[desc_col] if pd.notna(row[desc_col]) else ''
            desc = str(desc_value).strip()

            # Pular linhas sem descricao valida
            if len(desc) < 3:
                continue

            # Pegar codigo (opcional)
            codigo = None
            if codigo_col and pd.notna(row[codigo_col]):
                codigo = str(row[codigo_col]).strip()
                if codigo == '' or codigo.lower() == 'nan':
                    codigo = None

            items.append(BatchFileItem(descricao=desc, codigo=codigo))

        if not items:
            raise ValueError("Nenhum item valido encontrado. Verifique se o arquivo contem dados.")

        if len(items) > BatchFileParser.MAX_ITEMS:
            raise ValueError(
                f"Maximo de {BatchFileParser.MAX_ITEMS} itens por lote. "
                f"O arquivo contem {len(items)} itens."
            )

        logger.info(f"Extraidos {len(items)} itens. {col_info}")
        return items, col_info

    @staticmethod
    def _extract_descriptions(df: pd.DataFrame) -> Tuple[List[str], str]:
        """Metodo de compatibilidade - extrai apenas descricoes."""
        items, col_info = BatchFileParser._extract_with_codes(df)
        descriptions = [item.descricao for item in items]
        return descriptions, col_info

    @staticmethod
    def parse_text_batch(text: str, separator: str = ";") -> List[str]:
        """
        Faz parse de texto com descricoes separadas por delimitador.

        Args:
            text: Texto com descricoes separadas
            separator: Caractere separador (padrao: ";")

        Returns:
            Lista de descricoes limpas

        Raises:
            ValueError: Se nenhuma descricao valida encontrada ou excede limite
        """
        if not text or not text.strip():
            raise ValueError("Texto vazio")

        # Divide pelo separador
        parts = text.split(separator)

        # Limpa cada parte
        cleaned_descriptions = []
        for part in parts:
            cleaned = part.strip()
            # Ignora partes vazias ou muito curtas
            if len(cleaned) >= 3:
                cleaned_descriptions.append(cleaned)

        if not cleaned_descriptions:
            raise ValueError(
                f"Nenhuma descricao valida encontrada. "
                f"Separe os produtos com '{separator}' (ex: Produto 1{separator} Produto 2{separator} Produto 3)"
            )

        if len(cleaned_descriptions) > BatchFileParser.MAX_ITEMS:
            raise ValueError(
                f"Maximo de {BatchFileParser.MAX_ITEMS} itens por lote. "
                f"O texto contem {len(cleaned_descriptions)} itens."
            )

        logger.info(f"Extraidas {len(cleaned_descriptions)} descricoes do texto")
        return cleaned_descriptions

    @staticmethod
    def validate_images_batch(images_count: int) -> None:
        """
        Valida quantidade de imagens no lote.

        Args:
            images_count: Numero de imagens

        Raises:
            ValueError: Se quantidade invalida
        """
        if images_count == 0:
            raise ValueError("Nenhuma imagem fornecida")

        if images_count > BatchFileParser.MAX_ITEMS:
            raise ValueError(
                f"Maximo de {BatchFileParser.MAX_ITEMS} imagens por lote. "
                f"Foram fornecidas {images_count} imagens."
            )

        logger.info(f"Validado lote com {images_count} imagens")
