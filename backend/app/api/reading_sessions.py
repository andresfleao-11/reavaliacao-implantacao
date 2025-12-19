"""API endpoints para sessões de leitura RFID/Barcode"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User, ReadingSession, SessionReading, ReadingType, SessionStatus

router = APIRouter(prefix="/reading-sessions", tags=["reading-sessions"])


# === Schemas ===

class ReadingSessionCreate(BaseModel):
    reading_type: ReadingType
    project_id: Optional[int] = None
    location: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutos padrão


class ReadingSessionResponse(BaseModel):
    id: int
    created_at: datetime
    reading_type: ReadingType
    status: SessionStatus
    user_id: int
    project_id: Optional[int]
    location: Optional[str]
    timeout_seconds: int
    readings_count: int = 0

    class Config:
        from_attributes = True


class SessionReadingCreate(BaseModel):
    code: str
    rssi: Optional[str] = None
    device_id: Optional[str] = None


class SessionReadingResponse(BaseModel):
    id: int
    created_at: datetime
    code: str
    rssi: Optional[str]
    device_id: Optional[str]

    class Config:
        from_attributes = True


class ActiveSessionResponse(BaseModel):
    """Resposta para o app verificar se há sessão ativa"""
    has_active_session: bool
    session_id: Optional[int] = None
    reading_type: Optional[ReadingType] = None
    project_id: Optional[int] = None
    location: Optional[str] = None
    expires_at: Optional[datetime] = None


class BulkReadingsCreate(BaseModel):
    """Para enviar múltiplas leituras de uma vez"""
    readings: List[SessionReadingCreate]


# === Helpers ===

def check_and_expire_session(session: ReadingSession) -> bool:
    """Verifica se a sessão expirou e atualiza o status se necessário"""
    if session.status != SessionStatus.ACTIVE:
        return False

    expires_at = session.created_at + timedelta(seconds=session.timeout_seconds)
    if datetime.now(timezone.utc) > expires_at:
        session.status = SessionStatus.EXPIRED
        return False
    return True


# === Endpoints para Web ===

@router.post("", response_model=ReadingSessionResponse)
def create_session(
    data: ReadingSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cria uma nova sessão de leitura.
    Cancela qualquer sessão ativa anterior do mesmo usuário.
    """
    # Cancelar sessões ativas anteriores do usuário
    active_sessions = db.query(ReadingSession).filter(
        and_(
            ReadingSession.user_id == current_user.id,
            ReadingSession.status == SessionStatus.ACTIVE
        )
    ).all()

    for session in active_sessions:
        session.status = SessionStatus.CANCELLED

    # Criar nova sessão
    new_session = ReadingSession(
        reading_type=data.reading_type,
        user_id=current_user.id,
        project_id=data.project_id,
        location=data.location,
        timeout_seconds=data.timeout_seconds,
        status=SessionStatus.ACTIVE
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return ReadingSessionResponse(
        id=new_session.id,
        created_at=new_session.created_at,
        reading_type=new_session.reading_type,
        status=new_session.status,
        user_id=new_session.user_id,
        project_id=new_session.project_id,
        location=new_session.location,
        timeout_seconds=new_session.timeout_seconds,
        readings_count=0
    )


@router.get("/active", response_model=Optional[ReadingSessionResponse])
def get_my_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna a sessão ativa do usuário atual, se houver"""
    session = db.query(ReadingSession).filter(
        and_(
            ReadingSession.user_id == current_user.id,
            ReadingSession.status == SessionStatus.ACTIVE
        )
    ).first()

    if not session:
        return None

    # Verificar expiração
    if not check_and_expire_session(session):
        db.commit()
        return None

    readings_count = db.query(SessionReading).filter(
        SessionReading.session_id == session.id
    ).count()

    return ReadingSessionResponse(
        id=session.id,
        created_at=session.created_at,
        reading_type=session.reading_type,
        status=session.status,
        user_id=session.user_id,
        project_id=session.project_id,
        location=session.location,
        timeout_seconds=session.timeout_seconds,
        readings_count=readings_count
    )


@router.post("/{session_id}/complete", response_model=ReadingSessionResponse)
def complete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Finaliza uma sessão de leitura"""
    session = db.query(ReadingSession).filter(
        and_(
            ReadingSession.id == session_id,
            ReadingSession.user_id == current_user.id
        )
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Sessão não está ativa")

    session.status = SessionStatus.COMPLETED
    db.commit()
    db.refresh(session)

    readings_count = db.query(SessionReading).filter(
        SessionReading.session_id == session.id
    ).count()

    return ReadingSessionResponse(
        id=session.id,
        created_at=session.created_at,
        reading_type=session.reading_type,
        status=session.status,
        user_id=session.user_id,
        project_id=session.project_id,
        location=session.location,
        timeout_seconds=session.timeout_seconds,
        readings_count=readings_count
    )


@router.post("/{session_id}/cancel", response_model=ReadingSessionResponse)
def cancel_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancela uma sessão de leitura"""
    session = db.query(ReadingSession).filter(
        and_(
            ReadingSession.id == session_id,
            ReadingSession.user_id == current_user.id
        )
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    session.status = SessionStatus.CANCELLED
    db.commit()
    db.refresh(session)

    readings_count = db.query(SessionReading).filter(
        SessionReading.session_id == session.id
    ).count()

    return ReadingSessionResponse(
        id=session.id,
        created_at=session.created_at,
        reading_type=session.reading_type,
        status=session.status,
        user_id=session.user_id,
        project_id=session.project_id,
        location=session.location,
        timeout_seconds=session.timeout_seconds,
        readings_count=readings_count
    )


@router.get("/{session_id}/readings", response_model=List[SessionReadingResponse])
def get_session_readings(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista as leituras de uma sessão"""
    session = db.query(ReadingSession).filter(
        and_(
            ReadingSession.id == session_id,
            ReadingSession.user_id == current_user.id
        )
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    readings = db.query(SessionReading).filter(
        SessionReading.session_id == session_id
    ).order_by(SessionReading.created_at.desc()).all()

    return [
        SessionReadingResponse(
            id=r.id,
            created_at=r.created_at,
            code=r.code,
            rssi=r.rssi,
            device_id=r.device_id
        ) for r in readings
    ]


# === Endpoints para o App Mobile ===

@router.get("/app/check", response_model=ActiveSessionResponse)
def check_active_session_for_app(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Endpoint para o app verificar se há sessão ativa para um usuário.
    Não requer autenticação JWT - usa user_id como parâmetro.
    """
    session = db.query(ReadingSession).filter(
        and_(
            ReadingSession.user_id == user_id,
            ReadingSession.status == SessionStatus.ACTIVE
        )
    ).first()

    if not session:
        return ActiveSessionResponse(has_active_session=False)

    # Verificar expiração
    if not check_and_expire_session(session):
        db.commit()
        return ActiveSessionResponse(has_active_session=False)

    expires_at = session.created_at + timedelta(seconds=session.timeout_seconds)

    return ActiveSessionResponse(
        has_active_session=True,
        session_id=session.id,
        reading_type=session.reading_type,
        project_id=session.project_id,
        location=session.location,
        expires_at=expires_at
    )


@router.post("/app/readings/{session_id}", response_model=dict)
def add_readings_from_app(
    session_id: int,
    data: BulkReadingsCreate,
    db: Session = Depends(get_db)
):
    """
    Endpoint para o app enviar leituras para uma sessão.
    Não requer autenticação JWT.
    """
    session = db.query(ReadingSession).filter(
        ReadingSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Sessão não está ativa")

    # Verificar expiração
    if not check_and_expire_session(session):
        db.commit()
        raise HTTPException(status_code=400, detail="Sessão expirada")

    # Adicionar leituras
    added_count = 0
    for reading_data in data.readings:
        # Verificar se já existe leitura com esse código na sessão
        existing = db.query(SessionReading).filter(
            and_(
                SessionReading.session_id == session_id,
                SessionReading.code == reading_data.code
            )
        ).first()

        if not existing:
            reading = SessionReading(
                session_id=session_id,
                code=reading_data.code,
                rssi=reading_data.rssi,
                device_id=reading_data.device_id
            )
            db.add(reading)
            added_count += 1

    db.commit()

    total_count = db.query(SessionReading).filter(
        SessionReading.session_id == session_id
    ).count()

    return {
        "success": True,
        "added_count": added_count,
        "total_count": total_count
    }


@router.get("", response_model=List[ReadingSessionResponse])
def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista as sessões do usuário"""
    sessions = db.query(ReadingSession).filter(
        ReadingSession.user_id == current_user.id
    ).order_by(ReadingSession.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for session in sessions:
        # Verificar expiração
        check_and_expire_session(session)

        readings_count = db.query(SessionReading).filter(
            SessionReading.session_id == session.id
        ).count()

        result.append(ReadingSessionResponse(
            id=session.id,
            created_at=session.created_at,
            reading_type=session.reading_type,
            status=session.status,
            user_id=session.user_id,
            project_id=session.project_id,
            location=session.location,
            timeout_seconds=session.timeout_seconds,
            readings_count=readings_count
        ))

    db.commit()  # Commit any status changes from expiration checks
    return result
