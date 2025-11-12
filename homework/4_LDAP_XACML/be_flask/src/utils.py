import os
import shutil
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .models import db, BinItem


def ensure_storage_directory(storage_dir: str) -> None:
    """Ensure storage directory exists.

    Args:
        storage_dir: Path to storage directory
    """
    os.makedirs(storage_dir, exist_ok=True)


def ensure_bin_directory(storage_dir: str) -> str:
    """Ensure bin directory exists and return its path.

    Args:
        storage_dir: Base storage directory

    Returns:
        Path to bin directory
    """
    bin_dir = os.path.join(storage_dir, '.bin')
    os.makedirs(bin_dir, exist_ok=True)
    return bin_dir


def get_user_usage_bytes(username: str, storage_dir: str) -> int:
    """Calculate total bytes used by a user.

    Args:
        username: User's username
        storage_dir: Base storage directory

    Returns:
        Total bytes used
    """
    user_dir = os.path.join(storage_dir, username)
    total = 0
    if not os.path.exists(user_dir):
        return 0

    for root, dirs, files in os.walk(user_dir):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def get_user_files_list(username: str, storage_dir: str, subpath: str = '') -> List[Dict[str, Any]]:
    """Get list of files and directories for a user in a specific path.

    Args:
        username: User's username
        storage_dir: Base storage directory
        subpath: Subpath within user's directory

    Returns:
        List of file/directory dictionaries with name, size, mtime, type
    """
    user_dir = os.path.join(storage_dir, username)
    target_dir = os.path.join(user_dir, subpath) if subpath else user_dir
    items = []
    if not os.path.exists(target_dir):
        return items

    for name in os.listdir(target_dir):
        path = os.path.join(target_dir, name)
        stat = os.stat(path)
        item_type = 'directory' if os.path.isdir(path) else 'file'
        size = 0 if item_type == 'directory' else stat.st_size
        items.append({
            'name': name,
            'size': size,
            'mtime': int(stat.st_mtime),
            'type': item_type
        })
    return items


def get_user_bin_items(username: str) -> List[Dict[str, Any]]:
    """Get list of items in user's bin.

    Args:
        username: User's username

    Returns:
        List of bin item dictionaries
    """
    bin_items = BinItem.query.filter_by(username=username).order_by(BinItem.deleted_at.desc()).all()
    items = []
    for item in bin_items:
        items.append({
            'id': item.id,
            'original_path': item.original_path,
            'item_type': item.item_type,
            'size': item.size,
            'deleted_at': int(item.deleted_at.timestamp()),
            'bin_path': item.bin_path
        })
    return items


def move_to_bin(username: str, item_path: str, storage_dir: str) -> str:
    """Move an item to the bin.

    Args:
        username: User's username
        item_path: Path to item relative to user directory
        storage_dir: Base storage directory

    Returns:
        Bin path for the moved item
    """
    user_dir = os.path.join(storage_dir, username)
    full_item_path = os.path.join(user_dir, item_path)
    bin_dir = ensure_bin_directory(storage_dir)
    
    # Create unique bin path
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    bin_item_name = f"{username}_{timestamp}_{os.path.basename(item_path)}"
    bin_item_path = os.path.join(bin_dir, bin_item_name)
    
    # Move the item
    shutil.move(full_item_path, bin_item_path)
    
    return bin_item_name


def restore_from_bin(bin_item_id: int, username: str, storage_dir: str) -> bool:
    """Restore an item from the bin.

    Args:
        bin_item_id: ID of bin item
        username: User's username
        storage_dir: Base storage directory

    Returns:
        True if restored successfully
    """
    bin_item = BinItem.query.filter_by(id=bin_item_id, username=username).first()
    if not bin_item:
        return False
    
    bin_dir = ensure_bin_directory(storage_dir)
    user_dir = os.path.join(storage_dir, username)
    
    bin_full_path = os.path.join(bin_dir, bin_item.bin_path)
    restore_path = os.path.join(user_dir, bin_item.original_path)
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(restore_path), exist_ok=True)
    
    # Move back from bin
    shutil.move(bin_full_path, restore_path)
    
    # Remove from database
    db.session.delete(bin_item)
    db.session.commit()
    
    return True


def permanently_delete_from_bin(bin_item_id: int, username: str, storage_dir: str) -> bool:
    """Permanently delete an item from the bin.

    Args:
        bin_item_id: ID of bin item
        username: User's username
        storage_dir: Base storage directory

    Returns:
        True if deleted successfully
    """
    bin_item = BinItem.query.filter_by(id=bin_item_id, username=username).first()
    if not bin_item:
        return False
    
    bin_dir = ensure_bin_directory(storage_dir)
    bin_full_path = os.path.join(bin_dir, bin_item.bin_path)
    
    # Remove the file/directory
    if os.path.isdir(bin_full_path):
        shutil.rmtree(bin_full_path)
    else:
        os.remove(bin_full_path)
    
    # Remove from database
    db.session.delete(bin_item)
    db.session.commit()
    
    return True


def cleanup_expired_bin_items(storage_dir: str) -> int:
    """Clean up bin items older than 5 days.

    Args:
        storage_dir: Base storage directory

    Returns:
        Number of items cleaned up
    """
    cutoff_date = datetime.utcnow() - timedelta(days=5)
    expired_items = BinItem.query.filter(BinItem.deleted_at < cutoff_date).all()
    
    bin_dir = ensure_bin_directory(storage_dir)
    cleaned_count = 0
    
    for item in expired_items:
        bin_full_path = os.path.join(bin_dir, item.bin_path)
        try:
            if os.path.isdir(bin_full_path):
                shutil.rmtree(bin_full_path)
            else:
                os.remove(bin_full_path)
            db.session.delete(item)
            cleaned_count += 1
        except Exception:
            # Log error but continue
            pass
    
    db.session.commit()
    return cleaned_count


def ensure_user_directory(username: str, storage_dir: str) -> str:
    """Ensure user directory exists and return its path.

    Args:
        username: User's username
        storage_dir: Base storage directory

    Returns:
        Path to user directory
    """
    user_dir = os.path.join(storage_dir, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir