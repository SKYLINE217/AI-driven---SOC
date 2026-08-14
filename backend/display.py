import sys
import os

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console(force_terminal=True, highlight=False, emoji=False, markup=True)

SEVERITY_COLORS = {
    "critical": "bold red",
    "high":     "red",
    "medium":   "yellow",
    "low":      "green",
}


def print_incident_summary(incident: dict):
    sev = incident.get("severity", "low")
    color = SEVERITY_COLORS.get(sev, "white")
    panel = Panel(
        f"[bold]Entity:[/bold]     {incident.get('entity', '?')}\n"
        f"[bold]Technique:[/bold]  {incident.get('technique', '?')}\n"
        f"[bold]Tactic:[/bold]     {incident.get('tactic', '?')}\n"
        f"[bold]Confidence:[/bold] {incident.get('confidence', 0):.0%}\n"
        f"[bold]Rationale:[/bold]  {str(incident.get('rationale', ''))[:120]}",
        title=f"[{color}]Incident {incident['id']} - {str(sev).upper()}[/{color}]",
        border_style=color,
    )
    console.print(panel)


def print_incident_table(incidents: list):
    table = Table(title="Incidents", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Entity", style="white")
    table.add_column("Technique", style="dim")
    table.add_column("Severity", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Created", style="dim")
    for i in incidents:
        sev = i.get("severity", "low")
        table.add_row(
            str(i["id"])[:8],
            str(i.get("entity", "?")),
            str(i.get("technique", "?")),
            Text(str(sev).upper(), style=SEVERITY_COLORS.get(sev, "white")),
            str(i.get("status", "open")),
            str(i.get("created_at", "?"))[:19],
        )
    console.print(table)


def print_incident_detail(incident: dict):
    print_incident_summary(incident)
    if incident.get("ledger"):
        console.print("\n[bold]Audit Ledger:[/bold]")
        for entry in incident["ledger"]:
            console.print(
                f"  [{str(entry['timestamp'])[:19]}] {entry['action']} "
                f"(hash: {str(entry['this_hash'])[:12]}...)"
            )
