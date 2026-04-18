"""
Standalone test script for the frozen backend EXE
Run this to verify the backend is working correctly
"""

import subprocess
import time
import sys
import requests
from pathlib import Path

def test_backend_exe():
    """Test the frozen backend executable"""
    
    print("="*70)
    print("CraftML Backend EXE Test")
    print("="*70)
    
    # Path to the backend EXE
    backend_exe = Path("dist/craftml-backend.exe")
    
    if not backend_exe.exists():
        print(f"❌ Backend EXE not found at {backend_exe.absolute()}")
        print("   Run the build script first: .\\scripts\\build_desktop.ps1")
        return False
    
    print(f"\n✓ Found backend EXE: {backend_exe.absolute()}")
    print(f"  Size: {backend_exe.stat().st_size / (1024*1024):.2f} MB")
    
    # Start the backend process
    print("\n🚀 Starting backend server...")
    try:
        process = subprocess.Popen(
            [str(backend_exe)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return False
    
    # Wait for server to start
    print("⏳ Waiting for server to start (max 30 seconds)...")
    max_attempts = 30
    server_ready = False
    
    for i in range(max_attempts):
        time.sleep(1)
        try:
            response = requests.get("http://127.0.0.1:5000/docs", timeout=2)
            if response.status_code == 200:
                server_ready = True
                print(f"✅ Server started successfully after {i+1} seconds!")
                break
        except requests.exceptions.RequestException:
            print(f"   Attempt {i+1}/{max_attempts}...", end="\r")
            continue
    
    if not server_ready:
        print(f"\n❌ Server failed to start within {max_attempts} seconds")
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        print("\n📋 Server output:")
        print(stdout)
        if stderr:
            print("\n🔴 Errors:")
            print(stderr)
        return False
    
    # Test API endpoints
    print("\n🧪 Testing API endpoints...")
    
    tests = [
        ("GET", "http://127.0.0.1:5000/docs", "API Documentation"),
        ("GET", "http://127.0.0.1:5000/api/playground/models", "List Models"),
        ("GET", "http://127.0.0.1:5000/api/datasets", "List Datasets"),
        ("GET", "http://127.0.0.1:5000/api/hardware/system", "System Info"),
    ]
    
    passed = 0
    failed = 0
    
    for method, url, name in tests:
        try:
            response = requests.request(method, url, timeout=5)
            if response.status_code in [200, 404]:  # 404 is ok for empty lists
                print(f"   ✓ {name}: {response.status_code}")
                passed += 1
            else:
                print(f"   ✗ {name}: {response.status_code}")
                failed += 1
        except Exception as e:
            print(f"   ✗ {name}: {str(e)[:50]}")
            failed += 1
    
    # Check folders were created
    print("\n📁 Checking production folders...")
    
    import os
    appdata = Path(os.environ.get('APPDATA', ''))
    user_data_dir = appdata / 'CraftML Studio'
    
    folders_to_check = [
        user_data_dir / "resources",
        user_data_dir / "resources" / "models",
        user_data_dir / "resources" / "datasets",
        user_data_dir / "logs",
    ]
    
    for folder in folders_to_check:
        if folder.exists():
            print(f"   ✓ {folder}")
        else:
            print(f"   ✗ {folder} (not created)")
    
    # Stop the server
    print("\n🛑 Stopping server...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary:")
    print(f"  API Tests Passed: {passed}/{passed+failed}")
    print(f"  Server Status: {'✅ Working' if server_ready else '❌ Failed'}")
    print("="*70)
    
    return server_ready and failed == 0

if __name__ == "__main__":
    success = test_backend_exe()
    sys.exit(0 if success else 1)

