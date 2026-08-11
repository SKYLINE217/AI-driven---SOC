"""Playbooks router"""
from fastapi import APIRouter, Depends
from backend.api.deps import get_current_claims

router = APIRouter()

TEMPLATES = [
    {"id": "1", "name": "Brute Force — IP Block + Account Lockout", "technique_category": "T1110", "ioc_variables": ["source_ip", "target_users"]},
    {"id": "2", "name": "Lateral Movement — Network Segmentation", "technique_category": "T1021", "ioc_variables": ["pivot_host_ip", "target_subnet"]},
    {"id": "3", "name": "DDoS Mitigation — Rate Limiting", "technique_category": "T1498", "ioc_variables": ["attacker_cidrs"]},
    {"id": "4", "name": "Privilege Escalation — Account Suspend", "technique_category": "T1548", "ioc_variables": ["user_id", "host"]},
    {"id": "5", "name": "Data Exfiltration — Egress Block", "technique_category": "T1041", "ioc_variables": ["destination_ip", "port"]},
]

@router.get("/templates")
async def get_templates(_claims: dict = Depends(get_current_claims)):
    return TEMPLATES
