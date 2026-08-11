import { Map } from 'lucide-react'

export default function Navigator() {
  return (
    <div className="page-stub">
      <Map className="page-stub-icon" />
      <h2>MITRE ATT&amp;CK Navigator</h2>
      <p>Interactive heatmap of detected techniques across your incident set.</p>
      <p className="text-xs text-muted">Day 4: Embedded Navigator with live layer.json</p>
    </div>
  )
}
