from flask import Flask, render_template, request, jsonify, send_file
import markdown
import bleach
import re
import os
import random
import tempfile
import io
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for redaction functionality

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
    """Extract potential names from text using regex patterns"""
    # Find full names (First Last)
    full_name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    full_names = set(re.findall(full_name_pattern, text))
    
    # We'll just return full names for selection in the UI
    # The redaction will handle first/last names automatically
    return list(full_names)

def extract_emails(text):
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = set(re.findall(email_pattern, text))
    return list(emails)

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

# For Vercel deployment
if __name__ == '__main__':
    import os
    # Use debug=False in production, but allow override via environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=8080) 