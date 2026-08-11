import { ClipboardList } from 'lucide-react'

export default function IncidentDetail() {
  return (
    <div className="page-stub">
      <ClipboardList className="page-stub-icon" />
      <h2>Incident Detail</h2>
      <p>5-tab incident view: Overview, Attack Graph, MITRE Technique, Containment Playbook, Audit Trail.</p>
      <p className="text-xs text-muted">Day 4: Full incident detail with all tabs</p>
    </div>
  )
}
