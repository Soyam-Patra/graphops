"""
Central FalkorDB Connection Manager.
Reads environment variables (FALKORDB_URL, FALKORDB_HOST, FALKORDB_PORT, FALKORDB_PASSWORD, FALKORDB_USERNAME)
so that the application seamlessly runs locally, in Docker, on Render, or with FalkorDB Cloud.
"""

import os
from typing import Optional
from falkordb import FalkorDB

def get_falkordb_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None
) -> FalkorDB:
    """
    Returns a connected FalkorDB client, prioritizing environment variables
    for frictionless deployment on Render, Docker, or FalkorDB Cloud.
    """
    url = os.getenv("FALKORDB_URL")
    if url:
        return FalkorDB.from_url(url)

    db_host = os.getenv("FALKORDB_HOST") or host or "localhost"
    db_port_env = os.getenv("FALKORDB_PORT")
    db_port = int(db_port_env) if db_port_env else (port or 6379)
    db_password = os.getenv("FALKORDB_PASSWORD") or password or None
    db_username = os.getenv("FALKORDB_USERNAME") or None

    kwargs = {"host": db_host, "port": db_port}
    if db_password:
        kwargs["password"] = db_password
    if db_username:
        kwargs["username"] = db_username

    return FalkorDB(**kwargs)
