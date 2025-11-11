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
        save_path = os.path.join(user_dir, filename)
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
    """List files for user (or another user if moderator/admin)."""
    username, user = authenticate_user()

    # Allow moderators/admins to view other users' file lists via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(user, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to view other users')

    files = get_user_files_list(target, current_app.config['STORAGE_DIR'])
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
        'user': target
    })


@files_bp.route('/files/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download a file."""
    username, user = authenticate_user()

    # Allow moderators/admins to download other users' files via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(user, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to download other users files')

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)

    # Prevent path traversal by using send_from_directory
    if not os.path.exists(os.path.join(user_dir, filename)):
        return jsonify({'error': 'file not found'}), 404

    return send_from_directory(user_dir, filename, as_attachment=True)


@files_bp.route('/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file."""
    username, user = authenticate_user()

    # Deletions only allowed by owner or admin (moderator cannot delete)
    target = request.args.get('user') or username
    if target != username and getattr(user, 'role', 'user') != 'admin':
        abort(403, description='only owner or admin can delete files')

    user_dir = os.path.join(current_app.config['STORAGE_DIR'], target)
    path = os.path.join(user_dir, filename)

    if not os.path.exists(path):
        return jsonify({'error': 'file not found'}), 404

    os.remove(path)
    return jsonify({'status': 'deleted', 'filename': filename, 'user': target})


@files_bp.route('/users', methods=['GET'])
def list_usernames():
    """Return a simple list of usernames. Allowed for admin and moderator roles."""
    username, user = authenticate_user()

    if getattr(user, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to list users')

    users = User.query.order_by(User.username).all()
    return jsonify({'users': [u.username for u in users]})