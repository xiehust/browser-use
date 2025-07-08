# @file purpose: Efficient accessibility tree filtering algorithm
"""
Accessibility Tree Filtering for browser-use

This module provides an efficient algorithm to create a smaller, "interesting-only" 
accessibility tree from a full accessibility tree. It mimics Playwright's 
`interesting_only=True` behavior by filtering elements based on accessibility 
importance and user interaction relevance.

Algorithm Performance: O(n) time complexity, O(d) space complexity where n is 
the number of nodes and d is the tree depth.
"""

import json
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class InterestingCriteria(Enum):
    """Criteria that make an accessibility node 'interesting'"""
    HAS_ROLE = "has_role"
    IS_FOCUSABLE = "is_focusable" 
    HAS_NAME = "has_name"
    HAS_VALUE = "has_value"
    HAS_DESCRIPTION = "has_description"
    IS_INTERACTIVE = "is_interactive"
    IS_LANDMARK = "is_landmark"
    HAS_ARIA_ATTRIBUTES = "has_aria_attributes"
    HAS_STATE_PROPERTIES = "has_state_properties"


@dataclass
class FilteringStats:
    """Statistics about the filtering process"""
    total_nodes: int = 0
    interesting_nodes: int = 0
    filtered_nodes: int = 0
    criteria_matches: Dict[InterestingCriteria, int] = field(
        default_factory=lambda: {criteria: 0 for criteria in InterestingCriteria}
    )


