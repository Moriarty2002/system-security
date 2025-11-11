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


def get_user_files_list(username: str, storage_dir: str) -> List[Dict[str, Any]]:
    """Get list of files for a user.

    Args:
        username: User's username
        storage_dir: Base storage directory

    Returns:
        List of file dictionaries with name, size, mtime
    """
    user_dir = os.path.join(storage_dir, username)
    files = []
    if not os.path.exists(user_dir):
        return files

    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        if os.path.isfile(path):
            stat = os.stat(path)
            files.append({
                'name': name,
                'size': stat.st_size,
                'mtime': int(stat.st_mtime)
            })
    return files


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