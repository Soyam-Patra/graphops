#!/usr/bin/env bash
set -e

# If FALKORDB_HOST is not set or is localhost/127.0.0.1, start local FalkorDB daemon
if [ -z "$FALKORDB_HOST" ] || [ "$FALKORDB_HOST" = "localhost" ] || [ "$FALKORDB_HOST" = "127.0.0.1" ]; then
    echo "[*] Starting embedded FalkorDB instance..."
    mkdir -p /var/lib/falkordb/data
    redis-server --protected-mode no --dir /var/lib/falkordb/data --loadmodule /var/lib/falkordb/bin/falkordb.so --daemonize yes
    
    # Wait for FalkorDB to accept connections
    echo "[*] Waiting for FalkorDB on port 6379..."
    for i in $(seq 1 30); do
        if python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 6379)); s.close()" 2>/dev/null; then
            echo "[+] FalkorDB is online and healthy!"
            break
        fi
        sleep 1
    done

    # Pre-seed graphs
    echo "[*] Pre-seeding FalkorDB graphs..."
    python scripts/seed_company_brain.py || echo "[!] Company Brain seed finished"
else
    echo "[*] Using external FalkorDB at: $FALKORDB_HOST"
fi

# Determine HTTP Port (Render sets $PORT, default to 10000)
TARGET_PORT="${PORT:-10000}"
echo "[*] Launching GraphOps on port ${TARGET_PORT}..."

exec uvicorn src.api:app --host 0.0.0.0 --port "${TARGET_PORT}"
