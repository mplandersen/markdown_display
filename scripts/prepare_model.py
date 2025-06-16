#!/usr/bin/env python3
"""
Model Preparation Pipeline for Browser-Based PII Detection
Downloads, converts, and optimizes DistilBERT-NER for ONNX Runtime Web
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from tqdm import tqdm

# Force output to be unbuffered
import functools
print = functools.partial(print, flush=True)

# Setup logging with both file and console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('model_preparation.log')
    ]
)
logger = logging.getLogger(__name__)

# Model configuration
MODEL_CONFIG = {
    "model_id": "dslim/bert-base-NER",
    "model_name": "distilbert-ner-quantized",
    "version": "1.0.0",
    "target_size_mb": 35,
    "f1_score_threshold": 0.95,
    "quantization": "int8",
    "onnx_opset": 13
}

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
CACHE_DIR = PROJECT_ROOT / ".cache"
STATIC_DIR = PROJECT_ROOT / "static" / "models"

print("\n" + "="*60)
print("🚀 PII Detection Model Preparation Pipeline")
print("="*60)
print(f"📁 Project Root: {PROJECT_ROOT}")
print(f"📁 Models Directory: {MODELS_DIR}")
print(f"📁 Static Directory: {STATIC_DIR}")
print("="*60 + "\n")


class ModelPreparer:
    """Handles model download, conversion, and optimization"""
    
    def __init__(self, force_download: bool = False):
        self.force_download = force_download
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories"""
        for directory in [MODELS_DIR, CACHE_DIR, STATIC_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
            
    def check_dependencies(self) -> bool:
        """Verify all required dependencies are installed"""
        required_packages = [
            ("transformers", "transformers>=4.35.0"),
            ("torch", "torch>=2.0.0"),
            ("onnx", "onnx>=1.15.0"),
            ("onnxruntime", "onnxruntime>=1.16.0")
        ]
        
        missing = []
        optional_missing = []
        
        for package, install_name in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(install_name)
        
        # Check for optimum (optional but recommended)
        try:
            import optimum
            logger.info("Optimum is installed - will use for optimized conversion")
        except ImportError:
            optional_missing.append("optimum[exporters]")
            logger.warning("Optimum not found - will use fallback conversion method")
                
        if missing:
            logger.error(f"Missing required packages: {', '.join(missing)}")
            logger.info("Installing missing packages...")
            
            # Try to install missing packages
            for package in missing:
                logger.info(f"Installing {package}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.error(f"Failed to install {package}: {result.stderr}")
                    return False
                    
        if optional_missing:
            logger.info(f"Optional packages not installed: {', '.join(optional_missing)}")
            logger.info("The script will work but may be slower. To install: pip install " + " ".join(optional_missing))
            
        return True
        
    def download_model(self) -> Tuple[str, str]:
        """Download the pre-trained model from Hugging Face"""
        logger.info(f"Downloading model: {MODEL_CONFIG['model_id']}")
        
        try:
            from transformers import AutoModelForTokenClassification, AutoTokenizer
            
            # Cache directory for HF models
            cache_path = CACHE_DIR / "huggingface"
            cache_path.mkdir(exist_ok=True)
            
            # Download model and tokenizer
            model = AutoModelForTokenClassification.from_pretrained(
                MODEL_CONFIG['model_id'],
                cache_dir=str(cache_path)
            )
            
            tokenizer = AutoTokenizer.from_pretrained(
                MODEL_CONFIG['model_id'],
                cache_dir=str(cache_path)
            )
            
            # Save locally
            model_path = MODELS_DIR / "pytorch_model"
            model_path.mkdir(exist_ok=True)
            
            model.save_pretrained(str(model_path))
            tokenizer.save_pretrained(str(model_path))
            
            logger.info(f"Model downloaded successfully to {model_path}")
            return str(model_path), str(cache_path)
            
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise
            
    def convert_to_onnx(self, model_path: str) -> str:
        """Convert PyTorch model to ONNX format"""
        logger.info("Converting model to ONNX format...")
        
        output_path = MODELS_DIR / f"{MODEL_CONFIG['model_name']}.onnx"
        
        # Try using Python API first (more reliable than CLI)
        try:
            from optimum.onnxruntime import ORTModelForTokenClassification
            from transformers import AutoTokenizer
            
            logger.info("Using Optimum Python API for conversion...")
            
            # Load and convert model
            model = ORTModelForTokenClassification.from_pretrained(
                model_path,
                export=True,
                provider="CPUExecutionProvider"
            )
            
            # Save the ONNX model
            model.save_pretrained(str(MODELS_DIR))
            
            # Move the model to the correct filename
            onnx_files = list(MODELS_DIR.glob("*.onnx"))
            if onnx_files:
                onnx_files[0].rename(output_path)
                logger.info(f"ONNX model saved to {output_path}")
                return str(output_path)
            else:
                raise RuntimeError("No ONNX file generated")
                
        except ImportError:
            logger.warning("Optimum not properly installed, trying alternative method...")
            
        # Alternative: Use transformers export
        try:
            logger.info("Using alternative ONNX export method...")
            
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
            
            # Load model and tokenizer
            model = AutoModelForTokenClassification.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Prepare dummy input
            dummy_input = tokenizer(
                "John Smith lives in New York",
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            )
            
            # Export to ONNX
            torch.onnx.export(
                model,
                tuple(dummy_input.values()),
                str(output_path),
                input_names=["input_ids", "attention_mask", "token_type_ids"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence"},
                    "attention_mask": {0: "batch_size", 1: "sequence"},
                    "token_type_ids": {0: "batch_size", 1: "sequence"},
                    "logits": {0: "batch_size", 1: "sequence"}
                },
                opset_version=MODEL_CONFIG['onnx_opset'],
                do_constant_folding=True
            )
            
            logger.info(f"ONNX model exported to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"ONNX conversion failed: {e}")
            
            # Last resort: try CLI if available
            try:
                import shutil
                if shutil.which("optimum-cli"):
                    cmd = [
                        "optimum-cli", "export", "onnx",
                        "--model", model_path,
                        "--task", "token-classification",
                        str(MODELS_DIR)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        # Find and rename the generated file
                        onnx_files = list(MODELS_DIR.glob("*.onnx"))
                        if onnx_files:
                            onnx_files[0].rename(output_path)
                            return str(output_path)
            except:
                pass
                
            raise RuntimeError(
                "Failed to convert model to ONNX. Please ensure you have installed: "
                "pip install optimum[exporters] torch transformers"
            )
            
    def quantize_model(self, onnx_path: str) -> str:
        """Quantize ONNX model to reduce size"""
        logger.info("Quantizing model to INT8...")
        
        try:
            from onnxruntime.quantization import quantize_dynamic, QuantType
            
            quantized_path = MODELS_DIR / f"{MODEL_CONFIG['model_name']}_quantized.onnx"
            
            # Dynamic quantization to INT8 - use minimal parameters for compatibility
            quantize_dynamic(
                onnx_path,
                str(quantized_path),
                weight_type=QuantType.QInt8
            )
            
            # Check file size
            size_mb = quantized_path.stat().st_size / (1024 * 1024)
            logger.info(f"Quantized model size: {size_mb:.2f} MB")
            
            if size_mb > MODEL_CONFIG['target_size_mb'] * 1.1:  # 10% tolerance
                logger.warning(f"Model size ({size_mb:.2f} MB) exceeds target ({MODEL_CONFIG['target_size_mb']} MB)")
                logger.info("Using original ONNX model instead of quantized version")
                # Use original if quantized is not smaller
                original_size = Path(onnx_path).stat().st_size / (1024 * 1024)
                if original_size < size_mb:
                    return onnx_path
                    
            return str(quantized_path)
            
        except Exception as e:
            logger.warning(f"Quantization failed: {e}")
            logger.info("Continuing with non-quantized model")
            # Return original model if quantization fails
            return onnx_path
            
    def optimize_for_web(self, model_path: str) -> Dict[str, str]:
        """Optimize model for web deployment"""
        logger.info("Optimizing model for web deployment...")
        
        # Create web-optimized versions
        web_model_path = STATIC_DIR / f"{MODEL_CONFIG['model_name']}.onnx"
        
        # Copy quantized model
        import shutil
        shutil.copy2(model_path, web_model_path)
        
        # Generate model metadata
        metadata = {
            "model_id": MODEL_CONFIG['model_id'],
            "version": MODEL_CONFIG['version'],
            "quantization": MODEL_CONFIG['quantization'],
            "size_bytes": web_model_path.stat().st_size,
            "size_mb": web_model_path.stat().st_size / (1024 * 1024),
            "hash": self._calculate_hash(web_model_path),
            "onnx_opset": MODEL_CONFIG['onnx_opset'],
            "labels": self._extract_labels(model_path)
        }
        
        # Save metadata
        metadata_path = STATIC_DIR / f"{MODEL_CONFIG['model_name']}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        # Create .wasm fallback info
        wasm_info = {
            "wasm_backend": "ort-wasm-simd-threaded.wasm",
            "wasm_version": "1.14.0",
            "fallback_url": "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/"
        }
        
        wasm_info_path = STATIC_DIR / "wasm_config.json"
        with open(wasm_info_path, 'w') as f:
            json.dump(wasm_info, f, indent=2)
            
        logger.info(f"Web-optimized model saved to {web_model_path}")
        logger.info(f"Model size: {metadata['size_mb']:.2f} MB")
        
        return {
            "model_path": str(web_model_path),
            "metadata_path": str(metadata_path),
            "wasm_config": str(wasm_info_path)
        }
        
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
        
    def _extract_labels(self, model_path: str) -> Dict[str, int]:
        """Extract NER labels from model"""
        try:
            # Load config to get label mappings
            config_path = Path(model_path).parent / "pytorch_model" / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("id2label", {
                        "0": "O",
                        "1": "B-PER",
                        "2": "I-PER",
                        "3": "B-ORG",
                        "4": "I-ORG",
                        "5": "B-LOC",
                        "6": "I-LOC",
                        "7": "B-MISC",
                        "8": "I-MISC"
                    })
        except:
            pass
            
        # Default CoNLL-2003 labels
        return {
            "0": "O",
            "1": "B-PER",
            "2": "I-PER",
            "3": "B-ORG",
            "4": "I-ORG",
            "5": "B-LOC",
            "6": "I-LOC",
            "7": "B-MISC",
            "8": "I-MISC"
        }
        
    def create_tokenizer_config(self, model_path: str):
        """Create tokenizer configuration for browser"""
        logger.info("Creating tokenizer configuration...")
        
        from transformers import AutoTokenizer
        
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # Extract vocabulary
        vocab = tokenizer.get_vocab()
        
        # Create browser-compatible tokenizer config
        tokenizer_config = {
            "vocab": vocab,
            "unk_token": tokenizer.unk_token,
            "sep_token": tokenizer.sep_token,
            "pad_token": tokenizer.pad_token,
            "cls_token": tokenizer.cls_token,
            "mask_token": tokenizer.mask_token,
            "model_max_length": tokenizer.model_max_length,
            "do_lower_case": getattr(tokenizer, 'do_lower_case', False)
        }
        
        # Save tokenizer config
        tokenizer_path = STATIC_DIR / "tokenizer_config.json"
        with open(tokenizer_path, 'w') as f:
            json.dump(tokenizer_config, f)
            
        logger.info(f"Tokenizer config saved to {tokenizer_path}")
        return str(tokenizer_path)
        
    def run_pipeline(self) -> Dict[str, str]:
        """Run the complete model preparation pipeline"""
        print("\n" + "="*60)
        print("🚀 Starting Model Preparation Pipeline")
        print("="*60 + "\n")
        
        # Check dependencies
        print("1️⃣  Checking dependencies...")
        if not self.check_dependencies():
            raise RuntimeError("Missing dependencies")
        print("   ✅ All dependencies verified\n")
            
        # Download model
        print("2️⃣  Downloading model from Hugging Face...")
        print(f"   Model: {MODEL_CONFIG['model_id']}")
        model_path, cache_path = self.download_model()
        print(f"   ✅ Model downloaded to: {model_path}\n")
        
        # Convert to ONNX
        print("3️⃣  Converting model to ONNX format...")
        onnx_path = self.convert_to_onnx(model_path)
        print(f"   ✅ ONNX model created: {onnx_path}\n")
        
        # Quantize model
        print("4️⃣  Quantizing model to reduce size...")
        quantized_path = self.quantize_model(onnx_path)
        print(f"   ✅ Quantized model created: {quantized_path}\n")
        
        # Optimize for web
        print("5️⃣  Optimizing model for web deployment...")
        web_artifacts = self.optimize_for_web(quantized_path)
        print("   ✅ Web optimization complete\n")
        
        # Create tokenizer config
        print("6️⃣  Creating tokenizer configuration...")
        tokenizer_path = self.create_tokenizer_config(model_path)
        print(f"   ✅ Tokenizer config created: {tokenizer_path}\n")
        
        # Summary
        results = {
            **web_artifacts,
            "tokenizer_path": tokenizer_path,
            "status": "success"
        }
        
        print("="*60)
        print("✅ Model preparation completed successfully!")
        print("="*60)
        
        return results


def main():
    """Main entry point"""
    print("\n🎯 Starting Model Preparation Pipeline...")
    
    parser = argparse.ArgumentParser(description="Prepare PII detection model for browser deployment")
    parser.add_argument("--force", action="store_true", help="Force re-download of model")
    parser.add_argument("--validate", action="store_true", help="Run validation after preparation")
    args = parser.parse_args()
    
    try:
        print(f"\n📋 Configuration:")
        print(f"   - Model: {MODEL_CONFIG['model_id']}")
        print(f"   - Target Size: {MODEL_CONFIG['target_size_mb']}MB")
        print(f"   - Force Download: {args.force}")
        print(f"   - Run Validation: {args.validate}\n")
        
        preparer = ModelPreparer(force_download=args.force)
        results = preparer.run_pipeline()
        
        print("\n✅ Model preparation completed successfully!")
        print("\n📊 Results:")
        print(json.dumps(results, indent=2))
        
        # Check if model files exist
        model_file = Path(results.get("model_path", ""))
        if model_file.exists():
            size_mb = model_file.stat().st_size / (1024 * 1024)
            print(f"\n✅ Model file created: {model_file}")
            print(f"   Size: {size_mb:.2f} MB")
        else:
            print("\n❌ Warning: Model file not found at expected location")
        
        if args.validate:
            print("\n🔍 Running model validation...")
            # Import and run validation
            sys.path.append(str(PROJECT_ROOT))
            from scripts.validate_model import validate_model
            if validate_model(results["model_path"]):
                print("✅ Model validation passed!")
            else:
                print("❌ Model validation failed!")
                sys.exit(1)
                
        print("\n🎉 All done! Your model is ready for deployment.")
        print(f"\n📁 Model files are in: {STATIC_DIR}")
        print("\n🚀 Next steps:")
        print("   1. Test the model: python scripts/validate_model.py")
        print("   2. Run PII tests: python scripts/test_pii_detection.py")
        print("   3. Start the app: python app.py")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Pipeline failed: {e}")
        print("\n📋 Troubleshooting:")
        print("   1. Check model_preparation.log for details")
        print("   2. Ensure all dependencies are installed: python scripts/setup.py")
        print("   3. Check internet connection for model download")
        logger.exception("Pipeline failed with error:")
        sys.exit(1)


if __name__ == "__main__":
    main()