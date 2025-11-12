from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    username = db.Column(db.String(128), primary_key=True)
    # role: 'user', 'admin', 'moderator' - defines user permissions
    role = db.Column(db.String(32), nullable=False, default='user')
    quota = db.Column(BigInteger, nullable=False, default=0)
    password_hash = db.Column(db.String(256), nullable=False)

    def __repr__(self) -> str:
        return f'<User {self.username}>'


class BinItem(db.Model):
    __tablename__ = 'bin_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(128), db.ForeignKey('users.username'), nullable=False)
    original_path = db.Column(db.String(1024), nullable=False)  # Original path relative to user dir
    item_type = db.Column(db.String(32), nullable=False)  # 'file' or 'directory'
    size = db.Column(BigInteger, nullable=False, default=0)  # Size in bytes (0 for directories)
    deleted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bin_path = db.Column(db.String(1024), nullable=False)  # Path in bin storage

    def __repr__(self) -> str:
        return f'<BinItem {self.username}:{self.original_path}>'