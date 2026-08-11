"""Navigator, Metrics, Playbooks routers"""
from fastapi import APIRouter, Depends
from backend.api.deps import get_current_claims

router = APIRouter()

@router.get("/layer.json")
async def get_navigator_layer(_claims: dict = Depends(get_current_claims)):
    return {
        "name": "SOC Triager Layer",
        "versions": {"attack": "14", "navigator": "4.9"},
        "domain": "enterprise-attack",
        "techniques": [
            {"techniqueID": "T1110", "score": 95, "comment": "Active brute force detected"},
            {"techniqueID": "T1059", "score": 70, "comment": "Suspicious script execution"},
            {"techniqueID": "T1190", "score": 60, "comment": "Exploit attempt logged"},
        ],
    }
