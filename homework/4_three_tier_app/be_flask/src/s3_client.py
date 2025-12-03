"""
AWS S3 client module with Roles Anywhere authentication for object storage operations.

This module provides an S3 client that authenticates using AWS IAM Roles Anywhere
with X.509 certificates, allowing secure access to S3 buckets without long-term credentials.
"""

import os
import io
import json
import logging
import tempfile
import subprocess
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

logger = logging.getLogger(__name__)

# Constants
DIRECTORY_MARKER = '/.directory'


class RolesAnywhereCredentialProvider:
    """Custom credential provider for AWS Roles Anywhere."""
    
    def __init__(
        self,
        certificate_pem: str,
        private_key_pem: str,
        trust_anchor_arn: str,
        profile_arn: str,
        role_arn: str,
        region: str,
        session_duration: int = 3600
    ):
        """Initialize the credential provider.
        
        Args:
            certificate_pem: X.509 certificate in PEM format
            private_key_pem: Private key in PEM format
            trust_anchor_arn: ARN of the trust anchor
            profile_arn: ARN of the profile
            role_arn: ARN of the role to assume
            region: AWS region
            session_duration: Session duration in seconds
        """
        self.certificate_pem = certificate_pem
        self.private_key_pem = private_key_pem
        self.trust_anchor_arn = trust_anchor_arn
        self.profile_arn = profile_arn
        self.role_arn = role_arn
        self.region = region
        self.session_duration = session_duration
        
        # Temporary file paths (will be created on first use)
        self.cert_path = None
        self.key_path = None
    
    def _write_credentials_to_files(self):
        """Write certificate and key to temporary files if not already done."""
        if self.cert_path is None:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(self.certificate_pem)
                self.cert_path = f.name
        
        if self.key_path is None:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(self.private_key_pem)
                self.key_path = f.name
    
    def _cleanup_files(self):
        """Clean up temporary credential files."""
        if self.cert_path and os.path.exists(self.cert_path):
            try:
                os.unlink(self.cert_path)
            except Exception as e:
                logger.warning(f"Failed to delete cert file: {e}")
        
        if self.key_path and os.path.exists(self.key_path):
            try:
                os.unlink(self.key_path)
            except Exception as e:
                logger.warning(f"Failed to delete key file: {e}")
    
    def get_credentials(self) -> Dict[str, str]:
        """Get temporary credentials using the AWS credential helper or direct API call.
        
        Returns:
            Dictionary with AccessKeyId, SecretAccessKey, SessionToken, and Expiration
        """
        self._write_credentials_to_files()
        
        try:
            # Try using aws_signing_helper if available (AWS official tool)
            # Download from: https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html
            helper_path = '/usr/local/bin/aws_signing_helper'
            
            if os.path.exists(helper_path):
                return self._get_credentials_via_helper(helper_path)
            else:
                logger.info("AWS signing helper not found, using direct boto3 approach")
                return self._get_credentials_via_boto3()
                
        except Exception as e:
            logger.error(f"Failed to obtain credentials: {e}")
            raise
    
    def _get_credentials_via_helper(self, helper_path: str) -> Dict[str, str]:
        """Get credentials using AWS credential helper binary.
        
        Args:
            helper_path: Path to aws_signing_helper binary
            
        Returns:
            Credential dictionary
        """
        cmd = [
            helper_path,
            'credential-process',
            '--certificate', self.cert_path,
            '--private-key', self.key_path,
            '--trust-anchor-arn', self.trust_anchor_arn,
            '--profile-arn', self.profile_arn,
            '--role-arn', self.role_arn
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        creds = json.loads(result.stdout)
        
        return {
            'AccessKeyId': creds['AccessKeyId'],
            'SecretAccessKey': creds['SecretAccessKey'],
            'SessionToken': creds['SessionToken'],
            'Expiration': creds['Expiration']
        }
    
    def _get_credentials_via_boto3(self) -> Dict[str, str]:
        """Get credentials using boto3 STS assume role with web identity.
        
        This is a simplified approach that uses standard AWS STS.
        For production, consider installing aws_signing_helper.
        
        Returns:
            Credential dictionary
        """
        # For now, we'll use a simpler approach with static credentials from Vault
        # In production, you should use the AWS credential helper or implement
        # the full Roles Anywhere signing process
        
        # This approach requires the aws_signing_helper or custom implementation
        # For simplicity, we'll return credentials that can be set via environment
        raise NotImplementedError(
            "Direct boto3 Roles Anywhere authentication requires aws_signing_helper binary. "
            "Please install it from: https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html "
            "or use standard AWS credentials via environment variables."
        )


class S3Client:
    """AWS S3 client wrapper with Roles Anywhere authentication for file storage operations."""

    def __init__(
        self,
        region: str,
        bucket_name: str,
        trust_anchor_arn: str,
        profile_arn: str,
        role_arn: str,
        certificate_pem: str,
        private_key_pem: str,
        session_duration: int = 3600
    ):
        """Initialize S3 client with AWS Roles Anywhere authentication.

        Args:
            region: AWS region
            bucket_name: S3 bucket name for file storage
            trust_anchor_arn: ARN of the AWS Roles Anywhere trust anchor
            profile_arn: ARN of the AWS Roles Anywhere profile
            role_arn: ARN of the IAM role to assume
            certificate_pem: X.509 certificate in PEM format
            private_key_pem: Private key in PEM format
            session_duration: Session duration in seconds (default: 3600)
        """
        self.region = region
        self.bucket_name = bucket_name
        self.trust_anchor_arn = trust_anchor_arn
        self.profile_arn = profile_arn
        self.role_arn = role_arn
        self.session_duration = session_duration
        
        # Store certificate and key
        self.certificate_pem = certificate_pem
        self.private_key_pem = private_key_pem
        
        # Initialize credential provider
        self.credential_provider = RolesAnywhereCredentialProvider(
            certificate_pem=certificate_pem,
            private_key_pem=private_key_pem,
            trust_anchor_arn=trust_anchor_arn,
            profile_arn=profile_arn,
            role_arn=role_arn,
            region=region,
            session_duration=session_duration
        )
        
        # Initialize S3 client with Roles Anywhere credentials
        try:
            self.client = self._create_s3_client()
            self._ensure_bucket()
            logger.info(f"S3 client initialized successfully (region: {region}, bucket: {bucket_name})")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise

    def _create_s3_client(self):
        """Create S3 client with Roles Anywhere credentials.
        
        Returns:
            boto3 S3 client with temporary credentials
        """
        try:
            # Get temporary credentials
            creds = self.credential_provider.get_credentials()
            
            # Create S3 client with temporary credentials
            s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'],
                config=Config(signature_version='s3v4')
            )
            
            logger.info("Successfully obtained temporary credentials via Roles Anywhere")
            return s3_client
        except Exception as e:
            logger.error(f"Failed to create S3 client with Roles Anywhere: {e}")
            raise

    def _ensure_bucket(self) -> None:
        """Ensure the bucket exists and is accessible."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"Bucket exists and is accessible: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Bucket does not exist: {self.bucket_name}")
                raise RuntimeError(f"S3 bucket '{self.bucket_name}' does not exist")
            elif error_code == '403':
                logger.error(f"Access denied to bucket: {self.bucket_name}")
                raise RuntimeError(f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                logger.error(f"Error accessing bucket: {e}")
                raise

    def _get_object_path(self, username: str, file_path: str) -> str:
        """Construct object path in S3.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            Full object path in S3
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
        """Upload a file to S3.

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
                Bucket=self.bucket_name,
                Key=object_path,
                Body=file_data,
                ContentType=content_type,
                ContentLength=file_size
            )
            logger.info(f"Uploaded file: {object_path} ({file_size} bytes)")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file {object_path}: {e}")
            return False

    def download_file(self, username: str, file_path: str) -> Optional[bytes]:
        """Download a file from S3.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            File data as bytes, or None if not found
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_path
            )
            data = response['Body'].read()
            logger.debug(f"Downloaded file: {object_path}")
            return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File not found: {object_path}")
            else:
                logger.error(f"Failed to download file {object_path}: {e}")
            return None

    def get_file_stream(self, username: str, file_path: str):
        """Get a file stream from S3.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            File stream object, or None if not found
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_path
            )
            logger.debug(f"Retrieved file stream: {object_path}")
            return response['Body']
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File not found: {object_path}")
            else:
                logger.error(f"Failed to get file stream {object_path}: {e}")
            return None

    def delete_file(self, username: str, file_path: str) -> bool:
        """Delete a file from S3.

        Args:
            username: Username for namespace
            file_path: Relative file path within user's space

        Returns:
            True if successful
        """
        object_path = self._get_object_path(username, file_path)
        
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_path
            )
            logger.info(f"Deleted file: {object_path}")
            return True
        except ClientError as e:
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
            if recursive:
                return self._list_recursive(base_prefix)
            else:
                return self._list_non_recursive(base_prefix)
                
        except ClientError as e:
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
    
    def _list_recursive(self, base_prefix: str) -> List[Dict[str, Any]]:
        """List objects recursively.
        
        Args:
            base_prefix: Base prefix to list from
            
        Returns:
            List of file dictionaries
        """
        files = []
        paginator = self.client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=base_prefix):
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                if obj['Key'].endswith(DIRECTORY_MARKER):
                    continue
                
                relative_path = self._get_relative_path(obj['Key'], base_prefix)
                if relative_path:
                    files.append({
                        'name': relative_path,
                        'size': obj['Size'],
                        'mtime': int(obj['LastModified'].timestamp()),
                        'type': 'file'
                    })
        
        return files
    
    def _list_non_recursive(self, base_prefix: str) -> List[Dict[str, Any]]:
        """List objects non-recursively (current directory only).
        
        Args:
            base_prefix: Base prefix to list from
            
        Returns:
            List of file and directory dictionaries
        """
        files = []
        seen_dirs = set()
        paginator = self.client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=base_prefix, Delimiter='/'):
            # Add subdirectories from CommonPrefixes
            if 'CommonPrefixes' in page:
                for prefix_info in page['CommonPrefixes']:
                    dir_path = prefix_info['Prefix']
                    relative_path = self._get_relative_path(dir_path, base_prefix)
                    if relative_path:
                        dir_name = relative_path.rstrip('/')
                        # Skip .bin directory - only accessible via bin endpoint
                        if dir_name != '.bin' and dir_name not in seen_dirs:
                            seen_dirs.add(dir_name)
                            files.append({
                                'name': dir_name,
                                'size': 0,
                                'mtime': 0,
                                'type': 'directory'
                            })
            
            # Add files in current directory
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].endswith(DIRECTORY_MARKER):
                        continue
                    
                    relative_path = self._get_relative_path(obj['Key'], base_prefix)
                    if relative_path and '/' not in relative_path:
                        files.append({
                            'name': relative_path,
                            'size': obj['Size'],
                            'mtime': int(obj['LastModified'].timestamp()),
                            'type': 'file'
                        })
        
        return files

    def _get_relative_path(self, object_key: str, base_prefix: str) -> str:
        """Extract relative path from object key.
        
        Args:
            object_key: Full object key
            base_prefix: Base prefix to remove
            
        Returns:
            Relative path or empty string if not valid
        """
        if not object_key.startswith(base_prefix):
            return ''
        return object_key[len(base_prefix):]

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
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
            
            return total_size
        except ClientError as e:
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
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=object_path
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
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
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1
            )
            return response.get('KeyCount', 0) > 0
        except ClientError as e:
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
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=object_path
            )
            return response['ContentLength']
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
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
            self.client.copy_object(
                Bucket=self.bucket_name,
                Key=dest_object,
                CopySource={'Bucket': self.bucket_name, 'Key': src_object}
            )
            # Delete the original
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=src_object
            )
            logger.info(f"Moved file from {src_object} to {dest_object}")
            return True
        except ClientError as e:
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
            moved_count = 0
            paginator = self.client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=src_prefix):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    # Skip directory markers
                    if obj['Key'].endswith(DIRECTORY_MARKER):
                        continue
                    
                    # Calculate relative path within the directory
                    relative_path = obj['Key'][len(src_prefix):]
                    
                    # Construct destination path in bin
                    dest_object = self._get_object_path(username, f"{bin_prefix}/{relative_path}")
                    
                    # Copy to bin
                    self.client.copy_object(
                        Bucket=self.bucket_name,
                        Key=dest_object,
                        CopySource={'Bucket': self.bucket_name, 'Key': obj['Key']}
                    )
                    
                    # Delete original
                    self.client.delete_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    moved_count += 1
            
            logger.info(f"Moved directory {src_prefix} with {moved_count} files to {bin_prefix}")
            return moved_count > 0
            
        except ClientError as e:
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
            restored_count = 0
            paginator = self.client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=bin_prefix):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    # Skip directory markers
                    if obj['Key'].endswith(DIRECTORY_MARKER):
                        continue
                    
                    # Calculate relative path within the bin directory
                    relative_path = obj['Key'][len(bin_prefix):]
                    
                    # Construct destination path
                    dest_object = self._get_object_path(username, f"{original_path}/{relative_path}")
                    
                    # Copy back to original location
                    self.client.copy_object(
                        Bucket=self.bucket_name,
                        Key=dest_object,
                        CopySource={'Bucket': self.bucket_name, 'Key': obj['Key']}
                    )
                    
                    # Delete from bin
                    self.client.delete_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    restored_count += 1
            
            logger.info(f"Restored directory from {bin_prefix} with {restored_count} files to {original_path}")
            return restored_count > 0
            
        except ClientError as e:
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
            paginator = self.client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' not in page:
                    continue
                    
                # Delete objects in batches
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects_to_delete:
                    self.client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
            
            logger.info(f"Deleted directory: {prefix}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete directory {prefix}: {e}")
            return False
