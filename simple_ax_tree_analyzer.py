#!/usr/bin/env python3
"""
Simple Accessibility Tree Analyzer

This script extracts both full and interesting-only accessibility trees from a webpage
and analyzes the differences to understand the filtering algorithm used by Playwright's
interesting_only parameter.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import async_playwright


def analyze_node_differences(full_node: Dict[str, Any], interesting_node: Dict[str, Any] | None = None, 
                           path: str = "", differences: List[Dict] | None = None) -> List[Dict]:
    """Recursively analyze differences between full and interesting trees."""
    if differences is None:
        differences = []
    
    # Check if this node exists in interesting tree
    if interesting_node is None:
        differences.append({
            "path": path,
            "reason": "excluded_from_interesting",
            "node": {
                "role": full_node.get("role"),
                "name": full_node.get("name"),
                "value": full_node.get("value"),
                "description": full_node.get("description"),
                "focusable": full_node.get("focusable"),
                "disabled": full_node.get("disabled"),
                "hidden": full_node.get("hidden"),
                "level": full_node.get("level"),
                "children_count": len(full_node.get("children", []))
            }
        })
        return differences
    
    # Compare children recursively
    full_children = full_node.get("children", [])
    interesting_children = interesting_node.get("children", [])
    
    # Create a mapping of interesting children for comparison
    interesting_children_map = {}
    for i, child in enumerate(interesting_children):
        key = (child.get("role"), child.get("name"), child.get("value"))
        interesting_children_map[key] = child
    
    for i, full_child in enumerate(full_children):
        child_path = f"{path}/child[{i}]"
        key = (full_child.get("role"), full_child.get("name"), full_child.get("value"))
        
        if key in interesting_children_map:
            # Child exists in both trees, recurse
            analyze_node_differences(full_child, interesting_children_map[key], 
                                   child_path, differences)
        else:
            # Child doesn't exist in interesting tree
            analyze_node_differences(full_child, None, child_path, differences)
    
    return differences


def extract_node_attributes(node: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all attributes from a node for analysis."""
    if not node:
        return {}
    
    return {
        "role": node.get("role"),
        "name": node.get("name"), 
        "value": node.get("value"),
        "description": node.get("description"),
        "focusable": node.get("focusable"),
        "focused": node.get("focused"),
        "disabled": node.get("disabled"),
        "hidden": node.get("hidden"),
        "level": node.get("level"),
        "multiselectable": node.get("multiselectable"),
        "readonly": node.get("readonly"),
        "required": node.get("required"),
        "selected": node.get("selected"),
        "checked": node.get("checked"),
        "pressed": node.get("pressed"),
        "expanded": node.get("expanded"),
        "modal": node.get("modal"),
        "multiline": node.get("multiline"),
        "orientation": node.get("orientation"),
        "children_count": len(node.get("children", []))
    }


def collect_all_nodes(node: Dict[str, Any], nodes: List[Dict] | None = None, depth: int = 0) -> List[Dict]:
    """Collect all nodes from a tree with their attributes and depth."""
    if nodes is None:
        nodes = []
    
    if node:
        node_info = extract_node_attributes(node)
        node_info["depth"] = depth
        nodes.append(node_info)
        
        for child in node.get("children", []):
            collect_all_nodes(child, nodes, depth + 1)
    
    return nodes


def find_interesting_patterns(excluded_nodes: List[Dict]) -> Dict[str, Any]:
    """Analyze patterns in excluded nodes to understand the filtering criteria."""
    patterns = {
        "roles_excluded": {},
        "attributes_patterns": {},
        "common_exclusions": []
    }
    
    for node in excluded_nodes:
        role = node["node"]["role"]
        if role:
            patterns["roles_excluded"][role] = patterns["roles_excluded"].get(role, 0) + 1
        
        # Check for common exclusion patterns
        node_data = node["node"]
        if node_data.get("hidden"):
            patterns["common_exclusions"].append("hidden=true")
        if node_data.get("disabled"):
            patterns["common_exclusions"].append("disabled=true")
        if not node_data.get("focusable") and role in ["generic", "text"]:
            patterns["common_exclusions"].append("non_focusable_generic_or_text")
        if node_data.get("children_count", 0) == 0 and not node_data.get("name") and not node_data.get("value"):
            patterns["common_exclusions"].append("empty_leaf_node")
    
    return patterns


