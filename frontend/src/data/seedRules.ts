import type { MitreRule } from "@/types"

export const MITRE_RULES: MitreRule[] = [
  { id:"R001", technique_id:"T1110.001", name:"SSH Brute Force", tactic:"Credential Access", condition:"failed_auth_ratio > 0.8 AND event_count_5m > 10" },
  { id:"R002", technique_id:"T1110.003", name:"Password Spraying", tactic:"Credential Access", condition:"failed_auth_ratio > 0.5 AND dest_ip_fanout > 5 AND event_count_5m > 20" },
  { id:"R003", technique_id:"T1021.004", name:"SSH Lateral Movement", tactic:"Lateral Movement", condition:"source_is_internal AND dest_is_internal AND event_count_5m > 5" },
  { id:"R004", technique_id:"T1041", name:"Exfiltration Over C2 Channel", tactic:"Exfiltration", condition:"bytes_transferred > 1073741824 AND dest_is_external" },
  { id:"R005", technique_id:"T1498", name:"Network DoS", tactic:"Impact", condition:"bytes_transferred > 5368709120 AND distinct_dest_ports < 3" },
  { id:"R006", technique_id:"T1046", name:"Network Port Scan", tactic:"Discovery", condition:"distinct_dest_ports > 500 AND event_count_1m > 200" },
  { id:"R007", technique_id:"T1190", name:"Exploit Public-Facing Application", tactic:"Initial Access", condition:"event_count_1m > 50 AND dest_port IN [80,443,8080,5432]" },
  { id:"R008", technique_id:"T1548.003", name:"Sudo Privilege Escalation", tactic:"Privilege Escalation", condition:"action == 'sudo' AND tod_zscore > 2.5" },
  { id:"R009", technique_id:"T1078", name:"Valid Accounts Misuse", tactic:"Defense Evasion", condition:"geo_velocity_kmh > 800" },
  { id:"R010", technique_id:"T1059.004", name:"Unix Shell Execution", tactic:"Execution", condition:"action == 'shell_spawn' AND parent_process IN ['httpd','nginx','apache2']" },
  { id:"R011", technique_id:"T1071.001", name:"C2 Web Protocol", tactic:"Command and Control", condition:"event_count_5m > 0 AND bytes_transferred < 1024 AND dest_is_external" },
  { id:"R012", technique_id:"T1027", name:"Obfuscated Files", tactic:"Defense Evasion", condition:"event_count_1m > 0 AND action == 'process_inject'" },
  { id:"R013", technique_id:"T1505.003", name:"Web Shell", tactic:"Persistence", condition:"action == 'file_create' AND dest_port IN [80,443]" },
  { id:"R014", technique_id:"T1133", name:"External Remote Services", tactic:"Initial Access", condition:"source_is_external AND dest_port IN [22,3389,5900] AND event_count_5m > 3" },
  { id:"R015", technique_id:"T1562.001", name:"Disable Security Tools", tactic:"Defense Evasion", condition:"action IN ['service_stop','process_kill'] AND process IN ['av','edr','firewall']" },
]
