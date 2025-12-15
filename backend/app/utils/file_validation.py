"""
Validação e sanitização de uploads de arquivos
"""
import re
import os
from fastapi import HTTPException, UploadFile
from typing import List

# Configurações de segurança para upload
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB para imagens

# Magic bytes para validação de tipo MIME real
MAGIC_BYTES = {
    'image/jpeg': [b'\xFF\xD8\xFF'],
    'image/png': [b'\x89\x50\x4E\x47'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/bmp': [b'BM'],
    'image/webp': [b'RIFF'],
    'application/pdf': [b'%PDF'],
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza o nome do arquivo removendo caracteres perigosos
    """
    # Remove path traversal attempts
    filename = os.path.basename(filename)

    # Remove caracteres especiais perigosos, mantém apenas alphanumericos, pontos, hífens e underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Limita tamanho do nome do arquivo
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]

    return f"{name}{ext}"


def validate_file_extension(filename: str, allowed_extensions: set = ALLOWED_EXTENSIONS) -> None:
    """
    Valida a extensão do arquivo
    """
    ext = os.path.splitext(filename)[1].lower()

    if not ext:
        raise HTTPException(
            status_code=400,
            detail="Arquivo sem extensão"
        )

    if ext not in allowed_extensions:
        allowed_list = ', '.join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não permitido. Extensões permitidas: {allowed_list}"
        )


def validate_file_size(content: bytes, max_size: int = MAX_FILE_SIZE) -> None:
    """
    Valida o tamanho do arquivo
    """
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Arquivo vazio"
        )

    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo muito grande. Tamanho máximo: {max_size_mb:.1f}MB"
        )


def validate_magic_bytes(content: bytes, content_type: str) -> None:
    """
    Valida os magic bytes do arquivo para detectar spoofing de extensão
    """
    if content_type not in MAGIC_BYTES:
        # Tipo não tem validação de magic bytes configurada
        return

    valid_signatures = MAGIC_BYTES[content_type]

    for signature in valid_signatures:
        if content.startswith(signature):
            return

    raise HTTPException(
        status_code=400,
        detail="Conteúdo do arquivo não corresponde ao tipo declarado"
    )


async def validate_upload_file(
    file: UploadFile,
    allowed_extensions: set = ALLOWED_IMAGE_EXTENSIONS,
    max_size: int = MAX_IMAGE_SIZE,
    check_magic_bytes: bool = True
) -> bytes:
    """
    Valida completamente um arquivo de upload

    Args:
        file: Arquivo do upload
        allowed_extensions: Extensões permitidas
        max_size: Tamanho máximo em bytes
        check_magic_bytes: Se deve validar magic bytes

    Returns:
        Conteúdo do arquivo validado

    Raises:
        HTTPException: Se arquivo inválido
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Nenhum arquivo foi enviado"
        )

    # Validar extensão
    validate_file_extension(file.filename, allowed_extensions)

    # Ler conteúdo
    content = await file.read()

    # Validar tamanho
    validate_file_size(content, max_size)

    # Validar magic bytes (tipo MIME real)
    if check_magic_bytes and file.content_type:
        validate_magic_bytes(content, file.content_type)

    # Resetar ponteiro do arquivo para permitir releitura se necessário
    await file.seek(0)

    return content


async def validate_multiple_uploads(
    files: List[UploadFile],
    max_files: int = 5,
    allowed_extensions: set = ALLOWED_IMAGE_EXTENSIONS,
    max_size_per_file: int = MAX_IMAGE_SIZE,
    max_total_size: int = 20 * 1024 * 1024  # 20MB total
) -> List[bytes]:
    """
    Valida múltiplos arquivos de upload

    Args:
        files: Lista de arquivos
        max_files: Número máximo de arquivos
        allowed_extensions: Extensões permitidas
        max_size_per_file: Tamanho máximo por arquivo
        max_total_size: Tamanho máximo total de todos os arquivos

    Returns:
        Lista com conteúdo dos arquivos validados

    Raises:
        HTTPException: Se validação falhar
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Nenhum arquivo foi enviado"
        )

    # Filtrar arquivos vazios
    valid_files = [f for f in files if f.filename]

    if len(valid_files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Número máximo de arquivos excedido. Máximo: {max_files}"
        )

    contents = []
    total_size = 0

    for file in valid_files:
        content = await validate_upload_file(
            file,
            allowed_extensions=allowed_extensions,
            max_size=max_size_per_file
        )

        total_size += len(content)
        contents.append(content)

    if total_size > max_total_size:
        max_total_mb = max_total_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Tamanho total dos arquivos excedido. Máximo: {max_total_mb:.1f}MB"
        )

    return contents
