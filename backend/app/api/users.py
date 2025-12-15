from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from app.core.database import get_db
from app.models import User, UserRole
from app.core.auth import create_access_token, get_current_user, get_current_admin_user
from datetime import datetime

router = APIRouter(prefix="/api/users", tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== SCHEMAS ====================

class UserCreate(BaseModel):
    email: EmailStr
    nome: str
    password: str
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    ativo: Optional[bool] = None


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str


class AdminPasswordReset(BaseModel):
    new_password: str


class UserResponse(BaseModel):
    id: int
    email: str
    nome: str
    role: str
    ativo: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    message: str


class AccountUpdateRequest(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None


# ==================== HELPER FUNCTIONS ====================

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_email(email: str, db: Session) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


# ==================== AUTH ENDPOINTS ====================

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Autentica usuário e retorna suas informações"""
    user = get_user_by_email(request.email, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )

    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário bloqueado"
        )

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )

    # Gerar token JWT (sub deve ser string conforme JWT spec)
    access_token = create_access_token(data={"sub": str(user.id)})

    return LoginResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            nome=user.nome,
            role=user.role.value,
            ativo=user.ativo,
            created_at=user.created_at
        ),
        access_token=access_token,
        token_type="bearer",
        message="Login realizado com sucesso"
    )


# ==================== ACCOUNT ENDPOINTS (for all users) ====================

@router.get("/account/{user_id}", response_model=UserResponse)
def get_account(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtém informações da conta do usuário"""
    # Verificar se o usuário está tentando acessar sua própria conta
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return UserResponse(
        id=user.id,
        email=user.email,
        nome=user.nome,
        role=user.role.value,
        ativo=user.ativo,
        created_at=user.created_at
    )


@router.put("/account/{user_id}", response_model=UserResponse)
def update_account(
    user_id: int,
    request: AccountUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza informações da conta (nome e email)"""
    # Verificar se o usuário está tentando atualizar sua própria conta
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Verificar se o email já existe (se está sendo alterado)
    if request.email and request.email != user.email:
        existing = get_user_by_email(request.email, db)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email já cadastrado"
            )
        user.email = request.email

    if request.nome:
        user.nome = request.nome

    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        nome=user.nome,
        role=user.role.value,
        ativo=user.ativo,
        created_at=user.created_at
    )


@router.post("/account/{user_id}/change-password")
def change_password(
    user_id: int,
    request: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permite usuário alterar sua própria senha"""
    # Usuário só pode alterar sua própria senha
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode alterar sua própria senha"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Verificar senha atual
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta"
        )

    # Atualizar senha
    user.hashed_password = get_password_hash(request.new_password)
    db.commit()

    return {"message": "Senha alterada com sucesso"}


# ==================== ADMIN ENDPOINTS ====================

@router.get("", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários (ADMIN only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    total = db.query(User).count()

    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                email=u.email,
                nome=u.nome,
                role=u.role.value,
                ativo=u.ativo,
                created_at=u.created_at
            )
            for u in users
        ],
        total=total
    )


@router.post("", response_model=UserResponse)
def create_user(
    request: UserCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Cria novo usuário (ADMIN only)"""
    # Verificar se email já existe
    existing = get_user_by_email(request.email, db)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email já cadastrado"
        )

    # Criar usuário
    new_user = User(
        email=request.email,
        nome=request.nome,
        hashed_password=get_password_hash(request.password),
        role=request.role,
        ativo=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        nome=new_user.nome,
        role=new_user.role.value,
        ativo=new_user.ativo,
        created_at=new_user.created_at
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Obtém usuário por ID (ADMIN only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return UserResponse(
        id=user.id,
        email=user.email,
        nome=user.nome,
        role=user.role.value,
        ativo=user.ativo,
        created_at=user.created_at
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    request: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Atualiza usuário (ADMIN only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Verificar se o email já existe (se está sendo alterado)
    if request.email and request.email != user.email:
        existing = get_user_by_email(request.email, db)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email já cadastrado"
            )
        user.email = request.email

    if request.nome is not None:
        user.nome = request.nome

    if request.role is not None:
        user.role = request.role

    if request.ativo is not None:
        user.ativo = request.ativo

    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        nome=user.nome,
        role=user.role.value,
        ativo=user.ativo,
        created_at=user.created_at
    )


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: AdminPasswordReset,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Reseta senha de usuário (ADMIN only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    user.hashed_password = get_password_hash(request.new_password)
    db.commit()

    return {"message": "Senha resetada com sucesso"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Deleta usuário (ADMIN only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Não permitir deletar o próprio admin
    if user.role == UserRole.ADMIN:
        # Verificar se é o único admin
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Não é possível deletar o único administrador do sistema"
            )

    db.delete(user)
    db.commit()

    return {"message": "Usuário deletado com sucesso"}
