"""
XACML Policy Decision Point (PDP)

This module implements a simplified XACML 3.0 PDP that evaluates access control
policies defined in XML format. It processes authorization requests and returns
permit/deny decisions based on the configured policies.

The PDP evaluates:
- Subject attributes (username, role)
- Resource attributes (resource-owner, target-role)
- Action attributes (action type)
- Environment attributes (optional, for time-based policies)

Policy Combining Algorithm: deny-overrides
Rule Combining Algorithm: deny-overrides
"""

import os
import logging
from typing import Dict, Any, Optional
from xml.etree import ElementTree as ET
from enum import Enum

logger = logging.getLogger(__name__)


class Decision(Enum):
    """XACML decision types"""
    PERMIT = "Permit"
    DENY = "Deny"
    NOT_APPLICABLE = "NotApplicable"
    INDETERMINATE = "Indeterminate"


class XACMLRequest:
    """Represents an XACML authorization request"""
    
    def __init__(self, subject: Dict[str, Any], resource: Dict[str, Any], 
                 action: str, environment: Optional[Dict[str, Any]] = None):
        """
        Initialize XACML request.
        
        Args:
            subject: Subject attributes (username, role)
            resource: Resource attributes (resource-owner, target-role, etc.)
            action: Action being performed
            environment: Environment attributes (optional)
        """
        self.subject = subject
        self.resource = resource
        self.action = action
        self.environment = environment or {}
        
    def get_subject_attribute(self, attr_name: str) -> Optional[str]:
        """Get subject attribute value"""
        return self.subject.get(attr_name)
    
    def get_resource_attribute(self, attr_name: str) -> Optional[str]:
        """Get resource attribute value"""
        return self.resource.get(attr_name)
    
    def get_action(self) -> str:
        """Get action value"""
        return self.action


class XACMLResponse:
    """Represents an XACML authorization response"""
    
    def __init__(self, decision: Decision, status: str = "OK", 
                 obligations: Optional[list] = None, advice: Optional[list] = None):
        """
        Initialize XACML response.
        
        Args:
            decision: Authorization decision
            status: Status message
            obligations: Obligations to be fulfilled (optional)
            advice: Advisory information (optional)
        """
        self.decision = decision
        self.status = status
        self.obligations = obligations or []
        self.advice = advice or []
        
    def is_permitted(self) -> bool:
        """Check if request is permitted"""
        return self.decision == Decision.PERMIT


