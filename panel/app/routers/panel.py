"""Panel API endpoints"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path
import logging
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/ca")
async def get_ca_cert(download: bool = False):
    """Get CA certificate for node enrollment"""
    from app.hysteria2_server import Hysteria2Server
    import os
    
    # Resolve certificate path - in Docker, working dir is /app
    # settings.hysteria2_cert_path is "./certs/ca.crt" 
    # We need to resolve it to /app/certs/ca.crt
    cert_path_str = settings.hysteria2_cert_path
    cert_path = Path(cert_path_str)
    
    # If relative path, resolve from current working directory (should be /app in container)
    if not cert_path.is_absolute():
        base_dir = Path(os.getcwd())
        cert_path = base_dir / cert_path
    
    logger.debug(f"Looking for certificate at: {cert_path} (exists: {cert_path.exists()})")
    
    # Ensure parent directory exists
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate certificate if it doesn't exist or is empty
    needs_generation = False
    if not cert_path.exists():
        needs_generation = True
        logger.info(f"CA certificate missing at {cert_path}, generating...")
    elif cert_path.stat().st_size == 0:
        needs_generation = True
        logger.info(f"CA certificate is empty (0 bytes) at {cert_path}, deleting and regenerating...")
        # Delete empty file
        try:
            cert_path.unlink()
        except:
            pass
    
    if needs_generation:
        h2_server = Hysteria2Server()
        # Update paths to use resolved paths
        h2_server.cert_path = str(cert_path)
        h2_server.key_path = str(cert_path.parent / "ca.key")
        await h2_server._generate_certs()
        logger.info(f"Certificate generated at {cert_path}")
    
    if not cert_path.exists():
        raise HTTPException(status_code=500, detail=f"Failed to generate CA certificate at {cert_path}")
    
    # Check if file is empty
    try:
        cert_content = cert_path.read_text()
        logger.debug(f"Certificate file size: {len(cert_content)} bytes")
        if not cert_content or not cert_content.strip():
            raise HTTPException(status_code=500, detail="CA certificate is empty after generation")
    except Exception as e:
        logger.error(f"Error reading certificate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to read certificate: {str(e)}")
    
    # If download parameter is true, return as file download
    if download:
        return FileResponse(
            cert_path,
            media_type="application/x-pem-file",
            filename="ca.crt",
            headers={"Content-Disposition": "attachment; filename=ca.crt"}
        )
    
    # Otherwise return as text (for display/copy in UI)
    return Response(content=cert_content, media_type="text/plain")


@router.get("/health")
async def health():
    """Health check"""
    return {"status": "ok"}

