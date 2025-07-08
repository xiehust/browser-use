# @file purpose: Demo script showcasing accessibility tree filtering algorithm
"""
Accessibility Tree Filtering Demo

This script demonstrates the efficient accessibility tree filtering algorithm
that creates smaller, "interesting-only" trees from full accessibility trees.
It mimics Playwright's `interesting_only=True` behavior.

Usage:
    python browser_use/dom/accessibility/demo.py
"""

import json
import time
import asyncio
from typing import Dict, Any
from browser_use.dom.accessibility.filter import (
    AccessibilityTreeFilter,
    create_interesting_tree,
    compare_trees,
    InterestingCriteria
)


# Sample accessibility trees for demonstration
SAMPLE_TREES = {
    "simple_form": {
        "role": "main",
        "name": "Contact Form",
        "children": [
            {
                "role": "heading",
                "name": "Contact Us",
                "level": 1
            },
            {
                "role": "group", 
                "name": "Personal Information",
                "children": [
                    {
                        "role": "textbox",
                        "name": "First Name",
                        "value": "",
                        "focusable": True,
                        "description": "Enter your first name"
                    },
                    {
                        "role": "textbox", 
                        "name": "Last Name",
                        "value": "",
                        "focusable": True,
                        "description": "Enter your last name"
                    },
                    {
                        "role": "textbox",
                        "name": "Email",
                        "value": "",
                        "focusable": True,
                        "description": "Enter your email address"
                    }
                ]
            },
            {
                "role": "group",
                "name": "Message",
                "children": [
                    {
                        "role": "textbox",
                        "name": "Your message",
                        "value": "",
                        "focusable": True,
                        "multiline": True
                    }
                ]
            },
            {
                "role": "button",
                "name": "Send Message",
                "focusable": True
            },
            {
                "role": "generic",
                "children": [
                    {
                        "role": "generic",
                        "children": [
                            {
                                "role": "generic",
                                "text": "Copyright 2024"
                            }
                        ]
                    }
                ]
            }
        ]
    },
    
    "navigation_menu": {
        "role": "banner",
        "children": [
            {
                "role": "navigation",
                "name": "Main Navigation",
                "children": [
                    {
                        "role": "list",
                        "children": [
                            {
                                "role": "listitem",
                                "children": [
                                    {
                                        "role": "link",
                                        "name": "Home",
                                        "focusable": True
                                    }
                                ]
                            },
                            {
                                "role": "listitem", 
                                "children": [
                                    {
                                        "role": "link",
                                        "name": "About",
                                        "focusable": True
                                    }
                                ]
                            },
                            {
                                "role": "listitem",
                                "children": [
                                    {
                                        "role": "button",
                                        "name": "Services",
                                        "focusable": True,
                                        "expanded": False,
                                        "children": [
                                            {
                                                "role": "menu",
                                                "children": [
                                                    {
                                                        "role": "menuitem",
                                                        "name": "Web Design",
                                                        "focusable": True
                                                    },
                                                    {
                                                        "role": "menuitem", 
                                                        "name": "Development",
                                                        "focusable": True
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "role": "listitem",
                                "children": [
                                    {
                                        "role": "link",
                                        "name": "Contact",
                                        "focusable": True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "role": "generic",
                "children": [
                    {
                        "role": "generic",
                        "children": [
                            {
                                "role": "generic"
                            }
                        ]
                    }
                ]
            }
        ]
    },
    
    "data_table": {
        "role": "main",
        "children": [
            {
                "role": "heading",
                "name": "User Data",
                "level": 2
            },
            {
                "role": "table",
                "name": "Users Table",
                "children": [
                    {
                        "role": "rowgroup",
                        "children": [
                            {
                                "role": "row",
                                "children": [
                                    {
                                        "role": "columnheader",
                                        "name": "Name",
                                        "focusable": True
                                    },
                                    {
                                        "role": "columnheader",
                                        "name": "Email", 
                                        "focusable": True
                                    },
                                    {
                                        "role": "columnheader",
                                        "name": "Actions",
                                        "focusable": True
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "role": "rowgroup",
                        "children": [
                            {
                                "role": "row",
                                "children": [
                                    {
                                        "role": "cell",
                                        "name": "John Doe"
                                    },
                                    {
                                        "role": "cell",
                                        "name": "john@example.com"
                                    },
                                    {
                                        "role": "cell",
                                        "children": [
                                            {
                                                "role": "button",
                                                "name": "Edit",
                                                "focusable": True
                                            },
                                            {
                                                "role": "button",
                                                "name": "Delete",
                                                "focusable": True
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "role": "row",
                                "children": [
                                    {
                                        "role": "cell",
                                        "name": "Jane Smith"
                                    },
                                    {
                                        "role": "cell", 
                                        "name": "jane@example.com"
                                    },
                                    {
                                        "role": "cell",
                                        "children": [
                                            {
                                                "role": "button",
                                                "name": "Edit",
                                                "focusable": True
                                            },
                                            {
                                                "role": "button",
                                                "name": "Delete", 
                                                "focusable": True
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
}


def print_tree(tree: Dict[str, Any], depth: int = 0, max_depth: int = 10) -> None:
    """Pretty print an accessibility tree"""
    if depth > max_depth or not tree:
        return
        
    indent = "  " * depth
    role = tree.get('role', 'unknown')
    name = tree.get('name', '')
    value = tree.get('value', '')
    
    # Build display string
    display_parts = [f"{indent}├─ {role}"]
    
    if name:
        display_parts.append(f' "{name}"')
    if value:
        display_parts.append(f' value="{value}"')
        
    # Add interesting properties
    properties = []
    if tree.get('focusable'):
        properties.append('focusable')
    if tree.get('checked') is not None:
        properties.append(f"checked={tree.get('checked')}")
    if tree.get('selected') is not None:
        properties.append(f"selected={tree.get('selected')}")
    if tree.get('expanded') is not None:
        properties.append(f"expanded={tree.get('expanded')}")
        
    if properties:
        display_parts.append(f" [{', '.join(properties)}]")
        
    print(''.join(display_parts))
    
    # Print children
    for child in tree.get('children', []):
        print_tree(child, depth + 1, max_depth)


def count_nodes(tree: Dict[str, Any]) -> int:
    """Count total nodes in a tree"""
    if not tree:
        return 0
    count = 1
    for child in tree.get('children', []):
        count += count_nodes(child)
    return count


def analyze_filtering_criteria(filter_obj: AccessibilityTreeFilter) -> None:
    """Analyze and display filtering criteria statistics"""
    stats = filter_obj.get_filtering_stats()
    
    print("\n📊 Filtering Analysis:")
    print(f"   Total nodes processed: {stats.total_nodes}")
    print(f"   Interesting nodes kept: {stats.interesting_nodes}")
    print(f"   Nodes filtered out: {stats.filtered_nodes}")
    print(f"   Compression ratio: {filter_obj.get_compression_ratio():.2%}")
    
    print("\n🎯 Criteria Matches:")
    for criteria, count in stats.criteria_matches.items():
        if count > 0:
            print(f"   {criteria.value}: {count} nodes")


def demo_basic_filtering():
    """Demonstrate basic filtering on sample trees"""
    print("🌳 ACCESSIBILITY TREE FILTERING DEMO")
    print("=" * 50)
    
    for name, tree in SAMPLE_TREES.items():
        print(f"\n📝 Demo: {name.replace('_', ' ').title()}")
        print("-" * 30)
        
        # Original tree
        original_count = count_nodes(tree)
        print(f"\n📄 Original Tree ({original_count} nodes):")
        print_tree(tree, max_depth=6)
        
        # Filter the tree
        filter_obj = AccessibilityTreeFilter()
        start_time = time.time()
        filtered_tree = filter_obj.filter_tree(tree)
        end_time = time.time()
        
        # Filtered tree
        if filtered_tree:
            filtered_count = count_nodes(filtered_tree)
            print(f"\n✨ Filtered Tree ({filtered_count} nodes):")
            print_tree(filtered_tree, max_depth=6)
            
            # Statistics
            analyze_filtering_criteria(filter_obj)
            print(f"\n⚡ Performance: {(end_time - start_time)*1000:.2f}ms")
            
            # Comparison
            comparison = compare_trees(tree, filtered_tree)
            print(f"\n📈 Size Reduction: {comparison['size_reduction_percent']:.1f}%")
        else:
            print("\n✨ Filtered Tree: (completely filtered out)")
        
        print("\n" + "="*50)


def demo_strict_vs_normal_mode():
    """Demonstrate difference between strict and normal filtering modes"""
    print("\n🎛️  STRICT VS NORMAL MODE COMPARISON")
    print("=" * 50)
    
    # Create a tree with borderline interesting elements
    test_tree = {
        "role": "main",
        "children": [
            {
                "role": "generic",
                "name": "Just has a name"  # Borderline case
            },
            {
                "role": "group", 
                "name": "Group with name"  # Borderline case  
            },
            {
                "role": "button",
                "name": "Clear button",
                "focusable": True  # Clearly interesting
            },
            {
                "role": "generic"  # Not interesting
            }
        ]
    }
    
    # Normal mode
    normal_filter = AccessibilityTreeFilter(strict_mode=False)
    normal_result = normal_filter.filter_tree(test_tree)
    normal_count = count_nodes(normal_result) if normal_result else 0
    
    # Strict mode  
    strict_filter = AccessibilityTreeFilter(strict_mode=True)
    strict_result = strict_filter.filter_tree(test_tree)
    strict_count = count_nodes(strict_result) if strict_result else 0
    
    original_count = count_nodes(test_tree)
    
    print(f"\n📊 Results Comparison:")
    print(f"   Original nodes: {original_count}")
    print(f"   Normal mode: {normal_count} nodes kept")
    print(f"   Strict mode: {strict_count} nodes kept")
    
    print(f"\n🎯 Normal Mode Tree:")
    if normal_result:
        print_tree(normal_result)
    else:
        print("   (empty)")
        
    print(f"\n🎯 Strict Mode Tree:")
    if strict_result:
        print_tree(strict_result)
    else:
        print("   (empty)")


def demo_performance_benchmark():
    """Demonstrate performance on larger trees"""
    print("\n⚡ PERFORMANCE BENCHMARK")
    print("=" * 50)
    
    sizes = [100, 1000, 5000]
    
    for size in sizes:
        print(f"\n🏃 Testing with {size} nodes...")
        
        # Create large tree
        large_tree = create_large_test_tree(size)
        
        filter_obj = AccessibilityTreeFilter()
        
        # Benchmark filtering
        start_time = time.time()
        result = filter_obj.filter_tree(large_tree)
        end_time = time.time()
        
        # Results
        stats = filter_obj.get_filtering_stats()
        processing_time = (end_time - start_time) * 1000  # Convert to ms
        
        print(f"   ✅ Processed {stats.total_nodes} nodes in {processing_time:.2f}ms")
        print(f"   📊 Kept {stats.interesting_nodes} interesting nodes")
        print(f"   🗜️  Compression: {filter_obj.get_compression_ratio():.1%}")
        print(f"   🚀 Speed: {stats.total_nodes / (processing_time/1000):.0f} nodes/second")


def create_large_test_tree(num_nodes: int) -> Dict[str, Any]:
    """Create a large test tree for performance testing"""
    def create_node(index: int) -> Dict[str, Any]:
        if index % 4 == 0:
            return {"role": "button", "name": f"Button {index}", "focusable": True}
        elif index % 4 == 1:
            return {"role": "link", "name": f"Link {index}", "focusable": True}
        elif index % 4 == 2:
            return {"role": "textbox", "value": f"Value {index}", "focusable": True}
        else:
            return {"role": "generic"}
    
    # Build tree structure
    nodes = [create_node(i) for i in range(num_nodes)]
    root = {"role": "main", "children": []}
    current_level = [root]
    node_index = 0
    
    while node_index < len(nodes):
        next_level = []
        for parent in current_level:
            children = []
            for _ in range(min(3, len(nodes) - node_index)):
                child = nodes[node_index].copy()
                child["children"] = []
                children.append(child)
                next_level.append(child)
                node_index += 1
            parent["children"] = children
        current_level = next_level
        
    return root


def demo_real_world_scenario():
    """Demonstrate filtering on a complex real-world-like tree"""
    print("\n🌍 REAL-WORLD SCENARIO")
    print("=" * 50)
    
    # Simulate a complex web application interface
    complex_tree = {
        "role": "document",
        "children": [
            {
                "role": "banner",
                "children": [
                    {
                        "role": "navigation",
                        "name": "Main menu",
                        "children": [
                            {"role": "link", "name": "Dashboard", "focusable": True},
                            {"role": "link", "name": "Users", "focusable": True},
                            {"role": "link", "name": "Settings", "focusable": True}
                        ]
                    },
                    {
                        "role": "button",
                        "name": "User menu",
                        "focusable": True,
                        "expanded": False
                    }
                ]
            },
            {
                "role": "main",
                "children": [
                    {
                        "role": "heading",
                        "name": "User Management",
                        "level": 1
                    },
                    {
                        "role": "search",
                        "children": [
                            {
                                "role": "searchbox",
                                "name": "Search users",
                                "focusable": True,
                                "value": ""
                            },
                            {
                                "role": "button",
                                "name": "Search",
                                "focusable": True
                            }
                        ]
                    },
                    {
                        "role": "region",
                        "name": "User list",
                        "children": [
                            {
                                "role": "table",
                                "name": "Users",
                                "children": [
                                    # ... table content would be here
                                    {
                                        "role": "button",
                                        "name": "Add user",
                                        "focusable": True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "role": "contentinfo",
                "children": [
                    {
                        "role": "generic",
                        "children": [
                            {"role": "link", "name": "Privacy Policy", "focusable": True},
                            {"role": "link", "name": "Terms of Service", "focusable": True}
                        ]
                    }
                ]
            },
            # Add lots of generic/layout containers
            *[{"role": "generic", "children": [{"role": "generic"}]} for _ in range(20)]
        ]
    }
    
    original_count = count_nodes(complex_tree)
    
    # Filter the tree
    filter_obj = AccessibilityTreeFilter()
    filtered_tree = filter_obj.filter_tree(complex_tree)
    
    if filtered_tree:
        filtered_count = count_nodes(filtered_tree)
        
        print(f"\n📊 Complex Application Analysis:")
        print(f"   Original complexity: {original_count} nodes")
        print(f"   Filtered complexity: {filtered_count} nodes")
        print(f"   Efficiency gain: {((original_count - filtered_count) / original_count) * 100:.1f}% reduction")
        
        print(f"\n🎯 Filtered Structure:")
        print_tree(filtered_tree, max_depth=4)
        
        analyze_filtering_criteria(filter_obj)


def main():
    """Run the complete demo"""
    print("🚀 ACCESSIBILITY TREE FILTERING ALGORITHM DEMO")
    print("================================================")
    print("This demo showcases an efficient algorithm that creates")
    print("smaller 'interesting-only' accessibility trees from full trees,")
    print("similar to Playwright's interesting_only=True parameter.")
    print()
    
    try:
        # Run all demos
        demo_basic_filtering()
        demo_strict_vs_normal_mode()
        demo_performance_benchmark()
        demo_real_world_scenario()
        
        print("\n🎉 Demo completed successfully!")
        print("\nKey takeaways:")
        print("• The algorithm efficiently filters accessibility trees")
        print("• O(n) time complexity with caching for repeated patterns")
        print("• Significant size reduction while preserving important elements")
        print("• Strict mode available for more aggressive filtering")
        print("• Performance scales well with tree size")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    main()