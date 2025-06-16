from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import markdown
import bleach
import re
import os
import random
import tempfile
import io
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for redaction functionality

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['MODEL_VERSION'] = '1.0.0'

# Paths
PROJECT_ROOT = Path(__file__).parent
STATIC_DIR = PROJECT_ROOT / 'static'
MODELS_DIR = STATIC_DIR / 'models'

# Ensure directories exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed HTML tags and attributes for security
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img', 'hr'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
    '*': ['class']
}

def preprocess_markdown(text):
    """Fix markdown formatting to ensure lists and paragraphs are properly parsed"""
    # First, normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    lines = text.split('\n')
    processed_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Check if current line is a list item (bullet or numbered)
        is_list_item = bool(re.match(r'^\s*[-*+]\s+', line) or re.match(r'^\s*\d+\.\s+', line))
        
        # Check previous line context
        if i > 0:
            prev_line = lines[i-1].strip()
            prev_is_empty = prev_line == ''
            prev_is_list = bool(re.match(r'^\s*[-*+]\s+', lines[i-1]) or re.match(r'^\s*\d+\.\s+', lines[i-1]))
            
            # If this is a list item and previous line is not empty and not a list item
            if is_list_item and prev_line and not prev_is_empty and not prev_is_list:
                processed_lines.append('')  # Add blank line before list
        
        # Check if next line context for paragraph breaks
        if i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            next_is_list = bool(re.match(r'^\s*[-*+]\s+', next_line) or re.match(r'^\s*\d+\.\s+', next_line))
            
            # If current line has content and next line is a list, ensure proper spacing
            if line.strip() and next_is_list and not is_list_item:
                processed_lines.append(line)
                processed_lines.append('')  # Add blank line before list
                i += 1
                continue
        
        processed_lines.append(line)
        i += 1
    
    result = '\n'.join(processed_lines)
    return result

