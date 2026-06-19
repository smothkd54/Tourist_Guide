"""
app.py (root) - redirects to the actual backend.
Run: python backend/app.py
"""
import sys
from pathlib import Path

if __name__ == "__main__":
    backend = str(Path(__file__).parent / "backend" / "app.py")
    print(f"Run the backend directly:\n  python {backend}")
    sys.argv = ["python", backend]
    exec(open(backend).read())
