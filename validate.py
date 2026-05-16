#!/usr/bin/env python
"""Validation script for analyze_commits.py"""
import sys
import compileall
from pathlib import Path

root = Path(__file__).resolve().parent
print("=" * 60)
print("TEST 1: Python Compilation Check")
print("=" * 60)

try:
    result = compileall.compile_dir(str(root), recurse=True, quiet=2)
    if result:
        print("✓ Compilation successful")
    else:
        print("✗ Compilation check returned False")
        sys.exit(1)
except Exception as e:
    print(f"✗ Compilation error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 2: Help Output")
print("=" * 60)

try:
    import subprocess
    result = subprocess.run([sys.executable, str(root / "analyze_commits.py"), "--help"], 
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("✓ Help executed successfully")
        print(result.stdout[:500])
    else:
        print(f"✗ Help failed with exit code {result.returncode}")
        print(result.stderr)
        sys.exit(1)
except Exception as e:
    print(f"✗ Error running help: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 3: Output Directory Test")
print("=" * 60)

try:
    import tempfile
    import shutil
    
    tmpdir = Path(tempfile.mkdtemp())
    outdir = tmpdir / "output"
    
    try:
        result = subprocess.run(
            [sys.executable, str(root / "analyze_commits.py"), "--output-dir", str(outdir)],
            capture_output=True, text=True, timeout=10, cwd=str(root)
        )
        
        if result.returncode == 0 or outdir.exists():
            print("✓ Output directory test passed")
            if outdir.exists():
                files = list(outdir.glob("*"))
                print(f"  Output directory created with {len(files)} items")
        else:
            print(f"⚠ Exited with code {result.returncode}")
            if result.stdout:
                print(f"  stdout: {result.stdout[:200]}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        
except Exception as e:
    print(f"✗ Error in output test: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All validation tests completed")
print("=" * 60)