async def extract_and_analyze_trees(url: str = "https://example.com") -> Dict[str, Any]:
    """Extract both accessibility trees and analyze differences."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until='domcontentloaded')
        await asyncio.sleep(2)  # Wait for dynamic content
        
        print("Extracting full accessibility tree...")
        start_time = time.time()
        ax_tree_full = await page.accessibility.snapshot(interesting_only=False)
        full_time = time.time() - start_time
        
        print("Extracting interesting-only accessibility tree...")
        start_time = time.time()
        ax_tree_interesting = await page.accessibility.snapshot(interesting_only=True)
        interesting_time = time.time() - start_time
        
        await browser.close()
        
        # Collect all nodes from both trees
        full_nodes = collect_all_nodes(ax_tree_full)
        interesting_nodes = collect_all_nodes(ax_tree_interesting)
        
        print(f"\nTree extraction times:")
        print(f"  Full tree: {full_time:.3f}s")
        print(f"  Interesting tree: {interesting_time:.3f}s")
        
        print(f"\nNode counts:")
        print(f"  Full tree: {len(full_nodes)} nodes")
        print(f"  Interesting tree: {len(interesting_nodes)} nodes")
        print(f"  Reduction: {len(full_nodes) - len(interesting_nodes)} nodes ({((len(full_nodes) - len(interesting_nodes))/len(full_nodes)*100):.1f}%)")
        
        # Analyze differences
        differences = analyze_node_differences(ax_tree_full, ax_tree_interesting)
        patterns = find_interesting_patterns(differences)
        
        # Save trees to files
        Path("ax_tree_full.json").write_text(json.dumps(ax_tree_full, indent=2), encoding='utf-8')
        Path("ax_tree_interesting.json").write_text(json.dumps(ax_tree_interesting, indent=2), encoding='utf-8')
        
        return {
            "url": url,
            "full_tree": ax_tree_full,
            "interesting_tree": ax_tree_interesting,
            "full_nodes": full_nodes,
            "interesting_nodes": interesting_nodes,
            "differences": differences,
            "patterns": patterns,
            "stats": {
                "full_count": len(full_nodes),
                "interesting_count": len(interesting_nodes),
                "excluded_count": len(differences),
                "reduction_percentage": (len(full_nodes) - len(interesting_nodes))/len(full_nodes)*100
            }
        }


async def main():
    """Main function to run the analysis."""
    urls = [
        "https://example.com",
        "https://github.com",
        "https://www.google.com"
    ]
    
    all_results = []
    
    for url in urls:
        try:
            print(f"\n{'='*60}")
            print(f"Analyzing: {url}")
            print(f"{'='*60}")
            
            result = await extract_and_analyze_trees(url)
            all_results.append(result)
            
            # Print analysis
            print(f"\nExclusion patterns for {url}:")
            patterns = result["patterns"]
            
            print(f"\nMost excluded roles:")
            for role, count in sorted(patterns["roles_excluded"].items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {role}: {count} times")
            
            print(f"\nCommon exclusion reasons:")
            exclusion_reasons = {}
            for reason in patterns["common_exclusions"]:
                exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
            
            for reason, count in sorted(exclusion_reasons.items(), key=lambda x: x[1], reverse=True):
                print(f"  {reason}: {count} times")
                
        except Exception as e:
            print(f"Error analyzing {url}: {e}")
    
    # Save comprehensive analysis
    analysis_file = "ax_tree_analysis.json"
    Path(analysis_file).write_text(json.dumps({
        "results": all_results,
        "summary": {
            "total_urls_analyzed": len(all_results),
            "average_reduction": sum(r["stats"]["reduction_percentage"] for r in all_results) / len(all_results) if all_results else 0
        }
    }, indent=2, default=str), encoding='utf-8')
    
    print(f"\n{'='*60}")
    print(f"Analysis complete! Files saved:")
    print(f"  - ax_tree_full.json (last analyzed URL)")
    print(f"  - ax_tree_interesting.json (last analyzed URL)")
    print(f"  - {analysis_file} (comprehensive analysis)")


if __name__ == "__main__":
    asyncio.run(main())