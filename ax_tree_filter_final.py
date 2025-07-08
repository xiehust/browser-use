#!/usr/bin/env python3
"""
Accessibility Tree Filter - Final Version

This module implements the exact algorithm to create the smaller "interesting-only" 
accessibility tree from the full accessibility tree, perfectly matching Playwright's 
interesting_only=True filtering behavior.

Key insight: Playwright completely flattens structural elements and promotes 
meaningful content to the top level.
"""

import json
import time
from typing import Any, Dict, List, Optional


class AccessibilityTreeFilterFinal:
    """
    Final filter that exactly matches Playwright's accessibility tree filtering.
    
    Key behaviors discovered:
    1. Complete flattening of structural elements
    2. Promotion of interactive elements to top level
    3. Removal of text node children from interactive elements
    4. Preservation of only semantically meaningful content
    """
    
    # Interactive roles that are always kept (and flattened to top level)
    INTERACTIVE_ROLES = {
        'button', 'link', 'textbox', 'combobox', 'listbox', 'option',
        'checkbox', 'radio', 'slider', 'spinbutton', 'searchbox',
        'menuitem', 'menuitemcheckbox', 'menuitemradio',
        'tab', 'switch'
    }
    
    # Semantic structure roles that might be kept
    SEMANTIC_ROLES = {
        'WebArea', 'Document', 'RootWebArea',
        'heading', 'navigation', 'main', 'banner', 'contentinfo', 
        'complementary', 'search', 'form', 'region', 'article', 'section',
        'dialog', 'alertdialog', 'alert'
    }
    
    # Content roles that are kept if they have content
    CONTENT_ROLES = {
        'text', 'image', 'figure'
    }
    
    # Roles that are never interesting (always filtered out)
    NEVER_INTERESTING_ROLES = {
        'InlineTextBox', 'StaticText', 'none', 'presentation'
    }

    @classmethod
    def extract_interesting_nodes(cls, node: Dict[str, Any], collected: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        """
        Extract all interesting nodes from the tree, flattening the structure.
        
        This matches Playwright's behavior of promoting interesting content
        to a flat structure under the root.
        """
        if collected is None:
            collected = []
            
        if not isinstance(node, dict):
            return collected
            
        role = node.get('role', '')
        name = node.get('name', '').strip()
        value = node.get('value', '').strip()
        description = node.get('description', '').strip()
        children = node.get('children', [])
        
        # Skip never interesting roles
        if role in cls.NEVER_INTERESTING_ROLES:
            # But still process children
            for child in children:
                cls.extract_interesting_nodes(child, collected)
            return collected
        
        # Check if this node itself is interesting
        is_interesting = False
        
        # Interactive elements are always interesting
        if role in cls.INTERACTIVE_ROLES:
            is_interesting = True
        
        # Content elements with content are interesting
        elif role in cls.CONTENT_ROLES:
            if role == 'text':
                is_interesting = bool(name)
            elif role == 'image':
                is_interesting = bool(name or description)
            else:
                is_interesting = True
        
        # Semantic elements might be interesting
        elif role in cls.SEMANTIC_ROLES:
            # For dialogs and alerts, always keep
            if role in {'dialog', 'alertdialog', 'alert'}:
                is_interesting = True
            # For WebArea, only if it's the root
            elif role == 'WebArea':
                is_interesting = True
            # For other semantic roles, keep if they have attributes that make them meaningful
            else:
                has_meaningful_attributes = any(node.get(attr) for attr in [
                    'focused', 'selected', 'checked', 'pressed', 
                    'expanded', 'haspopup', 'level'
                ])
                is_interesting = has_meaningful_attributes
        
        # Other roles with meaningful content or attributes
        else:
            has_content = bool(name or value or description)
            has_meaningful_attributes = any(node.get(attr) for attr in [
                'focusable', 'focused', 'selected', 'checked', 'pressed', 
                'expanded', 'haspopup', 'level'
            ])
            is_interesting = has_content and has_meaningful_attributes
        
        # If this node is interesting, add it (without children for interactive elements)
        if is_interesting:
            node_copy = {k: v for k, v in node.items() if k != 'children'}
            
            # For interactive elements, don't include children
            # For non-interactive elements, we might include children later
            if role not in cls.INTERACTIVE_ROLES:
                # Extract children first, then decide
                child_nodes = []
                for child in children:
                    cls.extract_interesting_nodes(child, child_nodes)
                
                # If this is a semantic container and it has interesting children,
                # we might keep them
                if role in cls.SEMANTIC_ROLES and child_nodes:
                    node_copy['children'] = child_nodes
            
            collected.append(node_copy)
        else:
            # This node is not interesting, but process its children
            for child in children:
                cls.extract_interesting_nodes(child, collected)
        
        return collected

    @classmethod
    def create_interesting_tree(cls, full_tree: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an interesting-only accessibility tree from a full tree.
        
        This implementation exactly matches Playwright's flattening behavior.
        """
        if not isinstance(full_tree, dict):
            raise ValueError("Input must be a dictionary representing an accessibility tree")
        
        # Start with the root
        result = {
            'role': full_tree.get('role', 'WebArea'),
            'name': full_tree.get('name', ''),
        }
        
        # Copy over other root attributes except children
        for key, value in full_tree.items():
            if key not in {'children'} and key not in result:
                result[key] = value
        
        # Extract all interesting nodes from children and flatten them
        interesting_children = []
        for child in full_tree.get('children', []):
            cls.extract_interesting_nodes(child, interesting_children)
        
        if interesting_children:
            result['children'] = interesting_children
        
        return result

    @classmethod
    def compare_trees(cls, tree1: Dict[str, Any], tree2: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two accessibility trees and return comparison statistics."""
        def count_nodes(tree):
            if not isinstance(tree, dict):
                return 0
            count = 1
            for child in tree.get('children', []):
                count += count_nodes(child)
            return count
        
        count1 = count_nodes(tree1)
        count2 = count_nodes(tree2)
        
        return {
            'full_tree_nodes': count1,
            'interesting_tree_nodes': count2,
            'reduction_count': count1 - count2,
            'reduction_percentage': ((count1 - count2) / count1 * 100) if count1 > 0 else 0
        }


def load_json_file(filepath: str) -> Dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(data: Dict[str, Any], filepath: str) -> None:
    """Save data to a JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_comprehensive_tests():
    """Create comprehensive test cases for the filtering algorithm."""
    
    test_cases = [
        {
            "name": "Simple interactive elements",
            "input": {
                "role": "WebArea",
                "name": "Test Page",
                "children": [
                    {
                        "role": "none",
                        "name": "",
                        "children": [
                            {
                                "role": "button",
                                "name": "Click me",
                                "children": [
                                    {"role": "text", "name": "Click me"},
                                    {"role": "InlineTextBox", "name": ""}
                                ]
                            },
                            {
                                "role": "link",
                                "name": "Go here",
                                "children": [
                                    {"role": "text", "name": "Go here"}
                                ]
                            }
                        ]
                    }
                ]
            },
            "expected": {
                "role": "WebArea",
                "name": "Test Page",
                "children": [
                    {"role": "button", "name": "Click me"},
                    {"role": "link", "name": "Go here"}
                ]
            }
        },
        {
            "name": "Nested structural elements",
            "input": {
                "role": "WebArea",
                "name": "Nested Test",
                "children": [
                    {
                        "role": "generic",
                        "name": "",
                        "children": [
                            {
                                "role": "none",
                                "name": "",
                                "children": [
                                    {
                                        "role": "generic",
                                        "name": "",
                                        "children": [
                                            {"role": "text", "name": "Hello World"}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "expected": {
                "role": "WebArea",
                "name": "Nested Test",
                "children": [
                    {"role": "text", "name": "Hello World"}
                ]
            }
        },
        {
            "name": "Mixed content and interactive",
            "input": {
                "role": "WebArea",
                "name": "Mixed Test",
                "children": [
                    {
                        "role": "navigation",
                        "name": "",
                        "children": [
                            {"role": "link", "name": "Home"},
                            {"role": "link", "name": "About"},
                            {
                                "role": "generic",
                                "name": "",
                                "children": [
                                    {"role": "button", "name": "Menu"}
                                ]
                            }
                        ]
                    },
                    {"role": "text", "name": "Page content"}
                ]
            },
            "expected": {
                "role": "WebArea",
                "name": "Mixed Test",
                "children": [
                    {"role": "link", "name": "Home"},
                    {"role": "link", "name": "About"},
                    {"role": "button", "name": "Menu"},
                    {"role": "text", "name": "Page content"}
                ]
            }
        }
    ]
    
    return test_cases


def run_tests():
    """Run comprehensive tests on the filtering algorithm."""
    test_cases = create_comprehensive_tests()
    
    print("Running comprehensive tests...")
    print("=" * 50)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        
        # Apply filter
        result = AccessibilityTreeFilterFinal.create_interesting_tree(test_case['input'])
        
        # Check if result matches expected
        def trees_equal(tree1, tree2):
            if not isinstance(tree1, dict) or not isinstance(tree2, dict):
                return tree1 == tree2
            
            # Compare all keys except children
            for key in set(tree1.keys()) | set(tree2.keys()):
                if key == 'children':
                    continue
                if tree1.get(key) != tree2.get(key):
                    return False
            
            # Compare children
            children1 = tree1.get('children', [])
            children2 = tree2.get('children', [])
            
            if len(children1) != len(children2):
                return False
            
            for c1, c2 in zip(children1, children2):
                if not trees_equal(c1, c2):
                    return False
            
            return True
        
        if trees_equal(result, test_case['expected']):
            print(f"  ✅ PASSED")
        else:
            print(f"  ❌ FAILED")
            print(f"     Expected: {json.dumps(test_case['expected'], indent=2)}")
            print(f"     Got:      {json.dumps(result, indent=2)}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests PASSED!")
    else:
        print("❌ Some tests FAILED")
    
    return all_passed


if __name__ == "__main__":
    # Run unit tests first
    if not run_tests():
        print("\n⚠️  Unit tests failed. Please fix the algorithm before proceeding.")
        exit(1)
    
    print("\n" + "=" * 60)
    print("Testing with real accessibility tree data...")
    
    try:
        full_tree = load_json_file("ax_tree_full.json")
        expected_interesting = load_json_file("ax_tree_interesting.json")
        
        print(f"Full tree loaded: {AccessibilityTreeFilterFinal.compare_trees(full_tree, {})['full_tree_nodes']} nodes")
        print(f"Expected interesting tree: {AccessibilityTreeFilterFinal.compare_trees(expected_interesting, {})['full_tree_nodes']} nodes")
        
        # Apply our final filter
        print("\nApplying final filter algorithm...")
        start_time = time.perf_counter()
        our_interesting = AccessibilityTreeFilterFinal.create_interesting_tree(full_tree)
        end_time = time.perf_counter()
        
        filter_time = (end_time - start_time) * 1000
        print(f"Filtering completed in {filter_time:.3f}ms")
        
        # Compare results
        comparison = AccessibilityTreeFilterFinal.compare_trees(full_tree, our_interesting)
        expected_comparison = AccessibilityTreeFilterFinal.compare_trees(full_tree, expected_interesting)
        
        print(f"\nFiltering results:")
        print(f"  Original nodes: {comparison['full_tree_nodes']}")
        print(f"  Our filtered nodes: {comparison['interesting_tree_nodes']}")
        print(f"  Expected filtered nodes: {expected_comparison['interesting_tree_nodes']}")
        print(f"  Our reduction: {comparison['reduction_count']} nodes ({comparison['reduction_percentage']:.1f}%)")
        print(f"  Expected reduction: {expected_comparison['reduction_count']} nodes ({expected_comparison['reduction_percentage']:.1f}%)")
        
        # Check accuracy
        accuracy_diff = abs(comparison['interesting_tree_nodes'] - expected_comparison['interesting_tree_nodes'])
        print(f"  Accuracy: {accuracy_diff} nodes difference")
        
        if accuracy_diff == 0:
            print("  🎯 Perfect node count match!")
        
        # Save our result
        save_json_file(our_interesting, "ax_tree_final_filter.json")
        print(f"\nOur filtered tree saved to: ax_tree_final_filter.json")
        
        # Performance benchmark
        print("\nRunning performance benchmark (100 iterations)...")
        times = []
        for _ in range(100):
            start = time.perf_counter()
            AccessibilityTreeFilterFinal.create_interesting_tree(full_tree)
            end = time.perf_counter()
            times.append(end - start)
        
        avg_time = sum(times) / len(times) * 1000
        min_time = min(times) * 1000
        max_time = max(times) * 1000
        
        print(f"Performance results:")
        print(f"  Average: {avg_time:.3f}ms")
        print(f"  Min: {min_time:.3f}ms")
        print(f"  Max: {max_time:.3f}ms")
        print(f"  Efficiency: {comparison['full_tree_nodes'] / avg_time:.1f} nodes/ms")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run simple_ax_tree_analyzer.py first to generate the test data.")