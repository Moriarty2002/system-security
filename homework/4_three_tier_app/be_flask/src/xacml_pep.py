"""
XACML Policy Enforcement Point (PEP)

This module implements the Policy Enforcement Point that intercepts
requests and enforces authorization decisions from the PDP.

It provides decorators and functions to protect Flask endpoints
with XACML-based access control.
"""

import logging
from functools import wraps
from typing import Optional, Callable
from flask import abort, request

from .xacml_pdp import check_authorization

logger = logging.getLogger(__name__)


def enforce_xacml(action: str, 
                 resource_owner_param: Optional[str] = None,
                 target_role_param: Optional[str] = None):
    """
    Decorator to enforce XACML authorization on Flask endpoints.
    
    This decorator intercepts requests and checks authorization using XACML
    policies before allowing the endpoint to execute.
    
    Args:
        action: The action being performed (e.g., 'upload', 'download', 'list')
        resource_owner_param: Name of the parameter containing resource owner
                             If None, uses authenticated username as owner
        target_role_param: Name of the parameter containing target user's role
                          Used for admin operations on specific users
    
    Returns:
        Decorated function
    
    Example:
        @enforce_xacml('upload')
        def upload_file():
            # Only executes if XACML permits
            pass
            
        @enforce_xacml('list', resource_owner_param='target_user')
        def list_files(target_user):
            # Checks if user can list target_user's files
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Import here to avoid circular dependency
            from .auth import authenticate_user
            
            # Get authenticated user info
            username, user, role = authenticate_user()
            
            # Determine resource owner
            resource_owner = None
            if resource_owner_param:
                # Get from function parameters
                resource_owner = kwargs.get(resource_owner_param)
                
                # Try to get from query parameters if not in path
                if resource_owner is None:
                    resource_owner = request.args.get('user')
            
            # If no explicit resource owner, default to authenticated user
            if resource_owner is None:
                resource_owner = username
            
            # Determine target role if needed
            target_role = None
            if target_role_param:
                target_role = kwargs.get(target_role_param)
            
            # Check authorization with XACML
            permitted = check_authorization(
                username=username,
                role=role,
                action=action,
                resource_owner=resource_owner,
                target_role=target_role
            )
            
            if not permitted:
                logger.warning(
                    f"XACML denied access: user={username}, role={role}, "
                    f"action={action}, resource_owner={resource_owner}"
                )
                abort(403, description='Access denied by authorization policy')
            
            # Authorization passed, execute endpoint
            logger.debug(
                f"XACML permitted access: user={username}, role={role}, "
                f"action={action}, resource_owner={resource_owner}"
            )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_xacml_permission(username: str, role: str, action: str,
                           resource_owner: Optional[str] = None,
                           target_role: Optional[str] = None) -> bool:
    """
    Directly check XACML permission without decorator.
    
    Useful for programmatic authorization checks within business logic.
    
    Args:
        username: Subject username
        role: Subject role
        action: Action to perform
        resource_owner: Resource owner (optional)
        target_role: Target user's role (optional)
        
    Returns:
        True if permitted, False otherwise
    
    Example:
        if check_xacml_permission(username, role, 'delete', resource_owner=file_owner):
            delete_file()
        else:
            return error_response()
    """
    return check_authorization(
        username=username,
        role=role,
        action=action,
        resource_owner=resource_owner,
        target_role=target_role
    )


def require_xacml_permission(username: str, role: str, action: str,
                            resource_owner: Optional[str] = None,
                            target_role: Optional[str] = None) -> None:
    """
    Require XACML permission or abort with 403.
    
    Similar to check_xacml_permission but aborts on failure.
    
    Args:
        username: Subject username
        role: Subject role
        action: Action to perform
        resource_owner: Resource owner (optional)
        target_role: Target user's role (optional)
        
    Raises:
        403: If permission is denied
    
    Example:
        require_xacml_permission(username, role, 'update-quota', target_role=target_user_role)
        # Continues only if permitted
    """
    if not check_xacml_permission(username, role, action, resource_owner, target_role):
        logger.warning(
            f"XACML denied access: user={username}, role={role}, "
            f"action={action}, resource_owner={resource_owner}"
        )
        abort(403, description='Access denied by authorization policy')
