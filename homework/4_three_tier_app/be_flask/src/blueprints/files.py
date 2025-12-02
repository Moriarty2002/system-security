import os
import io
import logging
from flask import Blueprint, jsonify, request, send_file, abort, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import func

from ..keycloak_auth import authenticate_user, get_admin_keycloak_auth
from ..models import db, UserProfile, BinItem
from ..utils_minio import (
    get_user_usage_bytes,
    get_user_files_list,
    move_to_bin,
    get_user_bin_items,
    restore_from_bin,
    permanently_delete_from_bin,
    cleanup_expired_bin_items,
    get_directory_size
)

logger = logging.getLogger(__name__)
files_bp = Blueprint('files', __name__)

# Constants
ERROR_INVALID_PATH = 'invalid path'


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file for the authenticated user."""
    try:
        username, user = authenticate_user()
        minio_client = current_app.config['MINIO_CLIENT']

        # Prevent admin and moderator users from uploading files
        user_role = getattr(user, 'role', 'user')
        if user_role not in ['user']:
            logger.warning(f"{user_role.title()} user {username} attempted to upload file")
            return jsonify({'error': f'{user_role}s cannot upload files'}), 403

        if 'file' not in request.files:
            logger.warning(f"User {username} attempted upload without file")
            return jsonify({'error': 'no file part'}), 400

        file = request.files['file']
        filename_raw = file.filename or ''
        if filename_raw == '':
            logger.warning(f"User {username} attempted upload with empty filename")
            return jsonify({'error': 'no selected file'}), 400

        filename = secure_filename(filename_raw)

        # Get optional subdirectory path
        subpath = request.form.get('path', '').strip()
        if subpath.startswith('/') or '..' in subpath:
            return jsonify({'error': ERROR_INVALID_PATH}), 400

        # Construct full file path (use forward slashes for MinIO)
        if subpath:
            # Clean up subpath and ensure forward slashes
            subpath = subpath.strip('/').replace('\\', '/')
            full_path = f"{subpath}/{filename}"
        else:
            full_path = filename

        # Compute file size
        file_stream = file.stream
        file_stream.seek(0, os.SEEK_END)
        file_size = file_stream.tell()
        file_stream.seek(0)

        # Lock the user row and check quota inside a transaction
        # Use the user object already fetched by authenticate_user
        db_user = user
        if not db_user:
            logger.error(f"User {username} not found during upload - user object is None")
            abort(403, description='Unknown user')
        
        logger.info(f"Upload by {username}, keycloak_id={db_user.keycloak_id}, quota={db_user.quota}")

        current_usage = get_user_usage_bytes(username, minio_client)
        if current_usage + file_size > (db_user.quota or 0):
            logger.warning(f"User {username} exceeded quota: current={current_usage}, file_size={file_size}, quota={db_user.quota}")
            return jsonify({'error': 'quota exceeded'}), 403

        # Upload to MinIO
        try:
            file_stream.seek(0)
            success = minio_client.upload_file(
                username,
                full_path,
                file_stream,
                file_size,
                content_type=file.content_type or 'application/octet-stream'
            )
            
            if not success:
                raise RuntimeError("MinIO upload failed")
                
        except Exception as e:
            logger.error(f"Failed to upload file {filename} for user {username}: {str(e)}")
            return jsonify({'error': 'failed to save file', 'detail': str(e)}), 500

        # Commit to release locks
        db.session.commit()

        logger.info(f"User {username} successfully uploaded file {filename} ({file_size} bytes)")
        return jsonify({'status': 'ok', 'filename': filename, 'size': file_size})
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({'error': 'internal server error'}), 500


@files_bp.route('/files', methods=['GET'])
def list_files():
    """List files for user (or another user if moderator)."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    # Prevent admin users from listing files
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to list files")
        abort(403, description='admins cannot access file listings')

    # Allow moderators to view other users' file lists via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(user, 'role', '') != 'moderator':
        abort(403, description='insufficient role to view other users')

    subpath = request.args.get('path', '').strip()
    if subpath.startswith('/') or '..' in subpath:
        abort(400, description='invalid path')

    files = get_user_files_list(target, minio_client, subpath)
    usage = get_user_usage_bytes(target, minio_client)

    quota = None
    if target == username:
        quota = user.quota
    else:
        # For moderators viewing other users, need to get user by username via Keycloak
        try:
            kc = get_admin_keycloak_auth()
            if kc:
                # Search for user by username in Keycloak
                kc_users = kc.admin_search_users(target)
                if kc_users and len(kc_users) > 0:
                    target_keycloak_id = kc_users[0].get('id')
                    target_user = UserProfile.query.filter_by(keycloak_id=target_keycloak_id).first()
                    quota = target_user.quota if target_user else 0
                else:
                    quota = 0
            else:
                quota = 0
        except Exception as e:
            logger.warning(f"Failed to get quota for user {target}: {e}")
            quota = 0

    return jsonify({
        'files': files,
        'usage': usage,
        'quota': quota,
        'user': target,
        'path': subpath
    })


