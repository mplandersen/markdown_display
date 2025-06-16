#!/usr/bin/env python3
"""
Quick script to check if model preparation was successful
"""

import os
import json
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def check_file(path, description):
    """Check if a file exists and show its size"""
    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"{Colors.GREEN}✅ {description}{Colors.END}")
        print(f"   Path: {path}")
        print(f"   Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"{Colors.RED}❌ {description}{Colors.END}")
        print(f"   Expected at: {path}")
        return False

def main():
    print("\n" + "="*60)
    print("🔍 PII Model Preparation Check")
    print("="*60 + "\n")
    
    # Define paths
    project_root = Path(__file__).parent.parent
    models_dir = project_root / "models"
    static_models_dir = project_root / "static" / "models"
    
    print(f"📁 Project Root: {project_root}\n")
    
    # Check directories
    print("📂 Checking directories:")
    dirs_ok = True
    for dir_path, name in [(models_dir, "Models Directory"), 
                           (static_models_dir, "Static Models Directory")]:
        if dir_path.exists():
            print(f"{Colors.GREEN}✅ {name} exists{Colors.END}: {dir_path}")
        else:
            print(f"{Colors.RED}❌ {name} missing{Colors.END}: {dir_path}")
            dirs_ok = False
    
    print("\n📄 Checking model files:")
    
    # Expected files
    files_to_check = [
        (static_models_dir / "distilbert-ner-quantized.onnx", "ONNX Model"),
        (static_models_dir / "distilbert-ner-quantized.json", "Model Metadata"),
        (static_models_dir / "tokenizer_config.json", "Tokenizer Config"),
        (static_models_dir / "wasm_config.json", "WASM Config"),
    ]
    
    all_ok = True
    for file_path, description in files_to_check:
        if not check_file(file_path, description):
            all_ok = False
        print()
    
    # Check model metadata
    metadata_path = static_models_dir / "distilbert-ner-quantized.json"
    if metadata_path.exists():
        print("📊 Model Metadata:")
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            print(f"   Model ID: {metadata.get('model_id', 'Unknown')}")
            print(f"   Version: {metadata.get('version', 'Unknown')}")
            print(f"   Size: {metadata.get('size_mb', 'Unknown'):.2f} MB")
            print(f"   Quantization: {metadata.get('quantization', 'Unknown')}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Could not read metadata: {e}{Colors.END}")
    
    # Check log file
    print("\n📋 Checking logs:")
    log_file = project_root / "model_preparation.log"
    if log_file.exists():
        print(f"{Colors.GREEN}✅ Log file exists{Colors.END}: {log_file}")
        # Show last few lines
        with open(log_file, 'r') as f:
            lines = f.readlines()
            if lines:
                print("\n   Last log entries:")
                for line in lines[-5:]:
                    print(f"   {line.strip()}")
    else:
        print(f"{Colors.YELLOW}⚠️  No log file found{Colors.END}")
    
    # Summary
    print("\n" + "="*60)
    if all_ok and dirs_ok:
        print(f"{Colors.GREEN}✅ All model files are present!{Colors.END}")
        print("\nYour model is ready for use. Next steps:")
        print("1. Run validation: python scripts/validate_model.py")
        print("2. Start the app: python app.py")
    else:
        print(f"{Colors.RED}❌ Some files are missing!{Colors.END}")
        print("\nTo fix this:")
        print("1. Check if the model preparation script completed successfully")
        print("2. Run: python scripts/prepare_model.py")
        print("3. Check model_preparation.log for errors")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()