def extract_names(text):
    """Extract potential names from text using comprehensive regex patterns"""
    names = set()
    
    # Common false positives to exclude
    false_positives = {
        'the', 'and', 'or', 'but', 'for', 'with', 'about', 'from', 'to', 'in', 'on', 'at', 'by',
        'this', 'that', 'these', 'those', 'they', 'them', 'their', 'there', 'then', 'than',
        'when', 'where', 'what', 'which', 'who', 'why', 'how', 'can', 'could', 'would', 'should',
        'will', 'shall', 'may', 'might', 'must', 'have', 'has', 'had', 'been', 'being', 'are',
        'was', 'were', 'is', 'am', 'do', 'does', 'did', 'get', 'got', 'make', 'made', 'take',
        'took', 'come', 'came', 'go', 'went', 'see', 'saw', 'know', 'knew', 'think', 'thought',
        'say', 'said', 'tell', 'told', 'ask', 'asked', 'give', 'gave', 'put', 'set', 'let',
        'use', 'used', 'find', 'found', 'work', 'worked', 'call', 'called', 'try', 'tried',
        'need', 'needed', 'feel', 'felt', 'seem', 'seemed', 'leave', 'left', 'move', 'moved',
        'turn', 'turned', 'start', 'started', 'show', 'showed', 'play', 'played', 'run', 'ran',
        'walk', 'walked', 'sit', 'sat', 'stand', 'stood', 'lose', 'lost', 'pay', 'paid',
        'meet', 'met', 'include', 'including', 'follow', 'following', 'stop', 'stopped',
        'create', 'created', 'speak', 'spoke', 'read', 'write', 'wrote', 'provide', 'provided',
        'allow', 'allowed', 'help', 'helped', 'move', 'moved', 'live', 'lived', 'believe',
        'believed', 'hold', 'held', 'bring', 'brought', 'happen', 'happened', 'write', 'wrote',
        'sit', 'sat', 'stand', 'stood', 'hear', 'heard', 'let', 'put', 'say', 'said', 'mean',
        'meant', 'keep', 'kept', 'begin', 'began', 'seem', 'seemed', 'help', 'helped', 'talk',
        'talked', 'turn', 'turned', 'start', 'started', 'might', 'right', 'still', 'small',
        'large', 'great', 'good', 'new', 'first', 'last', 'long', 'little', 'own', 'other',
        'old', 'right', 'big', 'high', 'different', 'following', 'public', 'able', 'possible',
        'available', 'important', 'social', 'special', 'certain', 'personal', 'open', 'red',
        'top', 'common', 'whole', 'several', 'united', 'local', 'sure', 'real', 'left', 'least',
        'human', 'far', 'close', 'hand', 'eye', 'year', 'day', 'time', 'week', 'month', 'life',
        'world', 'country', 'state', 'city', 'area', 'community', 'name', 'business', 'home',
        'family', 'lot', 'fact', 'way', 'case', 'place', 'thing', 'man', 'woman', 'child',
        'boy', 'girl', 'student', 'teacher', 'number', 'part', 'point', 'problem', 'program',
        'question', 'system', 'government', 'company', 'group', 'party', 'money', 'information',
        'water', 'room', 'mother', 'father', 'office', 'door', 'health', 'person', 'art',
        'history', 'party', 'result', 'change', 'morning', 'reason', 'research', 'girl', 'guy',
        'moment', 'air', 'teacher', 'force', 'education', 'foot', 'boy', 'age', 'nothing',
        'everything', 'everyone', 'someone', 'anyone', 'something', 'anything', 'nothing',
        'each', 'every', 'all', 'both', 'either', 'neither', 'some', 'any', 'many', 'much',
        'few', 'little', 'more', 'most', 'less', 'least', 'enough', 'several', 'various',
        'different', 'same', 'similar', 'such', 'here', 'there', 'everywhere', 'somewhere',
        'anywhere', 'nowhere', 'above', 'below', 'over', 'under', 'between', 'among', 'through',
        'during', 'before', 'after', 'while', 'until', 'since', 'because', 'although', 'though',
        'however', 'therefore', 'moreover', 'furthermore', 'nevertheless', 'otherwise', 'instead',
        'meanwhile', 'finally', 'certainly', 'probably', 'perhaps', 'maybe', 'definitely',
        'absolutely', 'completely', 'totally', 'entirely', 'fully', 'quite', 'rather', 'pretty',
        'very', 'really', 'truly', 'actually', 'basically', 'generally', 'usually', 'normally',
        'typically', 'commonly', 'frequently', 'often', 'sometimes', 'occasionally', 'rarely',
        'seldom', 'never', 'always', 'forever', 'once', 'twice', 'again', 'also', 'too', 'even',
        'only', 'just', 'almost', 'nearly', 'hardly', 'barely', 'scarcely', 'soon', 'late',
        'early', 'quickly', 'slowly', 'carefully', 'easily', 'simply', 'clearly', 'obviously',
        'apparently', 'certainly', 'possibly', 'probably', 'definitely', 'absolutely', 'exactly',
        'precisely', 'approximately', 'roughly', 'about', 'around', 'nearly', 'almost', 'quite',
        'rather', 'fairly', 'pretty', 'very', 'extremely', 'incredibly', 'remarkably', 'especially',
        'particularly', 'specifically', 'generally', 'basically', 'essentially', 'mainly', 'mostly',
        'largely', 'primarily', 'chiefly', 'predominantly', 'principally', 'especially', 'particularly'
    }
    
    # Common titles and prefixes to help identify names
    titles = r'(?:Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Sir|Madam|Lady|Lord|Captain|Major|Colonel|General|Admiral)\.?'
    
    # Pattern 1: Full names with titles and suffixes
    # Examples: Dr. John Smith, Mary Johnson Jr., Prof. Sarah Wilson
    full_name_pattern = rf'\b{titles}\s+([A-Z][a-z]{{2,}}\s+[A-Z][a-z]{{2,}}(?:\s+(?:Jr|Sr|II|III|IV)\.?)?)\b'
    titled_names = re.findall(full_name_pattern, text, re.IGNORECASE)
    for name in titled_names:
        clean_name = name.strip()
        if clean_name:
            names.add(clean_name)
    
    # Pattern 2: Common name patterns - First Last format
    # More flexible capitalization pattern
    name_pattern = r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b'
    potential_names = re.findall(name_pattern, text)
    
    for name in potential_names:
        words = name.strip().split()
        if len(words) >= 2:  # At least first and last name
            # Check if any word is a common false positive
            if not any(word.lower() in false_positives for word in words):
                # Additional checks for likely names
                if is_likely_name(name):
                    names.add(name.strip())
    
    # Pattern 3: Names in possessive form
    possessive_pattern = r'\b([A-Z][a-z]{2,})\'s\b'
    possessive_names = re.findall(possessive_pattern, text)
    for name in possessive_names:
        if name.lower() not in false_positives and is_likely_name(name):
            names.add(name)
    
    # Pattern 4: Names after common indicators
    indicator_pattern = r'\b(?:by|from|with|dear|hello|hi|sincerely|regards|thanks|signed|written\s+by|authored\s+by|created\s+by|designed\s+by|developed\s+by)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b'
    indicated_names = re.findall(indicator_pattern, text, re.IGNORECASE)
    for name in indicated_names:
        clean_name = name.strip()
        if clean_name.lower() not in false_positives and is_likely_name(clean_name):
            names.add(clean_name)
    
    # Pattern 5: Email-based names (extract from email addresses)
    email_pattern = r'\b([a-zA-Z]{2,})[._-]([a-zA-Z]{2,})@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    email_names = re.findall(email_pattern, text)
    for first, last in email_names:
        if len(first) > 2 and len(last) > 2:
            full_name = f"{first.capitalize()} {last.capitalize()}"
            if not any(word.lower() in false_positives for word in [first, last]):
                names.add(full_name)
    
    # Pattern 6: Quoted names or names in parentheses
    quoted_pattern = r'["\']([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})["\']'
    quoted_names = re.findall(quoted_pattern, text)
    for name in quoted_names:
        if is_likely_name(name):
            names.add(name)
    
    return list(names)