class PolicyDecisionPoint:
    """
    XACML Policy Decision Point (PDP)
    
    Evaluates authorization requests against XACML policies.
    Implements deny-overrides combining algorithm.
    """
    
    # XACML 3.0 namespace
    XACML_NS = {'xacml': 'urn:oasis:names:tc:xacml:3.0:core:schema:wd-17'}
    
    def __init__(self, policy_file: str):
        """
        Initialize PDP with policy file.
        
        Args:
            policy_file: Path to XACML policy XML file
        """
        self.policy_file = policy_file
        self.policy_tree = None
        self.policy_root = None
        self._load_policies()
        
    def _load_policies(self):
        """Load and parse XACML policy file"""
        try:
            if not os.path.exists(self.policy_file):
                raise FileNotFoundError(f"Policy file not found: {self.policy_file}")
                
            self.policy_tree = ET.parse(self.policy_file)
            self.policy_root = self.policy_tree.getroot()
            logger.info(f"Successfully loaded XACML policies from {self.policy_file}")
            
        except Exception as e:
            logger.error(f"Failed to load XACML policies: {e}")
            raise
    
    def evaluate(self, request: XACMLRequest) -> XACMLResponse:
        """
        Evaluate an authorization request against policies.
        
        Args:
            request: XACML authorization request
            
        Returns:
            XACML response with decision
        """
        try:
            # Find all policies
            policies = self.policy_root.findall('.//xacml:Policy', self.XACML_NS)
            
            if not policies:
                logger.warning("No policies found in policy file")
                return XACMLResponse(Decision.NOT_APPLICABLE, "No policies found")
            
            # Evaluate policies using deny-overrides
            final_decision = Decision.NOT_APPLICABLE
            any_permit = False
            
            for policy in policies:
                policy_decision = self._evaluate_policy(policy, request)
                
                # Deny-overrides: any deny results in deny
                if policy_decision == Decision.DENY:
                    logger.debug(f"Policy {policy.get('PolicyId')} returned DENY")
                    return XACMLResponse(Decision.DENY, "Access denied by policy")
                
                if policy_decision == Decision.PERMIT:
                    any_permit = True
                    logger.debug(f"Policy {policy.get('PolicyId')} returned PERMIT")
            
            # If any policy permits and none deny, permit
            if any_permit:
                final_decision = Decision.PERMIT
                
            return XACMLResponse(final_decision)
            
        except Exception as e:
            logger.error(f"Error evaluating XACML request: {e}")
            return XACMLResponse(Decision.INDETERMINATE, f"Error: {str(e)}")
    
    def _evaluate_policy(self, policy: ET.Element, request: XACMLRequest) -> Decision:
        """
        Evaluate a single policy against request.
        
        Args:
            policy: Policy XML element
            request: XACML request
            
        Returns:
            Decision for this policy
        """
        # Check policy target
        target = policy.find('xacml:Target', self.XACML_NS)
        if target is not None and not self._match_target(target, request):
            return Decision.NOT_APPLICABLE
        
        # Evaluate rules using deny-overrides
        rules = policy.findall('.//xacml:Rule', self.XACML_NS)
        
        if not rules:
            return Decision.NOT_APPLICABLE
        
        any_permit = False
        
        for rule in rules:
            rule_decision = self._evaluate_rule(rule, request)
            
            # Deny-overrides: any deny results in deny
            if rule_decision == Decision.DENY:
                return Decision.DENY
            
            if rule_decision == Decision.PERMIT:
                any_permit = True
        
        return Decision.PERMIT if any_permit else Decision.NOT_APPLICABLE
    
    def _evaluate_rule(self, rule: ET.Element, request: XACMLRequest) -> Decision:
        """
        Evaluate a single rule against request.
        
        Args:
            rule: Rule XML element
            request: XACML request
            
        Returns:
            Decision for this rule
        """
        effect = rule.get('Effect')
        
        # Check rule target
        target = rule.find('xacml:Target', self.XACML_NS)
        if target is not None and not self._match_target(target, request):
            return Decision.NOT_APPLICABLE
        
        # Check rule condition
        condition = rule.find('xacml:Condition', self.XACML_NS)
        if condition is not None and not self._evaluate_condition(condition, request):
            return Decision.NOT_APPLICABLE
        
        # Rule matches, return effect
        return Decision.PERMIT if effect == "Permit" else Decision.DENY
    
    def _match_target(self, target: ET.Element, request: XACMLRequest) -> bool:
        """
        Check if target matches request.
        
        Args:
            target: Target XML element
            request: XACML request
            
        Returns:
            True if target matches
        """
        # Empty target matches everything
        if len(target) == 0:
            return True
        
        any_of_elements = target.findall('xacml:AnyOf', self.XACML_NS)
        
        for any_of in any_of_elements:
            all_of_elements = any_of.findall('xacml:AllOf', self.XACML_NS)
            
            for all_of in all_of_elements:
                if self._match_all_of(all_of, request):
                    return True
        
        return False
    
    def _match_all_of(self, all_of: ET.Element, request: XACMLRequest) -> bool:
        """
        Check if all matches in AllOf element match.
        
        Args:
            all_of: AllOf XML element
            request: XACML request
            
        Returns:
            True if all matches succeed
        """
        matches = all_of.findall('xacml:Match', self.XACML_NS)
        
        for match in matches:
            if not self._evaluate_match(match, request):
                return False
        
        return True
    
    def _evaluate_match(self, match: ET.Element, request: XACMLRequest) -> bool:
        """
        Evaluate a single match element.
        
        Args:
            match: Match XML element
            request: XACML request
            
        Returns:
            True if match succeeds
        """
        # Get attribute value from policy
        attr_value_elem = match.find('xacml:AttributeValue', self.XACML_NS)
        if attr_value_elem is None:
            return False
        expected_value = attr_value_elem.text
        
        # Get attribute designator
        attr_designator = match.find('xacml:AttributeDesignator', self.XACML_NS)
        if attr_designator is None:
            return False
        
        attr_id = attr_designator.get('AttributeId')
        category = attr_designator.get('Category')
        
        # Get actual value from request based on category
        actual_value = None
        
        if 'subject' in category.lower():
            actual_value = request.get_subject_attribute(attr_id)
        elif 'action' in category.lower():
            if attr_id == 'action':
                actual_value = request.get_action()
        elif 'resource' in category.lower():
            actual_value = request.get_resource_attribute(attr_id)
        
        # Compare values (case-sensitive string comparison)
        return actual_value == expected_value
    
    def _evaluate_condition(self, condition: ET.Element, request: XACMLRequest) -> bool:
        """
        Evaluate a condition element.
        
        Args:
            condition: Condition XML element
            request: XACML request
            
        Returns:
            True if condition evaluates to true
        """
        # Find the Apply element
        apply = condition.find('xacml:Apply', self.XACML_NS)
        if apply is None:
            return True
        
        return self._evaluate_apply(apply, request)
    
    def _evaluate_apply(self, apply: ET.Element, request: XACMLRequest) -> bool:
        """
        Evaluate an Apply function.
        
        Args:
            apply: Apply XML element
            request: XACML request
            
        Returns:
            Result of function evaluation
        """
        function_id = apply.get('FunctionId')
        
        # Handle string-equal function
        if 'string-equal' in function_id:
            designators = apply.findall('.//xacml:AttributeDesignator', self.XACML_NS)
            
            if len(designators) >= 2:
                # Get first attribute
                attr1_id = designators[0].get('AttributeId')
                category1 = designators[0].get('Category')
                
                # Get second attribute
                attr2_id = designators[1].get('AttributeId')
                category2 = designators[1].get('Category')
                
                # Get values
                val1 = self._get_attribute_value(attr1_id, category1, request)
                val2 = self._get_attribute_value(attr2_id, category2, request)
                
                return val1 is not None and val1 == val2
        
        # Handle not function
        elif 'function:not' in function_id:
            inner_apply = apply.find('xacml:Apply', self.XACML_NS)
            if inner_apply is not None:
                return not self._evaluate_apply(inner_apply, request)
        
        # Handle or function
        elif 'function:or' in function_id:
            inner_applies = apply.findall('xacml:Apply', self.XACML_NS)
            for inner_apply in inner_applies:
                if self._evaluate_apply(inner_apply, request):
                    return True
            return False
        
        return False
    
    def _get_attribute_value(self, attr_id: str, category: str, request: XACMLRequest) -> Optional[str]:
        """
        Get attribute value from request based on category.
        
        Args:
            attr_id: Attribute identifier
            category: Attribute category
            request: XACML request
            
        Returns:
            Attribute value or None
        """
        if 'subject' in category.lower():
            return request.get_subject_attribute(attr_id)
        elif 'resource' in category.lower():
            return request.get_resource_attribute(attr_id)
        elif 'action' in category.lower():
            if attr_id == 'action':
                return request.get_action()
        
        return None


