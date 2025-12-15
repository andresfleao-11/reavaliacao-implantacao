"""
Testes para validação de arquivos
"""
import pytest
from fastapi import HTTPException
from app.utils.file_validation import (
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_magic_bytes,
    ALLOWED_IMAGE_EXTENSIONS
)


def test_sanitize_filename():
    """Testa sanitização de nomes de arquivo"""
    # Remover caracteres perigosos
    assert sanitize_filename("../../../etc/passwd") == "_.._.._.._etc_passwd"
    assert sanitize_filename("file<>:\"|\\.txt") == "file________.txt"

    # Manter caracteres válidos
    assert sanitize_filename("image-2024_01.jpg") == "image-2024_01.jpg"

    # Limitar tamanho
    long_name = "a" * 200 + ".txt"
    result = sanitize_filename(long_name)
    assert len(result.split('.')[0]) <= 100


def test_validate_file_extension_valid():
    """Testa validação de extensão válida"""
    # Não deve lançar exceção
    validate_file_extension("image.jpg", ALLOWED_IMAGE_EXTENSIONS)
    validate_file_extension("photo.png", ALLOWED_IMAGE_EXTENSIONS)
    validate_file_extension("picture.gif", ALLOWED_IMAGE_EXTENSIONS)


def test_validate_file_extension_invalid():
    """Testa validação de extensão inválida"""
    with pytest.raises(HTTPException) as exc:
        validate_file_extension("malware.exe", ALLOWED_IMAGE_EXTENSIONS)

    assert exc.value.status_code == 400
    assert "não permitido" in exc.value.detail


def test_validate_file_extension_no_extension():
    """Testa arquivo sem extensão"""
    with pytest.raises(HTTPException) as exc:
        validate_file_extension("filename", ALLOWED_IMAGE_EXTENSIONS)

    assert exc.value.status_code == 400
    assert "sem extensão" in exc.value.detail


def test_validate_file_size_valid():
    """Testa validação de tamanho válido"""
    content = b"a" * 1000  # 1KB
    # Não deve lançar exceção
    validate_file_size(content, max_size=10000)


def test_validate_file_size_too_large():
    """Testa arquivo muito grande"""
    content = b"a" * 11000  # 11KB
    with pytest.raises(HTTPException) as exc:
        validate_file_size(content, max_size=10000)

    assert exc.value.status_code == 400
    assert "muito grande" in exc.value.detail


def test_validate_file_size_empty():
    """Testa arquivo vazio"""
    content = b""
    with pytest.raises(HTTPException) as exc:
        validate_file_size(content)

    assert exc.value.status_code == 400
    assert "vazio" in exc.value.detail


def test_validate_magic_bytes_jpeg():
    """Testa validação de magic bytes JPEG"""
    # JPEG válido
    content = b'\xFF\xD8\xFF\xE0' + b'a' * 100
    # Não deve lançar exceção
    validate_magic_bytes(content, 'image/jpeg')


def test_validate_magic_bytes_png():
    """Testa validação de magic bytes PNG"""
    # PNG válido
    content = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A' + b'a' * 100
    # Não deve lançar exceção
    validate_magic_bytes(content, 'image/png')


def test_validate_magic_bytes_spoofed():
    """Testa detecção de extensão falsa (spoofing)"""
    # Arquivo com conteúdo que não corresponde ao tipo declarado
    content = b'This is not a JPEG file'

    with pytest.raises(HTTPException) as exc:
        validate_magic_bytes(content, 'image/jpeg')

    assert exc.value.status_code == 400
    assert "não corresponde" in exc.value.detail
