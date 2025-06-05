document.addEventListener('DOMContentLoaded', function() {
    const markdownInput = document.getElementById('markdown-input');
    const convertBtn = document.getElementById('convert-btn');
    const output = document.getElementById('output');
    const copyBtn = document.getElementById('copy-btn');
    const redactBtn = document.getElementById('redact-btn');
    const redactionSection = document.getElementById('redaction-section');
    const closeRedactionBtn = document.getElementById('close-redaction');
    const applyRedactionBtn = document.getElementById('apply-redaction');
    const revertRedactionBtn = document.getElementById('revert-redaction');
    const namesListEl = document.getElementById('names-list');
    const emailsListEl = document.getElementById('emails-list');

    // Store original content for reverting
    let originalContent = '';
    let currentMappings = null;

    // Auto-convert on input change (with debounce)
    let debounceTimer;
    markdownInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(convertMarkdown, 500);
    });

    // Convert button click
    convertBtn.addEventListener('click', convertMarkdown);

    // Copy button click
    copyBtn.addEventListener('click', copyContent);

    // Redaction button click
    redactBtn.addEventListener('click', function() {
        const content = markdownInput.value.trim();
        if (!content) {
            alert('Please enter some content first');
            return;
        }
        detectPII();
    });

    // Close redaction section
    closeRedactionBtn.addEventListener('click', function() {
        redactionSection.style.display = 'none';
    });

    // Apply redaction
    applyRedactionBtn.addEventListener('click', applyRedaction);

    // Revert redaction
    revertRedactionBtn.addEventListener('click', function() {
        if (originalContent) {
            markdownInput.value = originalContent;
            revertRedactionBtn.style.display = 'none';
            currentMappings = null;
            convertMarkdown();
        }
    });

    // Enter key to convert (Ctrl+Enter)
    markdownInput.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            convertMarkdown();
        }
    });

    // Show placeholder initially without converting
    showPlaceholder();

    async function detectPII() {
        const content = markdownInput.value;
        
        try {
            const response = await fetch('/extract_pii', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content: content })
            });

            const data = await response.json();

            if (data.success) {
                displayPII(data.names, data.emails);
                redactionSection.style.display = 'block';
                redactionSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error detecting PII: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to detect PII. Please try again.');
        }
    }

    function displayPII(names, emails) {
        // Display names
        if (names.length > 0) {
            namesListEl.innerHTML = names.map(name => 
                `<div class="pii-item">
                    <label>
                        <input type="checkbox" value="${name}" checked>
                        ${name}
                    </label>
                </div>`
            ).join('');
        } else {
            namesListEl.innerHTML = '<p class="no-items">No names detected</p>';
        }

        // Display emails
        if (emails.length > 0) {
            emailsListEl.innerHTML = emails.map(email => 
                `<div class="pii-item">
                    <label>
                        <input type="checkbox" value="${email}" checked>
                        ${email}
                    </label>
                </div>`
            ).join('');
        } else {
            emailsListEl.innerHTML = '<p class="no-items">No emails detected</p>';
        }
    }

    async function applyRedaction() {
        const content = markdownInput.value;
        const redactionType = document.querySelector('input[name="redaction_type"]:checked').value;
        
        // Get selected names and emails
        const selectedNames = Array.from(namesListEl.querySelectorAll('input[type="checkbox"]:checked'))
            .map(cb => cb.value);
        
        const selectedEmails = Array.from(emailsListEl.querySelectorAll('input[type="checkbox"]:checked'))
            .map(cb => cb.value);

        if (selectedNames.length === 0 && selectedEmails.length === 0) {
            alert('Please select at least one item to redact');
            return;
        }

        try {
            // Store original content if not already stored
            if (!originalContent) {
                originalContent = content;
            }

            const response = await fetch('/redact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: content,
                    redaction_type: redactionType,
                    redact_names: selectedNames,
                    redact_emails: selectedEmails
                })
            });

            const data = await response.json();

            if (data.success) {
                markdownInput.value = data.redacted_content;
                currentMappings = data.mappings;
                
                // Show revert button
                revertRedactionBtn.style.display = 'inline-flex';
                
                // Hide redaction section
                redactionSection.style.display = 'none';
                
                // Convert the redacted content
                convertMarkdown();
                
                // Show success message
                showRedactionSummary(data.mappings);
            } else {
                alert('Error applying redaction: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to apply redaction. Please try again.');
        }
    }

    function showRedactionSummary(mappings) {
        let summary = 'Redaction applied successfully!\n\n';
        
        if (Object.keys(mappings.names).length > 0) {
            summary += 'Names redacted:\n';
            for (const [original, redacted] of Object.entries(mappings.names)) {
                summary += `• ${original} → ${redacted}\n`;
            }
            summary += '\n';
        }
        
        if (Object.keys(mappings.emails).length > 0) {
            summary += 'Emails redacted:\n';
            for (const [original, redacted] of Object.entries(mappings.emails)) {
                summary += `• ${original} → ${redacted}\n`;
            }
        }
        
        alert(summary);
    }

    async function convertMarkdown() {
        const markdown = markdownInput.value.trim();

        if (!markdown) {
            showPlaceholder();
            return;
        }

        // Show loading state
        setLoadingState(true);

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    markdown: markdown
                })
            });

            const data = await response.json();

            if (data.success) {
                displayOutput(data.html);
            } else {
                showError(data.error || 'An error occurred while converting markdown');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Failed to connect to the server. Please try again.');
        } finally {
            setLoadingState(false);
        }
    }

    async function copyContent() {
        try {
            const outputContent = output.innerHTML;
            
            // Check if there's content to copy (not placeholder or error)
            if (output.querySelector('.placeholder')) {
                return; // Don't copy placeholder content
            }

            // Create a temporary div to get the text content
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = outputContent;
            const textContent = tempDiv.innerText || tempDiv.textContent;

            // Enhanced HTML content with better styling for external applications
            const styledHTML = `
                <div style="font-family: Verdana, Geneva, sans-serif; font-size: 11pt; line-height: 1.3; color: #000000; font-weight: normal;">
                    ${outputContent}
                </div>
                <style>
                    * { font-weight: normal; }
                    h1, h2, h3, h4, h5, h6 { 
                        color: #1A2B6B; 
                        margin-bottom: 10px; 
                        margin-top: 16px; 
                        font-weight: bold;
                        line-height: 1.3;
                    }
                    h1 { 
                        font-size: 16pt; 
                        border-bottom: 2px solid #00ACFF; 
                        padding-bottom: 6px; 
                        font-weight: bold;
                    }
                    h2 { 
                        font-size: 14pt; 
                        border-bottom: 1px solid #e5e7eb; 
                        padding-bottom: 4px; 
                        font-weight: bold;
                    }
                    h3 { 
                        font-size: 12pt; 
                        font-weight: bold;
                    }
                    h4, h5, h6 { 
                        font-size: 11pt;
                        font-weight: bold;
                    }
                    p { 
                        margin-bottom: 10px; 
                        font-weight: normal;
                        font-size: 11pt;
                        line-height: 1.3;
                    }
                    ul, ol { 
                        margin: 8px 0; 
                        padding-left: 22px; 
                        font-weight: normal;
                    }
                    ul li, ol li { 
                        margin-bottom: 4px; 
                        line-height: 1.3; 
                        font-weight: normal;
                        font-size: 11pt;
                    }
                    ul li { 
                        list-style-type: disc; 
                    }
                    ol li { 
                        list-style-type: decimal; 
                    }
                    strong, b { 
                        color: #1A2B6B; 
                        font-weight: bold !important;
                    }
                    em, i { 
                        color: #6c757d; 
                        font-style: italic; 
                        font-weight: normal;
                    }
                    blockquote { 
                        background: rgba(0, 172, 255, 0.05); 
                        border-left: 3px solid #00ACFF; 
                        padding: 10px 15px; 
                        margin: 10px 0; 
                        border-radius: 0 4px 4px 0;
                        font-weight: normal;
                        font-size: 11pt;
                        line-height: 1.3;
                    }
                    code { 
                        background: #f1f5f9; 
                        padding: 2px 4px; 
                        border-radius: 3px; 
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace; 
                        font-size: 10pt; 
                        color: #1A2B6B;
                        font-weight: normal;
                    }
                    pre { 
                        background: #1e293b; 
                        color: #e2e8f0; 
                        padding: 12px; 
                        border-radius: 4px; 
                        overflow-x: auto; 
                        margin: 10px 0;
                        font-weight: normal;
                        font-size: 10pt;
                        line-height: 1.3;
                    }
                    pre code { 
                        background: none; 
                        padding: 0; 
                        color: inherit;
                        font-weight: normal;
                        font-size: 10pt;
                    }
                    div, span, text { 
                        font-weight: normal; 
                    }
                </style>
            `;

            // Try modern clipboard API with multiple formats
            if (navigator.clipboard && window.ClipboardItem) {
                try {
                    await navigator.clipboard.write([
                        new ClipboardItem({
                            'text/html': new Blob([styledHTML], { type: 'text/html' }),
                            'text/plain': new Blob([textContent], { type: 'text/plain' })
                        })
                    ]);
                    showCopySuccess();
                    return;
                } catch (error) {
                    console.log('ClipboardItem method failed:', error);
                    // Fall through to alternative methods
                }
            }

            // Fallback method: Use execCommand with a temporary element
            try {
                const tempContainer = document.createElement('div');
                tempContainer.style.position = 'fixed';
                tempContainer.style.left = '-9999px';
                tempContainer.style.top = '-9999px';
                tempContainer.innerHTML = styledHTML;
                document.body.appendChild(tempContainer);

                // Select the content
                const range = document.createRange();
                range.selectNodeContents(tempContainer);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);

                // Copy using execCommand
                const successful = document.execCommand('copy');
                
                // Clean up
                document.body.removeChild(tempContainer);
                selection.removeAllRanges();

                if (successful) {
                    showCopySuccess();
                    return;
                }
            } catch (error) {
                console.log('execCommand method failed:', error);
            }

            // Final fallback: Plain text only
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(textContent);
                showCopySuccess();
            } else {
                // Oldest fallback method
                const textArea = document.createElement('textarea');
                textArea.value = textContent;
                textArea.style.position = 'fixed';
                textArea.style.left = '-9999px';
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                showCopySuccess();
            }

        } catch (error) {
            console.error('Failed to copy:', error);
            showCopyError();
        }
    }

    function showCopySuccess() {
        const copyText = copyBtn.querySelector('.copy-text');
        const copySuccess = copyBtn.querySelector('.copy-success');
        
        copyText.style.display = 'none';
        copySuccess.style.display = 'inline';
        
        setTimeout(() => {
            copyText.style.display = 'inline';
            copySuccess.style.display = 'none';
        }, 2000);
    }

    function showCopyError() {
        const copyText = copyBtn.querySelector('.copy-text');
        copyText.textContent = 'Error';
        
        setTimeout(() => {
            copyText.textContent = 'Copy';
        }, 2000);
    }

    function displayOutput(html) {
        output.innerHTML = html;
        output.className = 'output';
        
        // Add smooth fade-in animation
        output.style.opacity = '0';
        setTimeout(() => {
            output.style.transition = 'opacity 0.3s ease';
            output.style.opacity = '1';
        }, 50);
    }

    function showPlaceholder() {
        output.innerHTML = `
            <div class="placeholder">
                <div class="placeholder-icon">📝</div>
                <p>Your converted markdown will appear here</p>
                <p class="placeholder-hint">Start typing markdown in the text area to see the preview</p>
            </div>
        `;
        output.className = 'output';
    }

    function showError(message) {
        output.innerHTML = `
            <div class="placeholder">
                <div class="placeholder-icon">❌</div>
                <p style="color: #ef4444;">Error: ${message}</p>
                <p class="placeholder-hint">Please check your markdown and try again</p>
            </div>
        `;
        output.className = 'output';
    }

    function setLoadingState(loading) {
        if (loading) {
            convertBtn.classList.add('loading');
            convertBtn.disabled = true;
        } else {
            convertBtn.classList.remove('loading');
            convertBtn.disabled = false;
        }
    }

    // Make convertMarkdown function globally available
    window.convertMarkdown = convertMarkdown;
}); 