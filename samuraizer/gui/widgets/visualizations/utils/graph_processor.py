# samuraizer_gui/ui/widgets/results_display/dot_preparer.py

import json
import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def prepare_dot_content(results_data: Dict[str, Any]) -> str:
    """
    Erstellt den DOT-Inhalt aus den Analyseergebnissen mit verbesserten Styling-Optionen.
    
    Args:
        results_data (Dict[str, Any]): Die Analyseergebnisse.
    
    Returns:
        str: Der generierte DOT-Inhalt.
    """
    try:
        def create_dot_node(name: str, attrs: dict = None) -> str:
            sanitized = name.replace('"', '\\"').replace('/', '_').replace('\\', '_')
            node_attrs = {
                'fontname': 'Helvetica',
                'fontsize': '10',
                'style': 'filled',
                'margin': '0.2',
            }
            if attrs:
                node_attrs.update(attrs)
            attr_str = ', '.join(f'{k}="{v}"' for k, v in node_attrs.items())
            return f'"{sanitized}" [{attr_str}]'

        def create_edge(src: str, dst: str, attrs: dict = None) -> str:
            src_sanitized = src.replace('"', '\\"').replace('/', '_').replace('\\', '_')
            dst_sanitized = dst.replace('"', '\\"').replace('/', '_').replace('\\', '_')
            edge_attrs = {
                'color': '#666666',
                'penwidth': '1.2',
                'arrowsize': '0.8',
            }
            if attrs:
                edge_attrs.update(attrs)
            attr_str = ', '.join(f'{k}="{v}"' for k, v in edge_attrs.items())
            return f'  "{src_sanitized}" -> "{dst_sanitized}" [{attr_str}];'

        def get_node_style(node_name: str, value: dict) -> dict:
            node_style = {}
            if isinstance(value, dict):
                if "type" in value:
                    node_type = value["type"]
                    if node_type == "error":
                        node_style.update({
                            'fillcolor': '#FFEBEE',
                            'color': '#D32F2F',
                            'shape': 'box',
                            'style': 'filled,bold',
                            'penwidth': '2.0'
                        })
                    elif node_type == "excluded":
                        node_style.update({
                            'fillcolor': '#F5F5F5',
                            'color': '#9E9E9E',
                            'shape': 'box',
                            'style': 'filled,dashed',
                            'penwidth': '1.0'
                        })
                    elif node_type == "text":
                        node_style.update({
                            'fillcolor': '#E8F5E9',
                            'color': '#2E7D32',
                            'shape': 'note',
                            'style': 'filled',
                        })
                    elif node_type == "binary":
                        node_style.update({
                            'fillcolor': '#E3F2FD',
                            'color': '#1976D2',
                            'shape': 'box',
                            'style': 'filled',
                        })
                    
                    if "size" in value:
                        size = value["size"]
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size/1024:.1f} KB"
                        else:
                            size_str = f"{size/(1024*1024):.1f} MB"
                        node_style['label'] = f"{os.path.basename(str(node_name))}\n{size_str}"
                    else:
                        node_style['label'] = os.path.basename(str(node_name))
                    
                    tooltip = [f"{attr}: {value[attr]}" for attr in ['encoding', 'created', 'modified', 'permissions'] if attr in value]
                    if tooltip:
                        node_style['tooltip'] = '\\n'.join(tooltip)
                else:
                    node_style.update({
                        'fillcolor': '#FFF3E0',
                        'color': '#E65100',
                        'shape': 'folder',
                        'style': 'filled',
                        'label': os.path.basename(str(node_name))
                    })
            return node_style

        def dict_to_dot(data: dict, parent_name: str = "root") -> List[str]:
            lines = []
            for key, value in sorted(data.items()):
                node_name = str(key)
                node_style = get_node_style(node_name, value)
                lines.append(f'  {create_dot_node(node_name, node_style)}')
                if parent_name != "root":
                    lines.append(create_edge(parent_name, node_name))
                if isinstance(value, dict) and "type" not in value:
                    lines.extend(dict_to_dot(value, node_name))
            return lines

        data = results_data.get("structure", results_data) if isinstance(results_data, dict) else results_data

        dot_lines = ["digraph Repository {"]
        dot_lines.extend([
            "  // Graph attributes",
            '  graph [',
            '    rankdir="LR",',
            '    splines="ortho",',
            '    ranksep="1.5",',
            '    nodesep="0.8",',
            '    pad="0.5",',
            '    bgcolor="white",',
            '  ];',
            '',
            "  // Default node attributes",
            '  node [',
            '    fontname="Helvetica",',
            '    fontsize="10",',
            '    shape="box",',
            '    style="filled",',
            '    margin="0.2",',
            '  ];',
            '',
            "  // Default edge attributes",
            '  edge [',
            '    color="#666666",',
            '    penwidth="1.2",',
            '    arrowsize="0.8",',
            '  ];',
            ''
        ])
        
        dot_lines.extend(dict_to_dot(data))
        dot_lines.append("}")

        dot_content = "\n".join(dot_lines)
        logger.debug(f"Generierter DOT-Inhalt mit {len(dot_lines)} Zeilen")
        return dot_content

    except Exception as e:
        logger.error(f"Fehler beim Erstellen des DOT-Inhalts: {e}", exc_info=True)
        raise ValueError(f"Ungültiger DOT-Inhalt: {str(e)}")
