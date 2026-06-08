#!/usr/bin/env python3
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

def get_structure(element, indent=0):
    lines = []
    prefix = "  " * indent
    
    attr_str = ""
    if element.attrib:
        attrs = [f"{k}='{v}'" for k, v in element.attrib.items()]
        attr_str = " " + " ".join(attrs)
    
    text = element.text.strip() if element.text else ""
    text_info = f" TEXT: {repr(text[:50])}" if text else ""
    
    # Group children by tag to identify repeated structures
    children_by_tag = defaultdict(list)
    for child in element:
        children_by_tag[child.tag].append(child)
        
    if not children_by_tag and not text:
        # Empty leaf node
        lines.append(f"{prefix}<{element.tag}{attr_str}>")
    else:
        line = f"{prefix}<{element.tag}{attr_str}>{text_info}"
        if children_by_tag:
            total_children = sum(len(v) for v in children_by_tag.values())
            line += f" ({total_children} children total)"
        lines.append(line)
        
        for tag, children in children_by_tag.items():
            count = len(children)
            if count == 1:
                # Single child, recurse normally
                child_lines = get_structure(children[0], indent + 1)
                lines.extend(child_lines)
            else:
                # Multiple children of the same tag: summarize
                lines.append(f"{prefix}  <{tag}> × {count} (showing 1st as example)")
                # Recurse into the first child to show the internal structure
                child_lines = get_structure(children[0], indent + 2)
                lines.extend(child_lines)
            
    return lines

def main():
    file_path = "investment_portfolio.xml"
    output_path = "investment_portfolio_structure.md"
        
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        lines = get_structure(root)
        output = "\n".join(lines)
        
        print(output)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output + "\n")
            
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()