def is_likely_name(name):
    """Additional validation to determine if a string is likely a person's name"""
    words = name.strip().split()
    
    # Must have at least 2 characters per word
    if any(len(word) < 2 for word in words):
        return False
    
    # Check for common name patterns
    # Names should not contain numbers
    if any(char.isdigit() for char in name):
        return False
    
    # Names should not be all uppercase (unless abbreviations)
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

def extract_emails(text):
    """Extract email addresses from text with improved pattern"""
    # More comprehensive email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = set(re.findall(email_pattern, text))
    return list(emails)

def extract_phone_numbers(text):
    """Extract phone numbers from text"""
    phone_patterns = [
        r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',  # US format
        r'\b\+?[1-9]\d{1,14}\b',  # International format
        r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b',  # XXX-XXX-XXXX
        r'\(\d{3}\)\s?\d{3}[-.\s]\d{4}',  # (XXX) XXX-XXXX
    ]
    
    phones = set()
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                # Reconstruct full number from groups
                phone = ''.join(match)
                if len(phone) >= 10:  # Valid phone numbers should be at least 10 digits
                    phones.add(phone)
            else:
                phones.add(match)
    
    return list(phones)

def extract_addresses(text):
    """Extract potential addresses from text"""
    # Simple address pattern - could be enhanced further
    address_patterns = [
        r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Place|Pl)\b',
        r'\b\d+\s+[A-Z]\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Place|Pl)\.?\s*,?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
    ]
    
    addresses = set()
    for pattern in address_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        addresses.update(matches)
    
    return list(addresses)

def extract_ssn(text):
    """Extract Social Security Numbers"""
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    ssns = re.findall(ssn_pattern, text)
    return ssns

