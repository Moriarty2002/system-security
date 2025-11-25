import os
import logging
from flask import Blueprint, jsonify, request, send_from_directory, abort, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import func

from ..auth import authenticate_user
from ..models import db, User, BinItem
from ..utils import get_user_usage_bytes, get_user_files_list, ensure_user_directory, move_to_bin, get_user_bin_items, restore_from_bin, permanently_delete_from_bin, cleanup_expired_bin_items

logger = logging.getLogger(__name__)
files_bp = Blueprint('files', __name__)


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file for the authenticated user."""
    try:
        username, user = authenticate_user()

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
        user_dir = ensure_user_directory(username, current_app.config['STORAGE_DIR'])

        # Get optional subdirectory path
        subpath = request.form.get('path', '').strip()
        if subpath.startswith('/') or '..' in subpath:
            return jsonify({'error': 'invalid path'}), 400

        upload_dir = os.path.join(user_dir, subpath) if subpath else user_dir
        os.makedirs(upload_dir, exist_ok=True)

        # Prevent uploading outside user directory
        if not os.path.abspath(upload_dir).startswith(os.path.abspath(user_dir) + os.sep if subpath else os.path.abspath(user_dir)):
            return jsonify({'error': 'path traversal detected'}), 403

        # Compute file size
        file_stream = file.stream
        file_stream.seek(0, os.SEEK_END)
        file_size = file_stream.tell()
        file_stream.seek(0)

        # Lock the user row and check quota inside a transaction
        # Acquire a FOR UPDATE lock to avoid concurrent quota races
        db_user = db.session.query(User).with_for_update().get(username)
        if not db_user:
            logger.error(f"User {username} not found during upload")
            abort(403, description='Unknown user')

        current_usage = get_user_usage_bytes(username, current_app.config['STORAGE_DIR'])
        if current_usage + file_size > (db_user.quota or 0):
            logger.warning(f"User {username} exceeded quota: current={current_usage}, file_size={file_size}, quota={db_user.quota}")
            return jsonify({'error': 'quota exceeded'}), 403

        # Save file to destination
        save_path = os.path.join(upload_dir, filename)
        try:
            # Ensure stream pointer at start
            try:
                file_stream.seek(0)
            except Exception:
                pass

            with open(save_path, 'wb') as out_f:
                while True:
                    chunk = file_stream.read(8192)
                    if not chunk:
                        break
                    out_f.write(chunk)
                out_f.flush()
                try:
                    os.fsync(out_f.fileno())
                except Exception:
                    # fsync may not be available on all platforms/FS; ignore if it fails
                    pass
        except Exception as e:
            # If saving fails, return an error so front-end can react
            logger.error(f"Failed to save file {filename} for user {username}: {str(e)}")
            return jsonify({'error': 'failed to save file', 'detail': str(e)}), 500

        # No DB metadata to update for file uploads; commit to release locks
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

    files = get_user_files_list(target, current_app.config['STORAGE_DIR'], subpath)
    usage = get_user_usage_bytes(target, current_app.config['STORAGE_DIR'])

    quota = None
    if target == username:
        quota = user.quota
    else:
        target_user = User.query.get(target)
        quota = target_user.quota if target_user else 0

    return jsonify({
        'files': files,
        'usage': usage,
        'quota': quota,
        'user': target,
        'path': subpath
    })


@files_bp.route('/users', methods=['GET'])
def list_users_for_moderator():
    """List all usernames (moderator only)."""
    username, user = authenticate_user()

    # Only moderators can access this endpoint
    if getattr(user, 'role', '') != 'moderator':
        abort(403, description='only moderators can list users')

    users = User.query.order_by(User.username).all()
    usernames = [u.username for u in users]

    return jsonify({'users': usernames})


@files_bp.route('/files/<filename>', methods=['GET'])
def download_file(filename):
    """Download a file."""
    username, user = authenticate_user()

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
        abort(400, description='invalid path')

    # Construct full path
    full_item_path = os.path.join(subpath, filename) if subpath else filename

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)
    full_path = os.path.join(user_dir, full_item_path)

    # Prevent path traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(user_dir) + os.sep):
        abort(403, description='path traversal detected')

    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return jsonify({'error': 'file not found'}), 404

    return send_from_directory(user_dir, full_item_path, as_attachment=True)


@files_bp.route('/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Move a file or directory to bin."""
    username, user = authenticate_user()

    # Prevent admin users from deleting files
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to delete file")
        abort(403, description='admins cannot delete files')

        # Deletions only allowed by owner (admins and moderators cannot delete)
    target = request.args.get('user') or username
    if target != username:
        abort(403, description='only owner can delete files')

    # Get path from query parameter
    subpath = request.args.get('path', '').strip()
    if subpath.startswith('/') or '..' in subpath:
        abort(400, description='invalid path')

    # Construct full path
    full_item_path = os.path.join(subpath, filename) if subpath else filename

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)
    full_path = os.path.join(user_dir, full_item_path)

    # Prevent path traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(user_dir) + os.sep):
        abort(403, description='path traversal detected')

    if not os.path.exists(full_path):
        return jsonify({'error': 'file not found'}), 404

    # Calculate size for bin tracking
    if os.path.isdir(full_path):
        # Calculate directory size recursively
        total_size = 0
        for root, dirs, files in os.walk(full_path):
            for name in files:
                total_size += os.path.getsize(os.path.join(root, name))
        item_type = 'directory'
        size = total_size
    else:
        item_type = 'file'
        size = os.path.getsize(full_path)

    # Move to bin
    try:
        bin_path = move_to_bin(target, full_item_path, current_app.config['STORAGE_DIR'])
        
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
            return jsonify({'error': 'invalid path'}), 400

        user_dir = ensure_user_directory(username, current_app.config['STORAGE_DIR'])
        full_path = os.path.join(user_dir, dirname)

        # Prevent creating outside user directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(user_dir) + os.sep):
            return jsonify({'error': 'path traversal detected'}), 403

        if os.path.exists(full_path):
            return jsonify({'error': 'directory already exists'}), 409

        os.makedirs(full_path, exist_ok=True)

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

    # Prevent admin users from restoring from bin
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to restore from bin")
        abort(403, description='admins cannot restore from bin')

    try:
        success = restore_from_bin(item_id, username, current_app.config['STORAGE_DIR'])
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

    # Prevent admin users from permanently deleting from bin
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to permanently delete from bin")
        abort(403, description='admins cannot permanently delete from bin')

    try:
        success = permanently_delete_from_bin(item_id, username, current_app.config['STORAGE_DIR'])
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

    if getattr(user, 'role', '') != 'admin':
        abort(403, description='only admins can cleanup bin')

    try:
        cleaned_count = cleanup_expired_bin_items(current_app.config['STORAGE_DIR'])
        logger.info(f"Admin {username} cleaned up {cleaned_count} expired bin items")
        return jsonify({'status': 'cleanup completed', 'items_cleaned': cleaned_count})
    except Exception as e:
        logger.error(f"Failed to cleanup bin: {str(e)}")
        return jsonify({'error': 'cleanup failed', 'detail': str(e)}), 500