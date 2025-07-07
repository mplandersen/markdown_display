#!/usr/bin/env python3
"""
Advanced PII Detection Engine
Combines ML model inference with rule-based pattern matching
Supports UK phone numbers and learns from user feedback
"""

import re
import json
import logging
import time
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
        """Convert to dictionary with numpy type conversion"""
        result = asdict(self)
        
        # Convert numpy types to Python types
        for key, value in result.items():
            if isinstance(value, np.integer):
                result[key] = int(value)
            elif isinstance(value, np.floating):
                result[key] = float(value)
            elif isinstance(value, np.ndarray):
                result[key] = value.tolist()
                
        return result


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
            'PERSON': [
                # Names with titles: Dr. John Smith, Mr. Smith, Mrs. Jane Doe
                (re.compile(r'\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Sir|Madam|Lady|Lord|Captain|Major|Colonel|General|Admiral)\.?\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b'), 0.90),
                # Full names: John Smith, Jane Doe, Mary Johnson
                (re.compile(r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b'), 0.75),
                # Names with possessive: John's, Sarah's
                (re.compile(r'\b([A-Z][a-z]{2,})\'s\b'), 0.70),
                # Names after indicators: by John Smith, from Mary
                (re.compile(r'\b(?:by|from|with|dear|sincerely|regards|thanks|signed|written\s+by|authored\s+by|created\s+by|designed\s+by|developed\s+by)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b', re.IGNORECASE), 0.85),
                # Names in quotes: "John Smith", 'Jane Doe'
                (re.compile(r'["\']([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})["\']'), 0.80),
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
                    matched_text = match.group()
                    start = match.start()
                    end = match.end()
                    
                    # For PERSON patterns, extract the captured group if it exists
                    if pii_type == 'PERSON' and match.groups():
                        # Use the captured group (the actual name without title/context)
                        captured_name = match.group(1)
                        if captured_name:
                            # Find the position of the captured name within the full match
                            name_start = text.find(captured_name, start)
                            if name_start != -1:
                                matched_text = captured_name
                                start = name_start
                                end = name_start + len(captured_name)
                            
                            # Additional validation for person names
                            if not self._is_likely_person_name(captured_name):
                                confidence *= 0.5  # Reduce confidence for questionable names
                    
                    if pii_type == 'CREDIT_CARD':
                        # Luhn algorithm validation
                        card_num = re.sub(r'[\s\-]', '', matched_text)
                        if self._validate_credit_card(card_num):
                            confidence = min(confidence + 0.10, 0.99)
                        else:
                            confidence = 0.3  # Low confidence if fails Luhn check
                    
                    entities.append(PIIEntity(
                        text=matched_text,
                        type=pii_type,
                        start=start,
                        end=end,
                        confidence=confidence,
                        source='pattern',
                        context=text[max(0, start-20):min(len(text), end+20)]
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

    def _is_likely_person_name(self, name: str) -> bool:
        """Validate if a string is likely a person's name"""
        if not name or len(name.strip()) < 2:
            return False
            
        words = name.strip().split()
        
        # Common false positives to exclude
        false_positives = {
            'the', 'and', 'or', 'but', 'for', 'with', 'about', 'from', 'to', 'in', 'on', 'at', 'by',
            'this', 'that', 'these', 'those', 'they', 'them', 'their', 'there', 'then', 'than',
            'when', 'where', 'what', 'which', 'who', 'why', 'how', 'can', 'could', 'would', 'should',
            'will', 'shall', 'may', 'might', 'must', 'have', 'has', 'had', 'been', 'being', 'are',
            'was', 'were', 'is', 'am', 'do', 'does', 'did', 'get', 'got', 'make', 'made', 'take',
            'great', 'good', 'new', 'first', 'last', 'long', 'little', 'own', 'other', 'old', 'right',
            'big', 'high', 'different', 'public', 'able', 'possible', 'available', 'important', 'social',
            'special', 'certain', 'personal', 'open', 'real', 'sure', 'whole', 'several', 'united',
            'local', 'human', 'far', 'close', 'year', 'day', 'time', 'week', 'month', 'life', 'world',
            'country', 'state', 'city', 'area', 'community', 'business', 'home', 'family', 'way', 'case',
            'place', 'thing', 'man', 'woman', 'child', 'boy', 'girl', 'student', 'teacher', 'number',
            'part', 'point', 'problem', 'program', 'question', 'system', 'government', 'company', 'group',
            'party', 'money', 'information', 'water', 'room', 'mother', 'father', 'office', 'door',
            'health', 'person', 'art', 'history', 'result', 'change', 'morning', 'reason', 'research',
            'moment', 'air', 'force', 'education', 'foot', 'age', 'nothing', 'everything', 'everyone',
            'someone', 'anyone', 'something', 'anything', 'each', 'every', 'all', 'both', 'either',
            'neither', 'some', 'any', 'many', 'much', 'few', 'more', 'most', 'less', 'least', 'enough',
            'several', 'various', 'different', 'same', 'similar', 'such', 'here', 'there', 'everywhere',
            'somewhere', 'anywhere', 'nowhere', 'above', 'below', 'over', 'under', 'between', 'among',
            'through', 'during', 'before', 'after', 'while', 'until', 'since', 'because', 'although',
            'though', 'however', 'therefore', 'moreover', 'furthermore', 'nevertheless', 'otherwise',
            'instead', 'meanwhile', 'finally', 'certainly', 'probably', 'perhaps', 'maybe', 'definitely',
            'absolutely', 'completely', 'totally', 'entirely', 'fully', 'quite', 'rather', 'very',
            'really', 'truly', 'actually', 'basically', 'generally', 'usually', 'normally', 'typically',
            'commonly', 'frequently', 'often', 'sometimes', 'occasionally', 'rarely', 'seldom', 'never',
            'always', 'forever', 'once', 'twice', 'again', 'also', 'too', 'even', 'only', 'just',
            'almost', 'nearly', 'hardly', 'barely', 'scarcely', 'soon', 'late', 'early', 'quickly',
            'slowly', 'carefully', 'easily', 'simply', 'clearly', 'obviously', 'apparently', 'certainly',
            'exactly', 'precisely', 'approximately', 'roughly', 'around', 'especially', 'particularly',
            'specifically', 'mainly', 'mostly', 'largely', 'primarily', 'chiefly', 'predominantly',
            'principally'
        }
        
        # Check if any word is a common false positive
        if any(word.lower() in false_positives for word in words):
            return False
        
        # Must have at least 2 characters per word
        if any(len(word) < 2 for word in words):
            return False
        
        # Names should not contain numbers
        if any(char.isdigit() for char in name):
            return False
        
        # Names should not be all uppercase (unless short abbreviations)
        if name.isupper() and len(name) > 4:
            return False
        
        # Check against common non-name patterns
        non_name_patterns = [
            r'\b(PDF|HTML|XML|JSON|CSV|DOC|DOCX|XLS|XLSX|PPT|PPTX)\b',  # File formats
            r'\b(HTTP|HTTPS|FTP|SMTP|TCP|UDP|IP|DNS|URL|URI)\b',  # Protocols
            r'\b(CEO|CTO|CFO|COO|VP|SVP|EVP|MD|PhD|MBA|BSc|MSc)\b',  # Titles/Degrees
            r'\b(USA|UK|US|EU|UN|NATO|FBI|CIA|NSA|IRS)\b',  # Organizations/Countries
            r'\b(API|SDK|GUI|UI|UX|AI|ML|DL|NLP|OCR|GPS)\b',  # Tech terms
        ]
        
        for pattern in non_name_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return False
        
        return True


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
        self._initialize_tokenizer()
    
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
    
    def _initialize_tokenizer(self):
        """Initialize the DistilBERT tokenizer"""
        try:
            from transformers import AutoTokenizer
            
            # Use DistilBERT tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-cased')
            logger.info("DistilBERT tokenizer loaded successfully")
            
        except ImportError:
            logger.error("transformers library not available. ML inference will be disabled.")
            self.tokenizer = None
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {e}")
            self.tokenizer = None
    
    def detect(self, text: str) -> List[PIIEntity]:
        """Run ML inference to detect entities"""
        if self.session is None or self.tokenizer is None:
            return []
        
        try:
            # Tokenize text using proper DistilBERT tokenizer
            max_length = 128
            encoded = self.tokenizer(
                text,
                max_length=max_length,
                padding='max_length',
                truncation=True,
                return_tensors='np',
                return_offsets_mapping=True
            )
            
            # Convert to proper format for ONNX
            input_ids = encoded['input_ids'].astype(np.int64)
            attention_mask = encoded['attention_mask'].astype(np.int64)
            token_type_ids = np.zeros_like(input_ids, dtype=np.int64)  # All zeros for single sentence
            
            # Run inference
            outputs = self.session.run(
                None,
                {
                    'input_ids': input_ids,
                    'attention_mask': attention_mask,
                    'token_type_ids': token_type_ids
                }
            )
            
            # Process predictions
            predictions = outputs[0][0]  # Shape: [sequence_length, num_labels]
            
            # Apply softmax to convert logits to probabilities
            def softmax(x):
                exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
                return exp_x / np.sum(exp_x, axis=-1, keepdims=True)
            
            probabilities = softmax(predictions)
            predicted_labels = np.argmax(probabilities, axis=1)
            confidences = np.max(probabilities, axis=1)
            
            # Convert predictions to entities using offset mapping
            entities = []
            current_entity = None
            offset_mapping = encoded['offset_mapping'][0]  # Remove batch dimension
            
            for i, (label_id, confidence) in enumerate(zip(predicted_labels, confidences)):
                # Skip special tokens and padding
                if offset_mapping[i][0] == 0 and offset_mapping[i][1] == 0:
                    continue
                    
                label = self.label_map.get(label_id, 'O')
                start_pos, end_pos = offset_mapping[i]
                
                if label.startswith('B-'):
                    # Start of new entity
                    if current_entity:
                        entities.append(current_entity)
                    
                    entity_type = self._map_entity_type(label[2:])
                    current_entity = {
                        'type': entity_type,
                        'start': int(start_pos),  # Convert numpy int to Python int
                        'end': int(end_pos),      # Convert numpy int to Python int
                        'confidence': float(confidence),  # Convert numpy float to Python float
                        'text': text[int(start_pos):int(end_pos)]  # Ensure slice indices are Python ints
                    }
                
                elif label.startswith('I-') and current_entity:
                    # Continuation of entity
                    entity_type = self._map_entity_type(label[2:])
                    if current_entity['type'] == entity_type:
                        current_entity['end'] = int(end_pos)  # Convert numpy int to Python int
                        current_entity['text'] = text[current_entity['start']:int(end_pos)]  # Ensure slice indices are Python ints
                        current_entity['confidence'] = min(current_entity['confidence'], float(confidence))  # Convert numpy float to Python float
                
                else:
                    # Not an entity or different entity type
                    if current_entity:
                        entities.append(current_entity)
                        current_entity = None
            
            # Don't forget the last entity
            if current_entity:
                entities.append(current_entity)
            
            # Convert to PIIEntity objects
            pii_entities = []
            for ent in entities:
                if ent['confidence'] >= 0.5:  # Basic confidence threshold
                    pii_entities.append(PIIEntity(
                        text=ent['text'],
                        type=ent['type'],
                        start=int(ent['start']),  # Convert numpy int64 to Python int
                        end=int(ent['end']),      # Convert numpy int64 to Python int
                        confidence=float(ent['confidence']),  # Convert numpy float to Python float
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