def extract_dates(text):
    """Extract dates that might be birthdates or sensitive dates"""
    date_patterns = [
        r'\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:\d{4}|\d{2})\b',  # MM/DD/YYYY or MM-DD-YYYY
        r'\b(?:0?[1-9]|[12]\d|3[01])[/\-](?:0?[1-9]|1[0-2])[/\-](?:\d{4}|\d{2})\b',  # DD/MM/YYYY or DD-MM-YYYY
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
    ]
    
    dates = set()
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.update(matches)
    
    return list(dates)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_markdown():
    try:
        data = request.get_json()
        markdown_text = data.get('markdown', '')
        
        # Preprocess to fix list formatting
        processed_markdown = preprocess_markdown(markdown_text)
        
        # Convert markdown to HTML with proper extensions
        html = markdown.markdown(
            processed_markdown,
            extensions=['codehilite', 'fenced_code', 'nl2br'],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight'
                }
            }
        )
        
        # Sanitize HTML for security
        clean_html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        
        return jsonify({
            'success': True,
            'html': clean_html
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/redact', methods=['POST'])
def redact_content():
    """Apply redaction to markdown content"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        redaction_type = data.get('redaction_type', 'abbreviation')
        redact_names = data.get('redact_names', [])
        redact_emails = data.get('redact_emails', [])
        
        # Apply redactions
        redacted_content = content
        
        # Create mappings for redactions
        name_mappings = {}
        first_name_mappings = {}  # For tracking first names
        last_name_mappings = {}   # For tracking last names
        email_mappings = {}
        
        # Process name redactions
        for name in redact_names:
            parts = name.split()
            
            # Skip if not a full name
            if len(parts) < 2:
                if redaction_type == 'abbreviation':
                    abbrev = name[0].upper() + name[-1].upper()
                    name_mappings[name] = abbrev
                else:
                    generic_names = ["Alex", "Taylor", "Jordan", "Casey", "Morgan", "Riley", "Quinn", "Avery", "Skyler", "Dakota"]
                    name_mappings[name] = random.choice(generic_names)
                continue
                
            first_name = parts[0]
            last_name = parts[-1]
            
            if redaction_type == 'abbreviation':
                # Create abbreviation (e.g., "John Smith" -> "JS")
                abbrev = first_name[0] + last_name[0]
                name_mappings[name] = abbrev.upper()
                
                # Map first name to the same abbreviation
                first_name_mappings[first_name] = abbrev.upper()
                
                # Map last name to just its initial
                last_name_mappings[last_name] = last_name[0].upper()
            else:  # generic
                # Use generic names
                generic_names = ["Alex", "Taylor", "Jordan", "Casey", "Morgan", "Riley", "Quinn", "Avery", "Skyler", "Dakota"]
                generic_surnames = ["Smith", "Jones", "Brown", "Johnson", "Williams", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
                
                generic_name = random.choice(generic_names)
                generic_surname = random.choice(generic_surnames)
                
                name_mappings[name] = f"{generic_name} {generic_surname}"
                first_name_mappings[first_name] = generic_name
                last_name_mappings[last_name] = generic_surname
        
        # Process email redactions
        for email in redact_emails:
            if redaction_type == 'abbreviation':
                # Create abbreviation (e.g., "john.smith@example.com" -> "js@example.com")
                username = email.split('@')[0]
                domain = email.split('@')[1]
                parts = re.split(r'[._-]', username)
                if len(parts) >= 2:
                    abbrev = parts[0][0] + parts[-1][0]
                    email_mappings[email] = f"{abbrev.lower()}@{domain}"
                else:
                    email_mappings[email] = f"{username[0].lower()}@{domain}"
            else:  # generic
                # Use generic email
                domain = email.split('@')[1]
                email_mappings[email] = f"user@{domain}"
        

        
        # Apply redactions in order of specificity (full names first, then parts)
        # Sort by length to avoid partial matches
        
        # 1. Apply full name redactions
        for name, replacement in sorted(name_mappings.items(), key=lambda x: len(x[0]), reverse=True):
            redacted_content = re.sub(r'\b' + re.escape(name) + r'\b', replacement, redacted_content)
        
        # 2. Apply last name redactions
        for last_name, replacement in sorted(last_name_mappings.items(), key=lambda x: len(x[0]), reverse=True):
            # Only replace last names that are standalone words
            redacted_content = re.sub(r'\b' + re.escape(last_name) + r'\b', replacement, redacted_content)
        
        # 3. Apply first name redactions
        for first_name, replacement in sorted(first_name_mappings.items(), key=lambda x: len(x[0]), reverse=True):
            # Only replace first names that are standalone words
            redacted_content = re.sub(r'\b' + re.escape(first_name) + r'\b', replacement, redacted_content)
        
        # 4. Apply email redactions
        for email, replacement in email_mappings.items():
            redacted_content = re.sub(re.escape(email), replacement, redacted_content)
        
        # Create redaction summary
        mappings = {
            'names': name_mappings,
            'first_names': first_name_mappings,
            'last_names': last_name_mappings,
            'emails': email_mappings,
            'redaction_type': redaction_type
        }
        
        return jsonify({
            'success': True,
            'redacted_content': redacted_content,
            'mappings': mappings
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/manual_redact', methods=['POST'])
def manual_redact():
    """Apply manual find/replace redaction"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        find_text = data.get('find_text', '')
        replace_text = data.get('replace_text', '')
        case_sensitive = data.get('case_sensitive', False)
        whole_word = data.get('whole_word', False)
        
        if not find_text:
            return jsonify({
                'success': False,
                'error': 'Find text cannot be empty'
            }), 400
        
        # Prepare the replacement
        redacted_content = content
        flags = 0 if case_sensitive else re.IGNORECASE
        
        # Escape the find text for regex
        escaped_find = re.escape(find_text)
        
        # Add word boundaries if whole word is selected
        if whole_word:
            pattern = r'\b' + escaped_find + r'\b'
        else:
            pattern = escaped_find
        
        # Count matches before replacement
        matches = re.findall(pattern, content, flags)
        match_count = len(matches)
        
        # Apply replacement
        redacted_content = re.sub(pattern, replace_text, content, flags=flags)
        
        return jsonify({
            'success': True,
            'redacted_content': redacted_content,
            'match_count': match_count,
            'mapping': {find_text: replace_text}
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/extract_pii', methods=['POST'])
def extract_pii():
    """Extract potential PII from content"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        names = extract_names(content)
        emails = extract_emails(content)
        
        return jsonify({
            'success': True,
            'names': names,
            'emails': emails
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback for improving PII detection"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        detected_names = data.get('detected_names', [])
        missed_names = data.get('missed_names', [])
        feedback_type = data.get('feedback_type', '')  # 'good' or 'bad' or 'correction' or 'manual_redaction'
        correction_mapping = data.get('correction_mapping', {})
        manual_redaction = data.get('manual_redaction', {})
        
        # Here you would typically save to a database
        # For now, we'll just log the feedback
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'content_hash': hash(content),  # Don't store actual content for privacy
            'detected_names': detected_names,
            'missed_names': missed_names,
            'feedback_type': feedback_type,
            'correction_mapping': correction_mapping,
            'manual_redaction': manual_redaction
        }
        
        # In a real implementation, save to database:
        # save_feedback_to_db(feedback_entry)
        print(f"Feedback received: {feedback_entry}")
        
        return jsonify({
            'success': True,
            'message': 'Thank you for your feedback! This helps improve our detection.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Model serving endpoints
@app.route('/api/model-info')
def model_info():
    """Provide model information and configuration"""
    model_path = MODELS_DIR / 'distilbert-ner-quantized.json'
    
    # Default configuration
    config = {
        'model_url': '/static/models/distilbert-ner-quantized.onnx',
        'model_version': app.config['MODEL_VERSION'],
        'model_hash': 'sha256:pending',
        'confidence_threshold': 0.75,
        'tokenizer_url': '/static/models/tokenizer_config.json',
        'wasm_config_url': '/static/models/wasm_config.json'
    }
    
    # Load actual model metadata if available
    if model_path.exists():
        try:
            with open(model_path, 'r') as f:
                metadata = json.load(f)
                config.update({
                    'model_hash': f"sha256:{metadata.get('hash', 'pending')}",
                    'model_size_mb': metadata.get('size_mb', 35),
                    'labels': metadata.get('labels', {})
                })
        except Exception as e:
            app.logger.warning(f"Could not load model metadata: {e}")
    
    return jsonify(config)

@app.route('/api/feedback', methods=['POST'])
def submit_api_feedback():
    """Collect anonymized feedback patterns for model improvement"""
    try:
        feedback = request.get_json()
        
        # Extract patterns without storing actual PII
        feedback_patterns = extract_patterns(feedback)
        
        # Store patterns (in production, use database)
        store_feedback_patterns(feedback_patterns)
        
        return jsonify({
            'status': 'success',
            'patterns_extracted': len(feedback_patterns)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 400

def extract_patterns(feedback):
    """Extract learning patterns from user feedback"""
    patterns = []
    
    for item in feedback.get('corrections', []):
        if item.get('corrected'):
            patterns.append({
                'pattern_type': 'correction',
                'original_label': item.get('original_label'),
                'corrected_label': item.get('corrected_label'),
                'context_features': item.get('context_features', {}),
                'confidence_delta': item.get('confidence_delta', 0)
            })
            
    return patterns

def store_feedback_patterns(patterns):
    """Store feedback patterns for future model updates"""
    # In production, store in database
    # For now, append to a JSON file
    feedback_file = PROJECT_ROOT / 'feedback_patterns.json'
    
    existing_patterns = []
    if feedback_file.exists():
        try:
            with open(feedback_file, 'r') as f:
                existing_patterns = json.load(f)
        except:
            pass
    
    existing_patterns.extend(patterns)
    
    with open(feedback_file, 'w') as f:
        json.dump(existing_patterns, f, indent=2)

# Static file serving with proper MIME types
@app.route('/static/models/<path:filename>')
def serve_model(filename):
    """Serve model files with appropriate headers"""
    response = send_from_directory(str(MODELS_DIR), filename)
    
    # Set appropriate headers for different file types
    if filename.endswith('.onnx'):
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
    elif filename.endswith('.json'):
        response.headers['Content-Type'] = 'application/json'
        response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
    elif filename.endswith('.wasm'):
        response.headers['Content-Type'] = 'application/wasm'
        response.headers['Cache-Control'] = 'public, max-age=31536000'
        
    # Enable CORS for model files
    response.headers['Access-Control-Allow-Origin'] = '*'
    
    return response

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'model_version': app.config['MODEL_VERSION'],
        'timestamp': datetime.utcnow().isoformat()
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Remove Vercel-specific code
if __name__ == '__main__':
    # Local development server
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    ) 