class AccessibilityTreeFilter:
    """
    Efficient accessibility tree filter that creates smaller, focused trees
    by identifying elements that are important for accessibility and user interaction.
    """
    
    # ARIA roles that are always considered interesting
    INTERACTIVE_ROLES = {
        'button', 'link', 'menuitem', 'menuitemradio', 'menuitemcheckbox',
        'radio', 'checkbox', 'tab', 'switch', 'slider', 'spinbutton',
        'combobox', 'searchbox', 'textbox', 'listbox', 'option', 'scrollbar'
    }
    
    # Landmark roles that provide navigation structure
    LANDMARK_ROLES = {
        'banner', 'contentinfo', 'main', 'navigation', 'region',
        'complementary', 'form', 'search', 'application'
    }
    
    # Container roles that might be interesting if they have children
    CONTAINER_ROLES = {
        'list', 'listbox', 'menu', 'menubar', 'tablist', 'tree',
        'grid', 'table', 'toolbar', 'group', 'radiogroup'
    }
    
    # ARIA properties that indicate interactivity or state
    ARIA_STATE_PROPERTIES = {
        'aria-checked', 'aria-selected', 'aria-expanded', 'aria-pressed',
        'aria-disabled', 'aria-hidden', 'aria-current', 'aria-busy',
        'aria-live', 'aria-atomic', 'aria-relevant'
    }
    
    # ARIA properties that provide accessible names/descriptions
    ARIA_LABEL_PROPERTIES = {
        'aria-label', 'aria-labelledby', 'aria-describedby', 'aria-description'
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the filter.
        
        Args:
            strict_mode: If True, applies stricter filtering criteria
        """
        self.strict_mode = strict_mode
        self.stats = FilteringStats()
        self._node_cache: Dict[str, bool] = {}

    def filter_tree(self, full_tree: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Filter a full accessibility tree to create an interesting-only version.
        
        Args:
            full_tree: The complete accessibility tree from Playwright
            
        Returns:
            Filtered accessibility tree containing only interesting elements
            
        Time Complexity: O(n) where n is the number of nodes
        Space Complexity: O(d) where d is the maximum depth of the tree
        """
        if not full_tree:
            return None
            
        self.stats = FilteringStats()
        self._node_cache.clear()
        
        filtered_tree = self._filter_node(full_tree)
        
        # Calculate final statistics
        self.stats.filtered_nodes = self.stats.total_nodes - self.stats.interesting_nodes
        
        return filtered_tree

    def _filter_node(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Recursively filter a single node and its children.
        
        Args:
            node: The accessibility node to filter
            
        Returns:
            Filtered node if interesting, None if should be filtered out
        """
        if not node:
            return None
            
        self.stats.total_nodes += 1
        
        # Create a unique key for caching (based on node properties)
        node_key = self._create_node_key(node)
        
        # Check cache first for performance
        if node_key in self._node_cache:
            if self._node_cache[node_key]:
                self.stats.interesting_nodes += 1
            return node.copy() if self._node_cache[node_key] else None
        
        # Check if this node is interesting
        is_interesting, matching_criteria = self._is_node_interesting(node)
        
        # Cache the result
        self._node_cache[node_key] = is_interesting
        
        # Update statistics
        for criteria in matching_criteria:
            self.stats.criteria_matches[criteria] += 1
        
        # Process children recursively
        filtered_children = []
        children = node.get('children', [])
        
        for child in children:
            filtered_child = self._filter_node(child)
            if filtered_child:
                filtered_children.append(filtered_child)
        
        # Special case: container nodes that aren't inherently interesting
        # but have interesting children should be included
        if not is_interesting and filtered_children:
            role = node.get('role', '').lower()
            if (role in self.CONTAINER_ROLES or 
                role in ['generic', 'group'] or
                not role):  # Include generic containers with interesting children
                is_interesting = True
                self.stats.criteria_matches[InterestingCriteria.IS_INTERACTIVE] += 1
        
        if is_interesting:
            self.stats.interesting_nodes += 1
            
            # Create filtered node
            filtered_node = node.copy()
            if filtered_children:
                filtered_node['children'] = filtered_children
            elif 'children' in filtered_node:
                # Remove empty children array to keep tree clean
                del filtered_node['children']
                
            return filtered_node
        
        # If node isn't interesting but has interesting children,
        # promote the children up (flatten the tree)
        if filtered_children and not self.strict_mode:
            # For non-strict mode, we can return children directly
            # This helps create a more concise tree
            return filtered_children[0] if len(filtered_children) == 1 else {
                'role': 'group',
                'children': filtered_children
            }
        
        return None

    def _is_node_interesting(self, node: Dict[str, Any]) -> tuple[bool, List[InterestingCriteria]]:
        """
        Determine if a node is interesting based on accessibility criteria.
        
        Args:
            node: The accessibility node to evaluate
            
        Returns:
            Tuple of (is_interesting, list_of_matching_criteria)
        """
        matching_criteria = []
        
        # Extract node properties
        role = node.get('role', '').lower()
        name = node.get('name', '').strip()
        value = node.get('value', '').strip()
        description = node.get('description', '').strip()
        focusable = node.get('focusable', False)
        
        # Criterion 1: Has a meaningful role
        if role and role != 'generic':
            matching_criteria.append(InterestingCriteria.HAS_ROLE)
        
        # Criterion 2: Is focusable
        if focusable:
            matching_criteria.append(InterestingCriteria.IS_FOCUSABLE)
        
        # Criterion 3: Has accessible name
        if name:
            matching_criteria.append(InterestingCriteria.HAS_NAME)
        
        # Criterion 4: Has value (form controls)
        if value:
            matching_criteria.append(InterestingCriteria.HAS_VALUE)
        
        # Criterion 5: Has description
        if description:
            matching_criteria.append(InterestingCriteria.HAS_DESCRIPTION)
        
        # Criterion 6: Is interactive element
        if role in self.INTERACTIVE_ROLES:
            matching_criteria.append(InterestingCriteria.IS_INTERACTIVE)
        
        # Criterion 7: Is landmark
        if role in self.LANDMARK_ROLES:
            matching_criteria.append(InterestingCriteria.IS_LANDMARK)
        
        # Criterion 8: Has ARIA attributes
        if self._has_aria_attributes(node):
            matching_criteria.append(InterestingCriteria.HAS_ARIA_ATTRIBUTES)
        
        # Criterion 9: Has state properties
        if self._has_state_properties(node):
            matching_criteria.append(InterestingCriteria.HAS_STATE_PROPERTIES)
        
        # Node is interesting if it matches any criteria
        is_interesting = len(matching_criteria) > 0
        
        # Additional rules for strict mode
        if self.strict_mode:
            # In strict mode, require multiple criteria for certain roles
            if role in ['generic', 'group'] and len(matching_criteria) < 2:
                is_interesting = False
                matching_criteria.clear()
        
        return is_interesting, matching_criteria

    def _has_aria_attributes(self, node: Dict[str, Any]) -> bool:
        """Check if node has important ARIA attributes."""
        # Note: In a real implementation, we'd check the actual DOM attributes
        # For now, we check if the node has aria-related properties in its data
        
        # Check for common ARIA properties that might be in the accessibility tree
        for key in node.keys():
            if key.startswith('aria') or key in self.ARIA_LABEL_PROPERTIES:
                return True
        
        # Check if name/description comes from ARIA (heuristic)
        name = node.get('name', '')
        if name and len(name) > 0:
            # If name exists, it likely comes from aria-label or aria-labelledby
            return True
        
        return False

    def _has_state_properties(self, node: Dict[str, Any]) -> bool:
        """Check if node has state-related properties."""
        state_indicators = [
            'checked', 'selected', 'expanded', 'pressed', 
            'disabled', 'focused', 'busy', 'current'
        ]
        
        return any(node.get(prop) is not None for prop in state_indicators)

    def _create_node_key(self, node: Dict[str, Any]) -> str:
        """Create a unique key for caching node filtering results."""
        # Create a hash based on important node properties
        key_parts = [
            node.get('role', ''),
            node.get('name', ''),
            node.get('value', ''),
            str(node.get('focusable', False)),
            str(node.get('checked', '')),
            str(node.get('selected', '')),
            str(node.get('expanded', ''))
        ]
        return '|'.join(key_parts)

    def get_filtering_stats(self) -> FilteringStats:
        """Get statistics about the last filtering operation."""
        return self.stats

    def get_compression_ratio(self) -> float:
        """Get the compression ratio (how much smaller the filtered tree is)."""
        if self.stats.total_nodes == 0:
            return 0.0
        return 1.0 - (self.stats.interesting_nodes / self.stats.total_nodes)


def create_interesting_tree(full_tree: Dict[str, Any], strict_mode: bool = False) -> Optional[Dict[str, Any]]:
    """
    Convenience function to create an interesting-only accessibility tree.
    
    Args:
        full_tree: Complete accessibility tree
        strict_mode: Whether to apply stricter filtering
        
    Returns:
        Filtered accessibility tree
    """
    filter_instance = AccessibilityTreeFilter(strict_mode=strict_mode)
    return filter_instance.filter_tree(full_tree)


def compare_trees(original: Dict[str, Any], filtered: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare original and filtered trees to show filtering results.
    
    Args:
        original: Original full tree
        filtered: Filtered tree
        
    Returns:
        Comparison statistics
    """
    def count_nodes(tree):
        if not tree:
            return 0
        count = 1
        for child in tree.get('children', []):
            count += count_nodes(child)
        return count
    
    original_count = count_nodes(original)
    filtered_count = count_nodes(filtered)
    
    return {
        'original_nodes': original_count,
        'filtered_nodes': filtered_count,
        'removed_nodes': original_count - filtered_count,
        'compression_ratio': 1.0 - (filtered_count / original_count) if original_count > 0 else 0.0,
        'size_reduction_percent': ((original_count - filtered_count) / original_count * 100) if original_count > 0 else 0.0
    }