"""
Tests for file ingestor.
"""
from backend.ingestion.file_ingestor import ingest_file
import tempfile
import os

def test_ingest_file_syslog():
    log_content = "Dec 10 09:12:45 host sudo: pam_unix(sudo:auth): authentication failure; logname= uid=0 euid=0 tty=/dev/pts/1 ruser= rhost=  user=root\n"
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(log_content)
        temp_path = f.name
        
    try:
        events = ingest_file(temp_path, "syslog")
        assert len(events) == 1
        assert events[0]["event"]["category"] == ["process"]
        assert events[0]["event"]["outcome"] == "unknown"
    finally:
        os.unlink(temp_path)
