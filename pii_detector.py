#!/usr/bin/env python3
"""
Advanced PII Detection Engine
Combines ML model inference with rule-based pattern matching
Supports UK phone numbers and learns from user feedback
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force output to be unbuffered
import functools
print = functools.partial(print, flush=True)


@dataclass
class PIIEntity:
    """Represents a detected PII entity"""
    text: str
    type: str
    start: int
    end: int
    confidence: float
    source: str  # 'ml_model', 'pattern', or 'hybrid'
    context: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


class PatternEngine:
    """Rule-based detection for structured PII types"""
    
    def __init__(self):
        self.patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, float]]]:
        """Compile regex patterns for different PII types"""
        return {
            'EMAIL': [
                (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), 0.99),
            ],
            'PHONE_UK': [
                # UK Mobile: 07xxx xxxxxx
                (re.compile(r'\b07\d{3}\s?\d{6}\b'), 0.95),
                # UK Landline with area code: (020) 7946 0958, 020 7946 0958, 020-7946-0958
                (re.compile(r'\b(?:\(0\d{2,4}\)|0\d{2,4})[\s\-]?\d{3,4}[\s\-]?\d{3,4}\b'), 0.93),
                # UK International: +44 20 7946 0958, +44 7700 900123
                (re.compile(r'\+44\s?(?:\(0\)|\b)?\d{2,4}\s?\d{3,4}\s?\d{3,4}\b'), 0.95),
                # UK No spaces: 02079460958
                (re.compile(r'\b0\d{10,11}\b'), 0.85),
            ],
            'SSN_US': [
                # US SSN: 123-45-6789
                (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), 0.95),
                # Without dashes: 123456789 (lower confidence)
                (re.compile(r'\b(?!000|666|9\d{2})\d{3}(?!00)\d{2}(?!0000)\d{4}\b'), 0.70),
            ],
            'CREDIT_CARD': [
                # Credit card with spaces/dashes: 4532 1234 5678 9012
                (re.compile(r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'), 0.85),
            ],
            'DATE': [
                # UK format: DD/MM/YYYY or DD-MM-YYYY
                (re.compile(r'\b(?:0?[1-9]|[12]\d|3[01])[/\-](?:0?[1-9]|1[0-2])[/\-](?:\d{4}|\d{2})\b'), 0.80),
                # US format: MM/DD/YYYY or MM-DD-YYYY
                (re.compile(r'\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:\d{4}|\d{2})\b'), 0.75),
                # Written format: 15 January 2023, Jan 15, 2023
                (re.compile(r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b', re.IGNORECASE), 0.85),
                (re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', re.IGNORECASE), 0.85),
            ],
            'POSTCODE_UK': [
                # UK Postcode: SW1A 1AA, EC1A 1BB, M1 1AE
                (re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', re.IGNORECASE), 0.90),
            ],
            'NI_NUMBER_UK': [
                # UK National Insurance Number: QQ 12 34 56 A
                (re.compile(r'\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-Z]\b', re.IGNORECASE), 0.85),
            ]
        }
        
    def detect(self, text: str) -> List[PIIEntity]:
        """Detect PII using regex patterns"""
        entities = []
        
        for pii_type, patterns in self.patterns.items():
            for pattern, base_confidence in patterns:
                for match in pattern.finditer(text):
                    # Additional validation for specific types
                    confidence = base_confidence
                    
                    if pii_type == 'CREDIT_CARD':
                        # Luhn algorithm validation
                        card_num = re.sub(r'[\s\-]', '', match.group())
                        if self._validate_credit_card(card_num):
                            confidence = min(confidence + 0.10, 0.99)
                        else:
                            confidence = 0.3  # Low confidence if fails Luhn check
                    
                    entities.append(PIIEntity(
                        text=match.group(),
                        type=pii_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        source='pattern',
                        context=text[max(0, match.start()-20):min(len(text), match.end()+20)]
                    ))
                    
        return entities
    
    def _validate_credit_card(self, card_number: str) -> bool:
        """Validate credit card using Luhn algorithm"""
        try:
            digits = [int(d) for d in card_number if d.isdigit()]
            if len(digits) < 13 or len(digits) > 19:
                return False
                
            # Luhn algorithm
            checksum = 0
            for i, digit in enumerate(reversed(digits[:-1])):
                if i % 2 == 0:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                checksum += digit
                
            return (checksum + digits[-1]) % 10 == 0
        except:
            return False


class FeedbackLearner:
    """Learns from user feedback to improve detection accuracy"""
    
    def __init__(self, feedback_file: str = "pii_feedback.json"):
        self.feedback_file = Path(feedback_file)
        self.feedback_data = self._load_feedback()
        
    def _load_feedback(self) -> Dict:
        """Load existing feedback data"""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("Could not load feedback file, starting fresh")
        
        return {
            'corrections': {},  # text -> {correct_type, count}
            'false_positives': {},  # text -> count
            'confidence_adjustments': {},  # pattern -> adjustment
            'stats': {
                'total_corrections': 0,
                'last_updated': None
            }
        }
    
    def record_feedback(self, entity: PIIEntity, feedback_type: str, correct_type: Optional[str] = None):
        """Record user feedback for an entity"""
        key = f"{entity.text}:{entity.type}"
        
        if feedback_type == 'false_positive':
            self.feedback_data['false_positives'][key] = \
                self.feedback_data['false_positives'].get(key, 0) + 1
        
        elif feedback_type == 'correction' and correct_type:
            if key not in self.feedback_data['corrections']:
                self.feedback_data['corrections'][key] = {}
            
            self.feedback_data['corrections'][key][correct_type] = \
                self.feedback_data['corrections'][key].get(correct_type, 0) + 1
        
        self.feedback_data['stats']['total_corrections'] += 1
        self.feedback_data['stats']['last_updated'] = datetime.now().isoformat()
        
        self._save_feedback()
    
    def adjust_confidence(self, entity: PIIEntity) -> float:
        """Adjust confidence based on historical feedback"""
        key = f"{entity.text}:{entity.type}"
        
        # Check false positives
        fp_count = self.feedback_data['false_positives'].get(key, 0)
        if fp_count > 3:
            return entity.confidence * 0.5  # Halve confidence for frequent false positives
        elif fp_count > 0:
            return entity.confidence * (1 - 0.1 * fp_count)  # Reduce by 10% per report
        
        # Check corrections
        if key in self.feedback_data['corrections']:
            corrections = self.feedback_data['corrections'][key]
            total_corrections = sum(corrections.values())
            if total_corrections > 2:
                # This is often misclassified
                return entity.confidence * 0.7
        
        return entity.confidence
    
    def _save_feedback(self):
        """Save feedback data to file"""
        try:
            with open(self.feedback_file, 'w') as f:
                json.dump(self.feedback_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save feedback: {e}")
    
    def get_stats(self) -> Dict:
        """Get feedback statistics"""
        return {
            'total_corrections': self.feedback_data['stats']['total_corrections'],
            'unique_false_positives': len(self.feedback_data['false_positives']),
            'unique_corrections': len(self.feedback_data['corrections']),
            'last_updated': self.feedback_data['stats']['last_updated']
        }


class MLModelInference:
    """Handles ONNX model inference for NER"""
    
    def __init__(self, model_path: str = "static/models/distilbert-ner-quantized.onnx"):
        self.model_path = Path(model_path)
        self.session = None
        self.tokenizer = None
        self.label_map = {
            0: 'O',
            1: 'B-PER',
            2: 'I-PER',
            3: 'B-ORG',
            4: 'I-ORG',
            5: 'B-LOC',
            6: 'I-LOC',
            7: 'B-MISC',
            8: 'I-MISC'
        }
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize ONNX runtime session"""
        try:
            import onnxruntime as ort
            
            logger.info(f"Loading ONNX model from {self.model_path}")
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model not found at {self.model_path}")
            
            # Create inference session
            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=['CPUExecutionProvider']
            )
            
            logger.info("ONNX model loaded successfully")
            
        except ImportError:
            logger.error("onnxruntime not installed. ML inference will be disabled.")
            logger.info("Install with: pip install onnxruntime")
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
    
    def _simple_tokenize(self, text: str) -> Dict:
        """Simple tokenization that mimics BERT tokenizer behavior"""
        # This is a simplified version - in production, you'd load the actual tokenizer
        words = text.split()
        tokens = ['[CLS]']
        word_ids = []
        
        for i, word in enumerate(words):
            # Simple subword tokenization (split on common patterns)
            if len(word) > 5:
                # Split long words
                tokens.extend([word[:len(word)//2], word[len(word)//2:]])
                word_ids.extend([i, i])
            else:
                tokens.append(word.lower())
                word_ids.append(i)
        
        tokens.append('[SEP]')
        word_ids.append(None)
        
        # Create attention mask
        attention_mask = [1] * len(tokens)
        
        # Pad to 128 tokens (typical BERT length)
        max_length = 128
        padding_length = max_length - len(tokens)
        if padding_length > 0:
            tokens.extend(['[PAD]'] * padding_length)
            attention_mask.extend([0] * padding_length)
            word_ids.extend([None] * padding_length)
        else:
            tokens = tokens[:max_length]
            attention_mask = attention_mask[:max_length]
            word_ids = word_ids[:max_length]
        
        # Convert to IDs (simplified - just hash the tokens)
        input_ids = [abs(hash(token)) % 28996 for token in tokens]  # Actual vocab size
        
        # Create token_type_ids (all zeros for single sentence)
        token_type_ids = [0] * len(tokens)
        
        return {
            'input_ids': np.array([input_ids], dtype=np.int64),
            'attention_mask': np.array([attention_mask], dtype=np.int64),
            'token_type_ids': np.array([token_type_ids], dtype=np.int64),  # ADD THIS LINE
            'word_ids': word_ids,
            'words': words
        }
    
    def detect(self, text: str) -> List[PIIEntity]:
        """Run ML inference to detect entities"""
        if self.session is None:
            return []
        
        try:
            # Tokenize text
            inputs = self._simple_tokenize(text)
            
            # Run inference
            outputs = self.session.run(
                None,
                {
                    'input_ids': inputs['input_ids'],
                    'attention_mask': inputs['attention_mask'],
                    'token_type_ids': inputs['token_type_ids']  # ADD THIS LINE
                }
            )
            
            # Process predictions
            predictions = outputs[0][0]  # Shape: [sequence_length, num_labels]
            predicted_labels = np.argmax(predictions, axis=1)
            confidences = np.max(predictions, axis=1)
            
            # Convert predictions to entities
            entities = []
            current_entity = None
            
            for i, (label_id, confidence) in enumerate(zip(predicted_labels, confidences)):
                if i >= len(inputs['word_ids']) or inputs['word_ids'][i] is None:
                    continue
                    
                label = self.label_map.get(label_id, 'O')
                word_idx = inputs['word_ids'][i]
                
                if label.startswith('B-'):
                    # Start of new entity
                    if current_entity:
                        entities.append(current_entity)
                    
                    entity_type = label[2:]
                    current_entity = {
                        'type': self._map_entity_type(entity_type),
                        'text': inputs['words'][word_idx],
                        'confidence': float(confidence),
                        'word_indices': [word_idx]
                    }
                
                elif label.startswith('I-') and current_entity:
                    # Continuation of entity
                    if word_idx not in current_entity['word_indices']:
                        current_entity['text'] += ' ' + inputs['words'][word_idx]
                        current_entity['word_indices'].append(word_idx)
                        current_entity['confidence'] = min(current_entity['confidence'], float(confidence))
                
                else:
                    # Not an entity
                    if current_entity:
                        entities.append(current_entity)
                        current_entity = None
            
            # Don't forget last entity
            if current_entity:
                entities.append(current_entity)
            
            # Convert to PIIEntity objects
            pii_entities = []
            for ent in entities:
                # Find position in original text
                start = text.find(ent['text'])
                if start != -1:
                    pii_entities.append(PIIEntity(
                        text=ent['text'],
                        type=ent['type'],
                        start=start,
                        end=start + len(ent['text']),
                        confidence=ent['confidence'],
                        source='ml_model'
                    ))
            
            return pii_entities
            
        except Exception as e:
            logger.error(f"ML inference failed: {e}")
            return []
    
    def _map_entity_type(self, label: str) -> str:
        """Map model labels to our PII types"""
        mapping = {
            'PER': 'PERSON',
            'ORG': 'ORGANIZATION',
            'LOC': 'LOCATION',
            'MISC': 'MISC'
        }
        return mapping.get(label, label)


class AdvancedPIIDetector:
    """Main PII detection engine combining ML and pattern-based approaches"""
    
    def __init__(self, model_path: Optional[str] = None):
        logger.info("Initializing Advanced PII Detector...")
        
        self.pattern_engine = PatternEngine()
        self.ml_inference = MLModelInference(model_path) if model_path else MLModelInference()
        self.feedback_learner = FeedbackLearner()
        
        # Context patterns for confidence boosting
        self.context_patterns = {
            'PERSON': [
                (re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sir|Lady|Lord)\b', re.IGNORECASE), 0.05),
                (re.compile(r'\b(?:CEO|CTO|Director|Manager|President)\b', re.IGNORECASE), 0.03),
            ],
            'EMAIL': [
                (re.compile(r'\b(?:email|contact|reach)\b', re.IGNORECASE), 0.02),
            ],
            'PHONE_UK': [
                (re.compile(r'\b(?:call|phone|mobile|tel|contact)\b', re.IGNORECASE), 0.03),
            ]
        }
        
        logger.info("PII Detector initialized successfully")
    
    def detect_pii(self, text: str, min_confidence: float = 0.5) -> List[PIIEntity]:
        """
        Detect all PII in the given text
        
        Args:
            text: Input text to analyze
            min_confidence: Minimum confidence threshold (0-1)
            
        Returns:
            List of detected PII entities
        """
        if not text:
            return []
        
        # Get detections from both engines
        pattern_entities = self.pattern_engine.detect(text)
        ml_entities = self.ml_inference.detect(text)
        
        # Combine all entities
        all_entities = pattern_entities + ml_entities
        
        # Apply context boosting
        all_entities = self._apply_context_boost(all_entities, text)
        
        # Apply feedback learning adjustments
        for entity in all_entities:
            entity.confidence = self.feedback_learner.adjust_confidence(entity)
        
        # Resolve overlaps and deduplicate
        final_entities = self._resolve_overlaps(all_entities)
        
        # Filter by minimum confidence
        final_entities = [e for e in final_entities if e.confidence >= min_confidence]
        
        # Sort by position
        final_entities.sort(key=lambda e: e.start)
        
        return final_entities
    
    def _apply_context_boost(self, entities: List[PIIEntity], text: str) -> List[PIIEntity]:
        """Boost confidence based on surrounding context"""
        for entity in entities:
            # Get context window (50 chars before and after)
            context_start = max(0, entity.start - 50)
            context_end = min(len(text), entity.end + 50)
            context = text[context_start:context_end].lower()
            
            # Check context patterns
            if entity.type in self.context_patterns:
                for pattern, boost in self.context_patterns[entity.type]:
                    if pattern.search(context):
                        entity.confidence = min(entity.confidence + boost, 0.99)
        
        return entities
    
    def _resolve_overlaps(self, entities: List[PIIEntity]) -> List[PIIEntity]:
        """Resolve overlapping entities by keeping the highest confidence ones"""
        if not entities:
            return []
        
        # Sort by start position and confidence (descending)
        entities.sort(key=lambda e: (e.start, -e.confidence))
        
        final_entities = []
        last_end = -1
        
        for entity in entities:
            # Check for overlap
            if entity.start >= last_end:
                # No overlap, keep this entity
                final_entities.append(entity)
                last_end = entity.end
            else:
                # Overlap detected
                # Check if this entity has significantly higher confidence
                if final_entities and entity.confidence > final_entities[-1].confidence + 0.1:
                    # Replace previous entity if this one is much more confident
                    final_entities[-1] = entity
                    last_end = entity.end
                elif entity.start >= final_entities[-1].start and entity.end > final_entities[-1].end:
                    # Partial overlap, different types - might be valid
                    if entity.type != final_entities[-1].type:
                        # Keep both if they're different types (e.g., PERSON within ORGANIZATION)
                        final_entities.append(entity)
                        last_end = entity.end
        
        return final_entities
    
    def submit_feedback(self, entity_dict: Dict, feedback_type: str, correct_type: Optional[str] = None):
        """Submit user feedback for an entity"""
        entity = PIIEntity(**entity_dict)
        self.feedback_learner.record_feedback(entity, feedback_type, correct_type)
    
    def get_stats(self) -> Dict:
        """Get detection statistics"""
        return {
            'ml_model_loaded': self.ml_inference.session is not None,
            'pattern_types': list(self.pattern_engine.patterns.keys()),
            'feedback_stats': self.feedback_learner.get_stats()
        }

print("DEBUG: AdvancedPIIDetector class defined successfully")


# Convenience functions for backward compatibility
def create_detector(model_path: Optional[str] = None) -> AdvancedPIIDetector:
    """Create and return a PII detector instance"""
    return AdvancedPIIDetector(model_path)


if __name__ == "__main__":
    # Test the detector
    print("Testing Advanced PII Detector...")
    
    detector = create_detector()
    
    test_texts = [
        "John Smith called from 07700 900123 about his account.",
        "Email jane.doe@example.com or call +44 20 7946 0958.",
        "My NI number is QQ 12 34 56 A and I live at SW1A 1AA.",
        "Card number 4532-1234-5678-9012 expires on 15/03/2025.",
        "Meeting with Apple CEO Tim Cook on January 15, 2024.",
    ]
    
    for text in test_texts:
        print(f"\nText: {text}")
        entities = detector.detect_pii(text)
        for entity in entities:
            print(f"  - {entity.type}: '{entity.text}' (confidence: {entity.confidence:.2%})")