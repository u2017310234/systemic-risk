"""Compatibility launcher. Use risk_mcp.server:app for ASGI imports."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk_mcp.server import app, main
if __name__ == "__main__":
    main()
