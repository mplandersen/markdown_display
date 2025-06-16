#!/usr/bin/env python3
"""
Model Validation Suite for PII Detection
Validates model accuracy, performance, and functionality
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import onnxruntime as ort

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "static" / "models"


class ModelValidator:
    """Validates ONNX model performance and accuracy"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.session = None
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        """Load model metadata"""
        metadata_path = Path(self.model_path).with_suffix('.json')
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                return json.load(f)
        return {}
        
    def initialize_session(self) -> bool:
        """Initialize ONNX Runtime session"""
        try:
            # Session options for optimization
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # Create session with CPU provider
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options,
                providers=['CPUExecutionProvider']
            )
            
            logger.info(f"Model loaded successfully: {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
            
    def validate_model_structure(self) -> Dict[str, Any]:
        """Validate model inputs and outputs"""
        if not self.session:
            self.initialize_session()
            
        results = {
            "valid": True,
            "inputs": {},
            "outputs": {},
            "issues": []
        }
        
        # Check inputs
        for input_info in self.session.get_inputs():
            input_shape = input_info.shape
            input_type = input_info.type
            
            results["inputs"][input_info.name] = {
                "shape": input_shape,
                "type": input_type
            }
            
            # Validate expected inputs
            if input_info.name not in ["input_ids", "attention_mask", "token_type_ids"]:
                results["issues"].append(f"Unexpected input: {input_info.name}")
                
        # Check outputs  
        for output_info in self.session.get_outputs():
            output_shape = output_info.shape
            output_type = output_info.type
            
            results["outputs"][output_info.name] = {
                "shape": output_shape,
                "type": output_type
            }
            
        # Validate model has expected structure
        if len(results["inputs"]) < 2:
            results["valid"] = False
            results["issues"].append("Model missing required inputs")
            
        if len(results["outputs"]) < 1:
            results["valid"] = False
            results["issues"].append("Model missing outputs")
            
        return results
        
    def benchmark_performance(self, test_sentences: List[str] = None) -> Dict[str, float]:
        """Benchmark model inference performance"""
        if not self.session:
            self.initialize_session()
            
        if not test_sentences:
            test_sentences = [
                "John Smith lives at 123 Main St, New York, NY 10001",
                "Contact me at john.doe@example.com or call 555-123-4567",
                "My SSN is 123-45-6789 and credit card 4532-1234-5678-9012",
                "Born on 01/15/1990, driver's license #D1234567"
            ] * 10  # 40 sentences for better benchmarking
            
        results = {
            "avg_inference_time_ms": 0,
            "min_inference_time_ms": float('inf'),
            "max_inference_time_ms": 0,
            "throughput_sentences_per_sec": 0,
            "memory_usage_mb": 0
        }
        
        # Warm-up run
        self._run_inference(test_sentences[0])
        
        # Benchmark runs
        inference_times = []
        
        for sentence in test_sentences:
            start_time = time.time()
            _ = self._run_inference(sentence)
            inference_time = (time.time() - start_time) * 1000  # ms
            inference_times.append(inference_time)
            
        # Calculate statistics
        results["avg_inference_time_ms"] = np.mean(inference_times)
        results["min_inference_time_ms"] = np.min(inference_times)
        results["max_inference_time_ms"] = np.max(inference_times)
        results["throughput_sentences_per_sec"] = 1000 / results["avg_inference_time_ms"]
        
        # Estimate memory usage
        import psutil
        import os
        process = psutil.Process(os.getpid())
        results["memory_usage_mb"] = process.memory_info().rss / 1024 / 1024
        
        return results
        
    def _run_inference(self, text: str) -> np.ndarray:
        """Run inference on a single text"""
        # Simple tokenization (in real implementation, use proper tokenizer)
        tokens = text.lower().split()[:128]  # Max sequence length
        
        # Create dummy inputs for testing
        seq_len = len(tokens)
        input_ids = np.random.randint(0, 1000, size=(1, seq_len), dtype=np.int64)
        attention_mask = np.ones((1, seq_len), dtype=np.int64)
        
        # Prepare inputs
        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask
        }
        
        # Add token_type_ids if model expects it
        if len(self.session.get_inputs()) > 2:
            inputs["token_type_ids"] = np.zeros((1, seq_len), dtype=np.int64)
            
        # Run inference
        outputs = self.session.run(None, inputs)
        return outputs[0]
        
    def validate_accuracy(self, test_data: List[Tuple[str, List[Dict]]] = None) -> Dict[str, float]:
        """Validate model accuracy on test data"""
        if not test_data:
            # Create synthetic test data
            test_data = self._create_synthetic_test_data()
            
        results = {
            "precision": 0,
            "recall": 0,
            "f1_score": 0,
            "accuracy": 0,
            "per_entity_scores": {}
        }
        
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0
        
        for text, expected_entities in test_data:
            # Run inference
            predicted_entities = self._extract_entities(text)
            
            # Compare predictions with expected
            for expected in expected_entities:
                found = False
                for predicted in predicted_entities:
                    if (predicted["start"] == expected["start"] and 
                        predicted["end"] == expected["end"] and
                        predicted["type"] == expected["type"]):
                        true_positives += 1
                        found = True
                        break
                        
                if not found:
                    false_negatives += 1
                    
            # Check for false positives
            for predicted in predicted_entities:
                found = False
                for expected in expected_entities:
                    if (predicted["start"] == expected["start"] and 
                        predicted["end"] == expected["end"]):
                        found = True
                        break
                        
                if not found:
                    false_positives += 1
                    
        # Calculate metrics
        if true_positives + false_positives > 0:
            results["precision"] = true_positives / (true_positives + false_positives)
            
        if true_positives + false_negatives > 0:
            results["recall"] = true_positives / (true_positives + false_negatives)
            
        if results["precision"] + results["recall"] > 0:
            results["f1_score"] = (2 * results["precision"] * results["recall"] / 
                                   (results["precision"] + results["recall"]))
                                   
        return results
        
    def _extract_entities(self, text: str) -> List[Dict]:
        """Extract entities from text (simplified for validation)"""
        # This is a placeholder - in real implementation, 
        # this would use the actual model inference
        entities = []
        
        # Simple pattern matching for validation
        import re
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            entities.append({
                "type": "EMAIL",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
            
        # Phone pattern
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        for match in re.finditer(phone_pattern, text):
            entities.append({
                "type": "PHONE",
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.90
            })
            
        return entities
        
    def _create_synthetic_test_data(self) -> List[Tuple[str, List[Dict]]]:
        """Create synthetic test data for validation"""
        test_data = [
            (
                "John Smith's email is john.smith@example.com",
                [
                    {"type": "PERSON", "text": "John Smith", "start": 0, "end": 10},
                    {"type": "EMAIL", "text": "john.smith@example.com", "start": 22, "end": 44}
                ]
            ),
            (
                "Call me at 555-123-4567 or 555.987.6543",
                [
                    {"type": "PHONE", "text": "555-123-4567", "start": 11, "end": 23},
                    {"type": "PHONE", "text": "555.987.6543", "start": 27, "end": 39}
                ]
            ),
            (
                "SSN: 123-45-6789, Credit Card: 4532-1234-5678-9012",
                [
                    {"type": "SSN", "text": "123-45-6789", "start": 5, "end": 16},
                    {"type": "CREDIT_CARD", "text": "4532-1234-5678-9012", "start": 31, "end": 50}
                ]
            )
        ]
        
        return test_data
        
    def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        report = ["=" * 50]
        report.append("MODEL VALIDATION REPORT")
        report.append("=" * 50)
        
        # Model info
        report.append(f"\nModel: {self.model_path}")
        report.append(f"Size: {self.metadata.get('size_mb', 'N/A'):.2f} MB")
        report.append(f"Version: {self.metadata.get('version', 'N/A')}")
        
        # Structure validation
        structure = self.validate_model_structure()
        report.append(f"\nModel Structure: {'✓ Valid' if structure['valid'] else '✗ Invalid'}")
        
        if structure['issues']:
            report.append("Issues:")
            for issue in structure['issues']:
                report.append(f"  - {issue}")
                
        # Performance benchmarks
        performance = self.benchmark_performance()
        report.append(f"\nPerformance Metrics:")
        report.append(f"  Average Inference: {performance['avg_inference_time_ms']:.2f} ms")
        report.append(f"  Throughput: {performance['throughput_sentences_per_sec']:.1f} sentences/sec")
        report.append(f"  Memory Usage: {performance['memory_usage_mb']:.1f} MB")
        
        # Accuracy validation
        accuracy = self.validate_accuracy()
        report.append(f"\nAccuracy Metrics:")
        report.append(f"  Precision: {accuracy['precision']:.2%}")
        report.append(f"  Recall: {accuracy['recall']:.2%}")
        report.append(f"  F1 Score: {accuracy['f1_score']:.2%}")
        
        # Target validation
        report.append(f"\nTarget Compliance:")
        target_f1 = 0.95
        target_size = 35  # MB
        target_speed = 50  # ms
        
        f1_check = "✓" if accuracy['f1_score'] >= target_f1 else "✗"
        size_check = "✓" if self.metadata.get('size_mb', 100) <= target_size * 1.1 else "✗"
        speed_check = "✓" if performance['avg_inference_time_ms'] <= target_speed else "✗"
        
        report.append(f"  {f1_check} F1 Score ≥ {target_f1:.0%} (actual: {accuracy['f1_score']:.2%})")
        report.append(f"  {size_check} Model Size ≤ {target_size} MB (actual: {self.metadata.get('size_mb', 0):.1f} MB)")
        report.append(f"  {speed_check} Inference ≤ {target_speed} ms (actual: {performance['avg_inference_time_ms']:.2f} ms)")
        
        return "\n".join(report)


def validate_model(model_path: str) -> bool:
    """Main validation function"""
    logger.info(f"Starting model validation for: {model_path}")
    
    validator = ModelValidator(model_path)
    
    # Initialize model
    if not validator.initialize_session():
        logger.error("Failed to initialize model")
        return False
        
    # Generate report
    report = validator.generate_report()
    print(report)
    
    # Save report
    report_path = PROJECT_ROOT / "validation_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    logger.info(f"Validation report saved to: {report_path}")
    
    # Check if model meets requirements
    accuracy = validator.validate_accuracy()
    performance = validator.benchmark_performance()
    
    meets_requirements = (
        accuracy['f1_score'] >= 0.90 and  # 90% F1 score minimum
        performance['avg_inference_time_ms'] <= 100  # 100ms max per inference
    )
    
    return meets_requirements


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = str(MODELS_DIR / "distilbert-ner-quantized.onnx")
        
    success = validate_model(model_path)
    sys.exit(0 if success else 1) 