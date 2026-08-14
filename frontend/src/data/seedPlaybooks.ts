import type { PlaybookTemplate } from "@/types"

export const PLAYBOOK_CATALOG: PlaybookTemplate[] = [
  { technique:"T1110", name:"Brute Force — IP Block", ioc_vars:["source_ip","target_host","failed_count"], actions:["Block source_ip on edge firewall (DROP)","Lock affected accounts after threshold","Alert SOC channel #critical-alerts"], template:"brute_force.yml.j2" },
  { technique:"T1021", name:"Lateral Movement — Segmentation", ioc_vars:["pivot_host","target_subnet","compromised_user"], actions:["Apply ACL to isolate pivot_host","Revoke compromised_user session tokens","Enable enhanced logging on target_subnet"], template:"lateral_movement.yml.j2" },
  { technique:"T1498", name:"DDoS Mitigation", ioc_vars:["source_cidrs","target_ip","traffic_gbps"], actions:["Rate-limit source_cidrs at upstream router","Activate null-route for saturating CIDRs","Engage upstream scrubbing centre"], template:"ddos_mitigation.yml.j2" },
  { technique:"T1548", name:"Privilege Escalation — Account Suspend", ioc_vars:["user_id","host","escalation_method"], actions:["Disable user_id account immediately","Terminate all active sessions on host","Force password reset on next login"], template:"privesc_account_suspend.yml.j2" },
  { technique:"T1041", name:"Data Exfiltration — Egress Block", ioc_vars:["destination_ip","port","bytes_exfiltrated"], actions:["Block outbound to destination_ip:port","Capture PCAP for forensics (5 min window)","Notify data protection officer"], template:"data_exfil_egress_block.yml.j2" },
  { technique:"T0000", name:"Generic Block", ioc_vars:["entity","threat_type"], actions:["Isolate entity from network","Create forensic snapshot","Escalate to senior analyst"], template:"generic_block.yml.j2" },
]
