"""
Mermaid attack graph generator.
Builds a Mermaid `graph LR` definition from incident entity data.
All node labels are sanitized via sanitize_mermaid_label() before rendering.
"""

from __future__ import annotations

from typing import Any

from artifacts.sanitizers import sanitize_mermaid_label

# Node style classes per entity role
ROLE_STYLES = {
    "attacker": "fill:#ef4444,color:#fff,stroke:#dc2626",
    "victim": "fill:#f97316,color:#fff,stroke:#ea580c",
    "pivot": "fill:#eab308,color:#000,stroke:#ca8a04",
    "context": "fill:#3b82f6,color:#fff,stroke:#2563eb",
}


def generate_attack_graph(incident: dict[str, Any]) -> str:
    """
    Generate a Mermaid graph LR definition from incident entity data.
    
    Returns a Mermaid source string ready to render in the browser via
    the mermaid npm package.
    """
    lines: list[str] = ["graph LR"]
    style_lines: list[str] = []

    entities = incident.get("entities", [])
    alerts = incident.get("alerts", [])
    technique = incident.get("technique_id", "Unknown")
    tactic = incident.get("tactic", "Unknown")

    if not entities:
        # Fallback: simple two-node graph
        lines.append('  A["Unknown Attacker"] -->|"Attack"| B["Unknown Target"]')
        return "\n".join(lines)

    node_ids: dict[str, str] = {}
    for i, entity in enumerate(entities):
        node_id = f"N{i}"
        role = entity.get("role", "context")

        # Build a human-readable node label
        parts = []
        if entity.get("ip"):
            parts.append(entity["ip"])
        if entity.get("host"):
            parts.append(entity["host"])
        if entity.get("user"):
            parts.append(f"user:{entity['user']}")
        if entity.get("geo_country"):
            parts.append(f"({entity['geo_country']})")
        if not parts:
            parts.append(role)

        label_text = "\\n".join(parts[:2])  # keep label short
        safe_label = sanitize_mermaid_label(label_text)
        lines.append(f'  {node_id}[{safe_label}]')

        # Apply style by role
        style = ROLE_STYLES.get(role, ROLE_STYLES["context"])
        style_lines.append(f'  style {node_id} {style}')

        node_ids[node_id] = role

    # Draw edges: attacker → victim(s), pivot → victim(s)
    attacker_ids = [nid for nid, role in node_ids.items() if role == "attacker"]
    victim_ids = [nid for nid, role in node_ids.items() if role == "victim"]
    pivot_ids = [nid for nid, role in node_ids.items() if role == "pivot"]

    edge_label = sanitize_mermaid_label(f"{technique} ({tactic})")

    for src in attacker_ids:
        for dst in victim_ids:
            lines.append(f'  {src} -->|{edge_label}| {dst}')

    for src in attacker_ids:
        for dst in pivot_ids:
            lines.append(f'  {src} -->|"pivot"| {dst}')

    for src in pivot_ids:
        for dst in victim_ids:
            lines.append(f'  {src} -->|"lateral move"| {dst}')

    lines.extend(style_lines)
    return "\n".join(lines)