# Singleton PDP instance
_pdp_instance: Optional[PolicyDecisionPoint] = None


def get_pdp() -> PolicyDecisionPoint:
    """
    Get singleton PDP instance.
    
    Returns:
        PolicyDecisionPoint instance
    """
    global _pdp_instance
    
    if _pdp_instance is None:
        # Get policy file path - try multiple locations for flexibility
        # 1. Docker container path (mounted volume)
        policy_file = '/app/xacml/policies.xml'
        
        # 2. If not in Docker, try relative path from project root
        if not os.path.exists(policy_file):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            policy_file = os.path.join(project_root, 'xacml', 'policies.xml')
        
        _pdp_instance = PolicyDecisionPoint(policy_file)
    
    return _pdp_instance


def check_authorization(username: str, role: str, action: str, 
                       resource_owner: Optional[str] = None,
                       target_role: Optional[str] = None) -> bool:
    """
    Convenience function to check authorization.
    
    Args:
        username: Subject username
        role: Subject role
        action: Action to perform
        resource_owner: Resource owner (optional)
        target_role: Target user's role (optional)
        
    Returns:
        True if permitted, False otherwise
    """
    pdp = get_pdp()
    
    subject = {
        'username': username,
        'role': role
    }
    
    resource = {}
    if resource_owner:
        resource['resource-owner'] = resource_owner
    if target_role:
        resource['target-role'] = target_role
    
    request = XACMLRequest(subject, resource, action)
    response = pdp.evaluate(request)
    
    logger.info(f"XACML decision for {username} ({role}) performing '{action}': {response.decision.value}")
    
    return response.is_permitted()
