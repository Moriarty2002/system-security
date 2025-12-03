from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from flask import g
import uuid

db = SQLAlchemy()


class UserProfile(db.Model):
    """User profile table for Keycloak-authenticated users.
    
    Stores ONLY application-specific data not managed by Keycloak.
    Keycloak manages: authentication, credentials, user info, timestamps.
    Application manages: quota (storage limits).
    
    Username and role are intentionally NOT stored - fetched from Keycloak token
    on each request to ensure immediate sync and prevent stale data.
    """
    __tablename__ = 'user_profiles'

    keycloak_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quota = db.Column(BigInteger, nullable=False, default=104857600)  # 100MB default
    
    # Username is NOT stored - always from Keycloak token (prevents sync issues)
    @property
    def username(self):
        """Get username from Flask g context (set by authenticate_user from token)."""
        return getattr(g, 'username', None)
    
    # Role is NOT stored - always from Keycloak token (prevents sync issues)
    @property
    def role(self):
        """Get role from Flask g context (set by authenticate_user)."""
        return getattr(g, 'user_role', 'user')

    def __repr__(self) -> str:
        return f'<UserProfile {self.keycloak_id}>'
    
    def to_dict(self) -> dict:
        """Convert to dictionary with username and role from token."""
        return {
            'keycloak_id': str(self.keycloak_id),
            'username': self.username,  # From token via Flask g
            'quota': self.quota,
            'role': self.role  # From token via Flask g
        }


class BinItem(db.Model):
    __tablename__ = 'bin_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(128), nullable=False, index=True)
    original_path = db.Column(db.String(1024), nullable=False)
    item_type = db.Column(db.String(32), nullable=False)
    size = db.Column(BigInteger, nullable=False, default=0)
    deleted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bin_path = db.Column(db.String(1024), nullable=False)

    def __repr__(self) -> str:
        return f'<BinItem {self.username}:{self.original_path}>'