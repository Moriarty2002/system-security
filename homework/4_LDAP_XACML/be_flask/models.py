from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    username = db.Column(db.String(128), primary_key=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    # role: 'user', 'admin', 'moderator' - kept as separate column to be explicit
    role = db.Column(db.String(32), nullable=False, default='user')
    quota = db.Column(BigInteger, nullable=False, default=0)
    password_hash = db.Column(db.String(256), nullable=False)

    def __repr__(self) -> str:
        return f'<User {self.username}>'