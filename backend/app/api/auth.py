from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.api.deps import bearer_scheme, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.discovery import DiscoveryJob
from app.models.list_eval import SavedList
from app.models.profile import CandidateProfile, ReferenceProfile
from app.models.user import User, UserSession
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserSettingsUpdate,
)
from app.services.audit import record_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _issue_session_tokens(db: Session, user: User, user_agent: str | None = None) -> TokenResponse:
    settings = get_settings()
    access_token = create_token(str(user.id), user.role, token_type="access")
    refresh_token = create_token(str(user.id), user.role, token_type="refresh")
    acc_payload = decode_token(access_token)
    ref_payload = decode_token(refresh_token)

    session = UserSession(
        user_id=user.id,
        refresh_jti=ref_payload["jti"],
        access_jti=acc_payload["jti"],
        is_revoked=False,
        user_agent=user_agent,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    email_norm = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == email_norm).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=email_norm,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="USER",  # Always assign standard USER role on self-registration
        is_active=True,
    )
    db.add(user)
    db.flush()
    record_audit_log(
        db,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return _issue_session_tokens(db, user, request.headers.get("user-agent"))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    email_norm = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email_norm, User.deleted_at.is_(None)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    record_audit_log(
        db,
        action="USER_LOGIN",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return _issue_session_tokens(db, user, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is not a refresh token")

    jti = decoded.get("jti")
    sub = decoded.get("sub")
    session = (
        db.query(UserSession)
        .filter(UserSession.refresh_jti == jti, UserSession.is_revoked.is_(False))
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked or unknown")

    user = db.query(User).filter(User.id == UUID(str(sub)), User.deleted_at.is_(None), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not active")

    # Rotate session
    session.is_revoked = True
    return _issue_session_tokens(db, user, request.headers.get("user-agent"))


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if credentials and credentials.credentials:
        try:
            decoded = decode_token(credentials.credentials)
            jti = decoded.get("jti")
            if jti:
                sessions = (
                    db.query(UserSession)
                    .filter(UserSession.user_id == current_user.id, UserSession.access_jti == jti)
                    .all()
                )
                for s in sessions:
                    s.is_revoked = True
        except jwt.PyJWTError:
            pass
    record_audit_log(
        db,
        action="USER_LOGOUT",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
    )
    db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.retention_days is not None:
        current_user.retention_days = payload.retention_days
    record_audit_log(
        db,
        action="USER_SETTINGS_UPDATED",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
    )
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get("/me/export")
def export_my_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Privacy right-to-access export of user-owned records."""
    refs = db.query(ReferenceProfile).filter(ReferenceProfile.owner_id == current_user.id, ReferenceProfile.deleted_at.is_(None)).all()
    jobs = db.query(DiscoveryJob).filter(DiscoveryJob.owner_id == current_user.id).all()
    lists = db.query(SavedList).filter(SavedList.owner_id == current_user.id, SavedList.deleted_at.is_(None)).all()
    private_cands = db.query(CandidateProfile).filter(CandidateProfile.owner_id == current_user.id, CandidateProfile.deleted_at.is_(None)).all()

    record_audit_log(
        db,
        action="USER_DATA_EXPORTED",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
    )
    db.commit()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "retention_days": current_user.retention_days,
        },
        "reference_profiles": [{"id": str(r.id), "full_name": r.full_name, "created_at": r.created_at.isoformat()} for r in refs],
        "discovery_jobs": [{"id": str(j.id), "status": j.status, "created_at": j.created_at.isoformat()} for j in jobs],
        "saved_lists": [{"id": str(l.id), "name": l.name} for l in lists],
        "uploaded_private_candidates_count": len(private_cands),
    }


@router.delete("/me")
def delete_my_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Soft-delete user account, revoke sessions, and delete private uploaded candidates."""
    now = datetime.now(timezone.utc)
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_revoked": True})
    db.query(CandidateProfile).filter(
        CandidateProfile.owner_id == current_user.id,
        CandidateProfile.visibility == "private",
    ).update({"deleted_at": now})
    db.query(ReferenceProfile).filter(ReferenceProfile.owner_id == current_user.id).update({"deleted_at": now})
    db.query(SavedList).filter(SavedList.owner_id == current_user.id).update({"deleted_at": now})
    current_user.is_active = False
    current_user.deleted_at = now
    current_user.email = f"deleted-{current_user.id}@redacted.local"
    record_audit_log(
        db,
        action="USER_DATA_DELETED",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
    )
    db.commit()
    return {"message": "Account and private user data deleted"}
