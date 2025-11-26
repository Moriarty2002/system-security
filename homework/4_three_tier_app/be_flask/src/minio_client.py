"""
MinIO client module for object storage operations.

This module provides a centralized MinIO client for file storage operations,
replacing the traditional filesystem-based storage with S3-compatible object storage.
"""

import os
import io
import logging
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime, timedelta
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

# Constants
DIRECTORY_MARKER = '/.directory'


class MinIOClient:
    """MinIO client wrapper for file storage operations."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False
    ):
        """Initialize MinIO client.

        Args:
            endpoint: MinIO server endpoint (host:port)
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket_name: Default bucket name for file storage
            secure: Use HTTPS if True
        """
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        
        try:
            self.client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            self._ensure_bucket()
            logger.info(f"MinIO client initialized successfully (endpoint: {endpoint}, bucket: {bucket_name})")
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def _ensure_bucket(self) -> None:
        """Ensure the bucket exists, create if it doesn't."""
        try:
            if not self.client.bucket_exists(bucket_name=self.bucket_name):
                self.client.make_bucket(bucket_name=self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.debug(f"Bucket already exists: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    def _get_object_path(self, username: str, file_path: str) -> str:
        """Construct object path in MinIO.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            Full object path in MinIO
        """
        # Remove leading/trailing slashes and normalize path
        file_path = file_path.strip('/')
        # Handle empty path
        if not file_path:
            return username + '/'
        return f"{username}/{file_path}"

    def upload_file(
        self,
        username: str,
        file_path: str,
        file_data: BinaryIO,
        file_size: int,
        content_type: str = 'application/octet-stream'
    ) -> bool:
        """Upload a file to MinIO.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space
            file_data: File data stream
            file_size: Size of file in bytes
            content_type: MIME type of file

        Returns:
            True if successful
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_path,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            logger.info(f"Uploaded file: {object_path} ({file_size} bytes)")
            return True
        except S3Error as e:
            logger.error(f"Failed to upload file {object_path}: {e}")
            return False

    def download_file(self, username: str, file_path: str) -> Optional[bytes]:
        """Download a file from MinIO.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            File data as bytes, or None if not found
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_path
            )
            data = response.read()
            response.close()
            response.release_conn()
            logger.debug(f"Downloaded file: {object_path}")
            return data
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.warning(f"File not found: {object_path}")
            else:
                logger.error(f"Failed to download file {object_path}: {e}")
            return None

    def get_file_stream(self, username: str, file_path: str):
        """Get a file stream from MinIO.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            File stream object, or None if not found
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_path
            )
            logger.debug(f"Retrieved file stream: {object_path}")
            return response
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.warning(f"File not found: {object_path}")
            else:
                logger.error(f"Failed to get file stream {object_path}: {e}")
            return None

    def delete_file(self, username: str, file_path: str) -> bool:
        """Delete a file from MinIO.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            True if successful
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_path
            )
            logger.info(f"Deleted file: {object_path}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete file {object_path}: {e}")
            return False

    def list_files(
        self,
        username: str,
        prefix: str = '',
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List files in a user's space.

        Args:
            username: Username for namespace
            prefix: Prefix path within user's space
            recursive: List recursively if True

        Returns:
            List of file dictionaries with name, size, mtime, type
        """
        base_prefix = self._build_base_prefix(username, prefix)
        
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=base_prefix,
                recursive=recursive
            )
            
            if recursive:
                return self._process_recursive_listing(objects, base_prefix)
            else:
                return self._process_non_recursive_listing(objects, base_prefix)
                
        except S3Error as e:
            logger.error(f"Failed to list files for {username} with prefix {prefix}: {e}")
            return []
    
    def _build_base_prefix(self, username: str, prefix: str) -> str:
        """Build the base prefix for listing objects.
        
        Args:
            username: Username for namespace
            prefix: Prefix path within user's space
            
        Returns:
            Full base prefix path
        """
        base_prefix = f"{username}/"
        if prefix:
            clean_prefix = prefix.strip('/')
            base_prefix = f"{username}/{clean_prefix}/"
        return base_prefix
    
    def _process_recursive_listing(
        self, 
        objects, 
        base_prefix: str
    ) -> List[Dict[str, Any]]:
        """Process objects for recursive listing.
        
        Args:
            objects: Iterator of MinIO objects
            base_prefix: Base prefix to strip from paths
            
        Returns:
            List of file dictionaries
        """
        files = []
        for obj in objects:
            if obj.object_name.endswith(DIRECTORY_MARKER):
                continue
            
            relative_path = self._get_relative_path(obj.object_name, base_prefix)
            if relative_path:
                files.append({
                    'name': relative_path,
                    'size': obj.size,
                    'mtime': int(obj.last_modified.timestamp()),
                    'type': 'file'
                })
        return files
    
    def _process_non_recursive_listing(
        self, 
        objects, 
        base_prefix: str
    ) -> List[Dict[str, Any]]:
        """Process objects for non-recursive listing.
        
        Args:
            objects: Iterator of MinIO objects
            base_prefix: Base prefix to strip from paths
            
        Returns:
            List of file and directory dictionaries
        """
        files = []
        seen_dirs = set()
        
        for obj in objects:
            if obj.object_name.endswith(DIRECTORY_MARKER):
                continue
            
            relative_path = self._get_relative_path(obj.object_name, base_prefix)
            if not relative_path:
                continue
            
            if '/' in relative_path:
                # It's in a subdirectory
                self._add_directory_entry(relative_path, seen_dirs, files)
            else:
                # It's a file in the current directory
                files.append({
                    'name': relative_path,
                    'size': obj.size,
                    'mtime': int(obj.last_modified.timestamp()),
                    'type': 'file'
                })
        
        return files
    
    def _get_relative_path(self, object_name: str, base_prefix: str) -> str:
        """Extract relative path from object name.
        
        Args:
            object_name: Full object name
            base_prefix: Base prefix to remove
            
        Returns:
            Relative path or empty string if not valid
        """
        if not object_name.startswith(base_prefix):
            return ''
        return object_name[len(base_prefix):]
    
    def _add_directory_entry(
        self, 
        relative_path: str, 
        seen_dirs: set, 
        files: List[Dict[str, Any]]
    ) -> None:
        """Add directory entry to files list if not seen.
        
        Args:
            relative_path: Path relative to base prefix
            seen_dirs: Set of already seen directory names
            files: List to append directory entry to
        """
        dir_name = relative_path.split('/')[0]
        
        # Skip .bin directory - only accessible via bin endpoint
        if dir_name == '.bin':
            return
        
        if dir_name and dir_name not in seen_dirs:
            seen_dirs.add(dir_name)
            files.append({
                'name': dir_name,
                'size': 0,
                'mtime': 0,
                'type': 'directory'
            })

    def get_user_usage(self, username: str) -> int:
        """Calculate total bytes used by a user.

        Args:
            username: Username

        Returns:
            Total bytes used
        """
        prefix = f"{username}/"
        total_size = 0
        
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            for obj in objects:
                total_size += obj.size
            
            return total_size
        except S3Error as e:
            logger.error(f"Failed to calculate usage for {username}: {e}")
            return 0

    def file_exists(self, username: str, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            True if file exists
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_path
            )
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            logger.error(f"Error checking file existence {object_path}: {e}")
            return False

    def is_directory(self, username: str, dir_path: str) -> bool:
        """Check if a path represents a directory (has files under it).

        Args:
            username: Username for namespace
            dir_path: Directory path to check

        Returns:
            True if directory exists (has objects with this prefix)
        """
        prefix = self._get_object_path(username, dir_path)
        if not prefix.endswith('/'):
            prefix += '/'
        
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=False
            )
            # Check if there's at least one object
            for _ in objects:
                return True
            return False
        except S3Error as e:
            logger.error(f"Error checking directory {prefix}: {e}")
            return False

    def get_file_size(self, username: str, file_path: str) -> Optional[int]:
        """Get size of a file.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            File size in bytes, or None if not found
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_path
            )
            return stat.size
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.warning(f"File not found: {object_path}")
            else:
                logger.error(f"Failed to get file size {object_path}: {e}")
            return None

    def move_file(self, username: str, src_path: str, dest_path: str) -> bool:
        """Move/rename a file.

        Args:
            username: Username for namespace
            src_path: Source file path
            dest_path: Destination file path

        Returns:
            True if successful
        """
        src_object = self._get_object_path(username, src_path)
        dest_object = self._get_object_path(username, dest_path)
        
        try:
            # Copy the object
            from minio.commonconfig import CopySource
            self.client.copy_object(
                bucket_name=self.bucket_name,
                object_name=dest_object,
                source=CopySource(self.bucket_name, src_object)
            )
            # Delete the original
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=src_object
            )
            logger.info(f"Moved file from {src_object} to {dest_object}")
            return True
        except S3Error as e:
            logger.error(f"Failed to move file from {src_object} to {dest_object}: {e}")
            return False

    def move_directory_to_bin(self, username: str, dir_path: str, bin_prefix: str) -> bool:
        """Move all files in a directory to bin, preserving structure.

        Args:
            username: Username for namespace
            dir_path: Directory path to move
            bin_prefix: Bin prefix path (e.g., '.bin/username_timestamp_dirname')

        Returns:
            True if successful
        """
        src_prefix = self._get_object_path(username, dir_path)
        if not src_prefix.endswith('/'):
            src_prefix += '/'
        
        try:
            # List all objects in the directory recursively
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=src_prefix,
                recursive=True
            )
            
            moved_count = 0
            directory_markers = []
            from minio.commonconfig import CopySource
            
            for obj in objects:
                # Track directory markers for later deletion
                if obj.object_name.endswith(DIRECTORY_MARKER):
                    directory_markers.append(obj.object_name)
                    continue
                    
                # Calculate relative path within the directory
                relative_path = obj.object_name[len(src_prefix):]
                
                # Construct destination path in bin
                dest_object = self._get_object_path(username, f"{bin_prefix}/{relative_path}")
                
                # Copy to bin
                self.client.copy_object(
                    bucket_name=self.bucket_name,
                    object_name=dest_object,
                    source=CopySource(self.bucket_name, obj.object_name)
                )
                
                # Delete original
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=obj.object_name
                )
                moved_count += 1
            
            # Delete all directory markers to fully remove the directory from listings
            for marker in directory_markers:
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=marker
                )
            
            logger.info(f"Moved directory {src_prefix} with {moved_count} files to {bin_prefix}")
            return moved_count > 0
            
        except S3Error as e:
            logger.error(f"Failed to move directory {src_prefix} to {bin_prefix}: {e}")
            return False

    def restore_directory_from_bin(self, username: str, bin_path: str, original_path: str) -> bool:
        """Restore all files from a directory in bin back to original location.

        Args:
            username: Username for namespace
            bin_path: Bin path (e.g., '.bin/username_timestamp_dirname')
            original_path: Original directory path to restore to

        Returns:
            True if successful
        """
        bin_prefix = self._get_object_path(username, bin_path)
        if not bin_prefix.endswith('/'):
            bin_prefix += '/'
        
        try:
            # List all objects in the bin directory
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=bin_prefix,
                recursive=True
            )
            
            restored_count = 0
            from minio.commonconfig import CopySource
            
            for obj in objects:
                # Skip directory markers
                if obj.object_name.endswith(DIRECTORY_MARKER):
                    continue
                
                # Calculate relative path within the bin directory
                relative_path = obj.object_name[len(bin_prefix):]
                
                # Construct destination path
                dest_object = self._get_object_path(username, f"{original_path}/{relative_path}")
                
                # Copy back to original location
                self.client.copy_object(
                    bucket_name=self.bucket_name,
                    object_name=dest_object,
                    source=CopySource(self.bucket_name, obj.object_name)
                )
                
                # Delete from bin
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=obj.object_name
                )
                restored_count += 1
            
            logger.info(f"Restored directory from {bin_prefix} with {restored_count} files to {original_path}")
            return restored_count > 0
            
        except S3Error as e:
            logger.error(f"Failed to restore directory from {bin_prefix} to {original_path}: {e}")
            return False

    def delete_directory(self, username: str, dir_path: str) -> bool:
        """Delete a directory and all its contents.

        Args:
            username: Username for namespace
            dir_path: Directory path

        Returns:
            True if successful
        """
        prefix = self._get_object_path(username, dir_path)
        if not prefix.endswith('/'):
            prefix += '/'
        
        try:
            # List all objects with the prefix
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            # Delete all objects
            for obj in objects:
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=obj.object_name
                )
            
            logger.info(f"Deleted directory: {prefix}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete directory {prefix}: {e}")
            return False


