"""
Utility functions for S3-based file storage operations.

This module provides file storage operations using AWS S3 with Roles Anywhere authentication.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from .models import db, BinItem
from .s3_client import S3Client

logger = logging.getLogger(__name__)


def get_user_usage_bytes(username: str, s3_client: S3Client) -> int:
    """Calculate total bytes used by a user in S3.

    Args:
        username: User's username
        s3_client: S3 client instance

    Returns:
        Total bytes used
    """
    return s3_client.get_user_usage(username)


def get_user_files_list(
    username: str,
    s3_client: S3Client,
    subpath: str = ''
) -> List[Dict[str, Any]]:
    """Get list of files and directories for a user in a specific path.

    Args:
        username: User's username
        s3_client: S3 client instance
        subpath: Subpath within user's directory

    Returns:
        List of file/directory dictionaries with name, size, mtime, type
    """
    return s3_client.list_files(username, prefix=subpath, recursive=False)


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


def move_to_bin(
    username: str,
    item_path: str,
    s3_client: S3Client,
    is_directory: bool = False
) -> str:
    """Move an item to the bin in S3.

    Args:
        username: User's username
        item_path: Path to item relative to user directory
        s3_client: S3 client instance
        is_directory: Whether the item is a directory

    Returns:
        Bin path for the moved item
    """
    # Create unique bin path
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    bin_item_name = f"{username}_{timestamp}_{item_path.replace('/', '_')}"
    bin_path = f".bin/{bin_item_name}"
    
    # Move the file or directory in S3
    if is_directory:
        success = s3_client.move_directory_to_bin(username, item_path, bin_path)
    else:
        success = s3_client.move_file(username, item_path, bin_path)
    
    if not success:
        raise RuntimeError(f"Failed to move {item_path} to bin")
    
    return bin_path


def restore_from_bin(
    bin_item_id: int,
    username: str,
    s3_client: S3Client
) -> bool:
    """Restore an item from the bin in S3.

    Args:
        bin_item_id: ID of bin item
        username: User's username
        s3_client: S3 client instance

    Returns:
        True if restored successfully
    """
    bin_item = BinItem.query.filter_by(id=bin_item_id, username=username).first()
    if not bin_item:
        return False
    
    # Restore based on item type
    if bin_item.item_type == 'directory':
        success = s3_client.restore_directory_from_bin(
            username, 
            bin_item.bin_path, 
            bin_item.original_path
        )
    else:
        # Move back from bin (single file)
        success = s3_client.move_file(username, bin_item.bin_path, bin_item.original_path)
    
    if not success:
        logger.error(f"Failed to restore {bin_item.bin_path} to {bin_item.original_path}")
        return False
    
    # Remove from database
    db.session.delete(bin_item)
    db.session.commit()
    
    return True


def permanently_delete_from_bin(
    bin_item_id: int,
    username: str,
    s3_client: S3Client
) -> bool:
    """Permanently delete an item from the bin in S3.

    Args:
        bin_item_id: ID of bin item
        username: User's username
        s3_client: S3 client instance

    Returns:
        True if deleted successfully
    """
    bin_item = BinItem.query.filter_by(id=bin_item_id, username=username).first()
    if not bin_item:
        return False
    
    # Delete based on item type
    if bin_item.item_type == 'directory':
        success = s3_client.delete_directory(username, bin_item.bin_path)
    else:
        # Delete single file from S3
        success = s3_client.delete_file(username, bin_item.bin_path)
    
    if not success:
        logger.error(f"Failed to delete {bin_item.bin_path} from S3")
        return False
    
    # Remove from database
    db.session.delete(bin_item)
    db.session.commit()
    
    return True


def cleanup_expired_bin_items(s3_client: S3Client) -> int:
    """Clean up bin items older than 5 days from S3.

    Args:
        s3_client: S3 client instance

    Returns:
        Number of items cleaned up
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=5)
    expired_items = BinItem.query.filter(BinItem.deleted_at < cutoff_date).all()
    
    cleaned_count = 0
    
    for item in expired_items:
        try:
            # Delete from S3
            s3_client.delete_file(item.username, item.bin_path)
            
            # Remove from database
            db.session.delete(item)
            cleaned_count += 1
        except Exception as e:
            logger.error(f"Failed to cleanup bin item {item.id}: {e}")
            # Continue with other items
    
    db.session.commit()
    return cleaned_count


def get_directory_size(username: str, dir_path: str, s3_client: S3Client) -> int:
    """Calculate size of a directory recursively.

    Args:
        username: User's username
        dir_path: Directory path
        s3_client: S3 client instance

    Returns:
        Total size in bytes
    """
    prefix = dir_path if dir_path.endswith('/') else f"{dir_path}/"
    files = s3_client.list_files(username, prefix=prefix, recursive=True)
    
    total_size = 0
    for file_info in files:
        if file_info['type'] == 'file':
            total_size += file_info['size']
    
    return total_size
