"""
Servico de parse de arquivos para cotacao em lote.
Suporta CSV e XLSX com uma coluna de descricao de produtos.
"""
import pandas as pd
from typing import List, Tuple
from pathlib import Path
import io
import logging

logger = logging.getLogger(__name__)


class BatchFileParser:
    """Parser para arquivos de entrada de lote (CSV, XLSX)"""

    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    MAX_ITEMS = 500  # Maximo de itens por lote

    @staticmethod
    def parse_file(file_content: bytes, filename: str) -> Tuple[List[str], str]:
        """
        Faz parse de arquivo CSV ou XLSX e extrai descricoes de produtos.

        Args:
            file_content: Conteudo binario do arquivo
            filename: Nome do arquivo (para detectar extensao)

        Returns:
            Tuple de (lista de descricoes, nome da coluna detectada)

        Raises:
            ValueError: Se formato invalido ou nenhum dado valido encontrado
        """
        ext = Path(filename).suffix.lower()

        if ext not in BatchFileParser.ALLOWED_EXTENSIONS:
            raise ValueError(f"Formato nao suportado: {ext}. Use CSV ou XLSX.")

        if ext == '.csv':
            return BatchFileParser._parse_csv(file_content)
        else:
            return BatchFileParser._parse_excel(file_content)

    @staticmethod
    def _parse_csv(content: bytes) -> Tuple[List[str], str]:
        """
        Faz parse de arquivo CSV com deteccao de encoding.

        Args:
            content: Conteudo binario do CSV

        Returns:
            Tuple de (lista de descricoes, nome da coluna)
        """
        df = None
        # Tenta encodings comuns
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

        return BatchFileParser._extract_descriptions(df)

    @staticmethod
    def _parse_excel(content: bytes) -> Tuple[List[str], str]:
        """
        Faz parse de arquivo XLSX/XLS.

        Args:
            content: Conteudo binario do Excel

        Returns:
            Tuple de (lista de descricoes, nome da coluna)
        """
        try:
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            logger.info("Excel parsed com sucesso")
        except Exception as e:
            raise ValueError(f"Erro ao ler arquivo Excel: {str(e)}")

        return BatchFileParser._extract_descriptions(df)

    @staticmethod
    def _extract_descriptions(df: pd.DataFrame) -> Tuple[List[str], str]:
        """
        Extrai descricoes da primeira coluna do DataFrame.

        Args:
            df: DataFrame pandas

        Returns:
            Tuple de (lista de descricoes limpas, nome da coluna)
        """
        if df.empty:
            raise ValueError("Arquivo vazio ou sem dados validos")

        if len(df.columns) == 0:
            raise ValueError("Arquivo nao contem colunas")

        # Usa a primeira coluna
        col_name = str(df.columns[0])

        # Extrai valores, remove nulos e converte para string
        descriptions = df[df.columns[0]].dropna().astype(str).tolist()

        # Limpa as descricoes
        cleaned_descriptions = []
        for desc in descriptions:
            cleaned = desc.strip()
            # Ignora linhas vazias ou muito curtas
            if len(cleaned) >= 3:
                cleaned_descriptions.append(cleaned)

        if not cleaned_descriptions:
            raise ValueError("Nenhuma descricao valida encontrada no arquivo. Verifique se a primeira coluna contem as descricoes dos produtos.")

        if len(cleaned_descriptions) > BatchFileParser.MAX_ITEMS:
            raise ValueError(
                f"Maximo de {BatchFileParser.MAX_ITEMS} itens por lote. "
                f"O arquivo contem {len(cleaned_descriptions)} itens."
            )

        logger.info(f"Extraidas {len(cleaned_descriptions)} descricoes da coluna '{col_name}'")
        return cleaned_descriptions, col_name

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
