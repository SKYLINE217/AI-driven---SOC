import { BookOpen } from 'lucide-react'

export default function PlaybookLibrary() {
  return (
    <div className="page-stub">
      <BookOpen className="page-stub-icon" />
      <h2>Playbook Library</h2>
      <p>Catalog of containment templates: brute force, lateral movement, DDoS, privilege escalation, exfiltration.</p>
      <p className="text-xs text-muted">Day 4: Full template catalog with Jinja2 source viewer</p>
    </div>
  )
}
