import os
import logging
from flask import Blueprint, jsonify, request, send_from_directory, abort, current_app
from werkzeug.utils import secure_filename

from ..auth import authenticate_user
from ..models import db, User
from ..utils import get_user_usage_bytes, get_user_files_list, ensure_user_directory

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


@files_bp.route('/files/<path:filename>', methods=['GET'])
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

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)
    full_path = os.path.join(user_dir, filename)

    # Prevent path traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(user_dir) + os.sep):
        abort(403, description='path traversal detected')

    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return jsonify({'error': 'file not found'}), 404

    return send_from_directory(user_dir, filename, as_attachment=True)


@files_bp.route('/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file or empty directory."""
    username, user = authenticate_user()

    # Prevent admin users from deleting files
    if getattr(user, 'role', 'user') == 'admin':
        logger.warning(f"Admin user {username} attempted to delete file")
        abort(403, description='admins cannot delete files')

        # Deletions only allowed by owner (admins and moderators cannot delete)
    target = request.args.get('user') or username
    if target != username:
        abort(403, description='only owner can delete files')

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)
    full_path = os.path.join(user_dir, filename)

    # Prevent path traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(user_dir) + os.sep):
        abort(403, description='path traversal detected')

    if not os.path.exists(full_path):
        return jsonify({'error': 'file not found'}), 404

    if os.path.isdir(full_path):
        try:
            os.rmdir(full_path)  # Only removes empty directories
        except OSError:
            return jsonify({'error': 'directory not empty'}), 400
    else:
        os.remove(full_path)

    return jsonify({'status': 'deleted', 'filename': filename, 'user': target})


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