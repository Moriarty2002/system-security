import os
from typing import List, Dict, Any


def ensure_storage_directory(storage_dir: str) -> None:
    """Ensure storage directory exists.

    Args:
        storage_dir: Path to storage directory
    """
    os.makedirs(storage_dir, exist_ok=True)


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