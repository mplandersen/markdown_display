#!/usr/bin/env python3
"""
Setup script for PII Detection Model
Ensures all dependencies are properly installed
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed: {description}")
        return False
    
    print(f"✅ Success: {description}")
    return True

def main():
    print("\n🚀 PII Detection Model Setup")
    print("="*60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    # Upgrade pip
    if not run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Upgrading pip"
    ):
        print("⚠️  Warning: Could not upgrade pip, continuing anyway...")
    
    # Install core dependencies first
    core_deps = [
        "numpy>=1.24.0",
        "torch>=2.0.0",
        "transformers>=4.35.0",
    ]
    
    for dep in core_deps:
        if not run_command(
            f"{sys.executable} -m pip install '{dep}'",
            f"Installing {dep.split('>=')[0]}"
        ):
            sys.exit(1)
    
    # Install ONNX dependencies
    onnx_deps = [
        "onnx>=1.15.0",
        "onnxruntime>=1.16.0",
    ]
    
    for dep in onnx_deps:
        if not run_command(
            f"{sys.executable} -m pip install '{dep}'",
            f"Installing {dep.split('>=')[0]}"
        ):
            sys.exit(1)
    
    # Try to install optimum (may fail on some systems)
    print("\n" + "="*60)
    print("🔧 Installing Optimum (optional but recommended)")
    print("="*60)
    
    result = subprocess.run(
        f"{sys.executable} -m pip install 'optimum[exporters]>=1.16.0'",
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("⚠️  Warning: Could not install optimum[exporters]")
        print("   The model conversion will use a fallback method.")
        print("   If you want to try installing it manually:")
        print("   pip install 'optimum[exporters]'")
    else:
        print("✅ Optimum installed successfully")
    
    # Install remaining dependencies
    print("\n" + "="*60)
    print("🔧 Installing remaining dependencies")
    print("="*60)
    
    remaining_deps = [
        "flask>=3.0.0",
        "markdown>=3.5.1",
        "bleach>=6.1.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "tqdm>=4.65.0",
        "requests>=2.31.0",
        "pytest>=7.4.0",
    ]
    
    failed = []
    for dep in remaining_deps:
        if not run_command(
            f"{sys.executable} -m pip install '{dep}'",
            f"Installing {dep.split('>=')[0]}"
        ):
            failed.append(dep)
    
    # Create necessary directories
    print("\n" + "="*60)
    print("🔧 Creating project directories")
    print("="*60)
    
    project_root = Path(__file__).parent.parent
    dirs_to_create = [
        project_root / "models",
        project_root / "static" / "models",
        project_root / ".cache",
        project_root / "logs",
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_path}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Setup Summary")
    print("="*60)
    
    if failed:
        print(f"⚠️  Some packages failed to install: {', '.join(failed)}")
        print("   You may need to install them manually")
    else:
        print("✅ All core dependencies installed successfully!")
    
    print("\n🎯 Next Steps:")
    print("1. Run: python scripts/prepare_model.py")
    print("2. This will download and convert the PII detection model")
    print("3. The process will take 5-10 minutes depending on your connection")
    
    print("\n✨ Setup complete!")

if __name__ == "__main__":
    main() 