@files_bp.route('/files/<filename>', methods=['GET'])
def download_file(filename):
    """Download a file."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    # Prevent admin users from downloading files
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to download file")
        abort(403, description='admins cannot download files')

    # Allow moderators to download other users' files via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(user, 'role', '') != 'moderator':
        abort(403, description='insufficient role to download other users files')

    # Get path from query parameter
    subpath = request.args.get('path', '').strip()
    if subpath.startswith('/') or '..' in subpath:
        abort(400, description=ERROR_INVALID_PATH)

    # Construct full path (use forward slashes for MinIO)
    if subpath:
        subpath = subpath.strip('/').replace('\\', '/')
        full_item_path = f"{subpath}/{filename}"
    else:
        full_item_path = filename

    # Get file from MinIO
    file_data = minio_client.download_file(target, full_item_path)
    
    if file_data is None:
        return jsonify({'error': 'file not found'}), 404

    # Send file as attachment
    return send_file(
        io.BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream'
    )


@files_bp.route('/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Move a file or directory to bin."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    # Prevent admin users from deleting files
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to delete file")
        abort(403, description='admins cannot delete files')

    # Deletions only allowed by owner
    target = request.args.get('user') or username
    if target != username:
        abort(403, description='only owner can delete files')

    # Get path from query parameter
    subpath = request.args.get('path', '').strip()
    if subpath.startswith('/') or '..' in subpath:
        abort(400, description=ERROR_INVALID_PATH)

    # Construct full path (use forward slashes for MinIO)
    if subpath:
        subpath = subpath.strip('/').replace('\\', '/')
        full_item_path = f"{subpath}/{filename}"
    else:
        full_item_path = filename

    # Check if it's a directory or file
    is_directory = minio_client.is_directory(target, full_item_path)
    is_file = minio_client.file_exists(target, full_item_path)
    
    if not is_directory and not is_file:
        return jsonify({'error': 'file not found'}), 404

    # Calculate size
    if is_directory:
        size = get_directory_size(target, full_item_path, minio_client)
        item_type = 'directory'
    else:
        size = minio_client.get_file_size(target, full_item_path) or 0
        item_type = 'file'

    # Move to bin
    try:
        bin_path = move_to_bin(target, full_item_path, minio_client, is_directory=is_directory)
        
        # Record in database
        bin_item = BinItem(
            username=target,
            original_path=full_item_path,
            item_type=item_type,
            size=size,
            bin_path=bin_path
        )
        db.session.add(bin_item)
        db.session.commit()
        
        logger.info(f"User {username} moved {item_type} {full_item_path} to bin")
        return jsonify({'status': 'moved to bin', 'filename': filename, 'user': target, 'item_type': item_type})
    except Exception as e:
        logger.error(f"Failed to move {full_item_path} to bin for user {username}: {str(e)}")
        return jsonify({'error': 'failed to move to bin', 'detail': str(e)}), 500


@files_bp.route('/mkdir', methods=['POST'])
def create_directory():
    """Create a directory for the authenticated user."""
    try:
        username, user = authenticate_user()
        minio_client = current_app.config['MINIO_CLIENT']

        # Prevent admin and moderator users from creating directories
        user_role = getattr(user, 'role', 'user')
        if user_role not in ['user']:
            logger.warning(f"{user_role.title()} user {username} attempted to create directory")
            return jsonify({'error': f'{user_role}s cannot create directories'}), 403

        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'path required'}), 400

        dirname = data['path'].strip()
        if not dirname or dirname.startswith('/') or '..' in dirname:
            return jsonify({'error': ERROR_INVALID_PATH}), 400

        # In MinIO, directories don't really exist - they're implicit from object paths
        # We'll create a .directory marker file to represent the directory
        marker_path = f"{dirname}/.directory" if not dirname.endswith('/') else f"{dirname}.directory"
        
        # Check if it already exists
        if minio_client.file_exists(username, marker_path):
            return jsonify({'error': 'directory already exists'}), 409

        # Create directory marker
        marker_data = io.BytesIO(b'')
        success = minio_client.upload_file(
            username,
            marker_path,
            marker_data,
            0,
            content_type='application/x-directory'
        )

        if not success:
            return jsonify({'error': 'failed to create directory'}), 500

        logger.info(f"User {username} created directory {dirname}")
        return jsonify({'status': 'ok', 'path': dirname})
    except Exception as e:
        logger.error(f"Unexpected error in create_directory: {str(e)}")
        return jsonify({'error': 'internal server error'}), 500


@files_bp.route('/bin', methods=['GET'])
def list_bin():
    """List items in user's bin."""
    username, user = authenticate_user()

    # Prevent admin users from accessing bin
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to access bin")
        abort(403, description='admins cannot access bin')

    bin_items = get_user_bin_items(username)
    return jsonify({'bin_items': bin_items})


@files_bp.route('/bin/<int:item_id>/restore', methods=['POST'])
def restore_from_bin_endpoint(item_id):
    """Restore an item from bin."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    # Prevent admin users from restoring from bin
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to restore from bin")
        abort(403, description='admins cannot restore from bin')

    try:
        success = restore_from_bin(item_id, username, minio_client)
        if not success:
            return jsonify({'error': 'item not found or access denied'}), 404
        
        logger.info(f"User {username} restored item {item_id} from bin")
        return jsonify({'status': 'restored', 'item_id': item_id})
    except Exception as e:
        logger.error(f"Failed to restore item {item_id} for user {username}: {str(e)}")
        return jsonify({'error': 'failed to restore', 'detail': str(e)}), 500


@files_bp.route('/bin/<int:item_id>', methods=['DELETE'])
def permanently_delete_from_bin_endpoint(item_id):
    """Permanently delete an item from bin."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    # Prevent admin users from permanently deleting from bin
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to permanently delete from bin")
        abort(403, description='admins cannot permanently delete from bin')

    try:
        success = permanently_delete_from_bin(item_id, username, minio_client)
        if not success:
            return jsonify({'error': 'item not found or access denied'}), 404
        
        logger.info(f"User {username} permanently deleted item {item_id} from bin")
        return jsonify({'status': 'permanently deleted', 'item_id': item_id})
    except Exception as e:
        logger.error(f"Failed to permanently delete item {item_id} for user {username}: {str(e)}")
        return jsonify({'error': 'failed to delete', 'detail': str(e)}), 500


@files_bp.route('/bin/cleanup', methods=['POST'])
def cleanup_bin():
    """Clean up expired bin items (admin only)."""
    username, user = authenticate_user()
    minio_client = current_app.config['MINIO_CLIENT']

    if getattr(user, 'role', '') != 'admin':
        abort(403, description='only admins can cleanup bin')

    try:
        cleaned_count = cleanup_expired_bin_items(minio_client)
        logger.info(f"Admin {username} cleaned up {cleaned_count} expired bin items")
        return jsonify({'status': 'cleanup completed', 'items_cleaned': cleaned_count})
    except Exception as e:
        logger.error(f"Failed to cleanup bin: {str(e)}")
        return jsonify({'error': 'cleanup failed', 'detail': str(e)}), 500