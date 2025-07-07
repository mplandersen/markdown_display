/**
 * Enhanced Markdown Display with ML-Powered PII Detection
 * Integrates client-side ML detection with existing functionality
 * 
 * FILE LOCATION: static/js/script.js (UPDATE EXISTING FILE)
 */

// Global variables
let mlDetector = null;
let originalContent = '';
let currentMappings = null;
let detectionMethod = 'hybrid'; // 'ml-only', 'server-only', 'hybrid'

// Expose detection method globally for debugging
window.detectionMethod = detectionMethod;

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 DOM Content Loaded - Initializing app...');
    
    // Get DOM elements
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

    // Debug: Check if all elements are found
    console.log('📋 DOM Elements status:', {
        markdownInput: !!markdownInput,
        convertBtn: !!convertBtn,
        redactBtn: !!redactBtn,
        output: !!output,
        copyBtn: !!copyBtn,
        redactionSection: !!redactionSection,
        applyRedactionBtn: !!applyRedactionBtn,
        namesListEl: !!namesListEl,
        emailsListEl: !!emailsListEl
    });

    if (!markdownInput || !convertBtn || !redactBtn) {
        console.error('❌ Critical DOM elements not found!');
        return;
    }

    // Add detection method event listeners for debugging
    const detectionMethodInputs = document.querySelectorAll('input[name="detection_method"]');
    console.log('Found detection method inputs:', detectionMethodInputs.length);
    
    // Initialize detection method from currently selected radio
    const currentlySelected = document.querySelector('input[name="detection_method"]:checked');
    if (currentlySelected) {
        detectionMethod = currentlySelected.value;
        console.log('Initial detection method set to:', detectionMethod);
    }
    
    detectionMethodInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            detectionMethod = e.target.value;
            console.log('Detection method changed to:', detectionMethod);
            
            // Also update window.detectionMethod for global access
            window.detectionMethod = detectionMethod;
        });
        console.log('Added listener to detection method radio:', input.value);
    });

    // Initialize ML detector
    await initializeMLDetector();

    // Auto-convert on input change (with debounce)
    let debounceTimer;
    markdownInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(convertMarkdown, 500);
    });

    // Convert button click
    convertBtn.addEventListener('click', function() {
        console.log('✨ Convert & Display button clicked!');
        convertMarkdown();
    });

    // Copy button click
    copyBtn.addEventListener('click', copyContent);

    // Redaction button click - now uses ML detection
    redactBtn.addEventListener('click', async function() {
        console.log('🔍 Detect & Redact PII button clicked!');
        const content = markdownInput.value.trim();
        console.log('Content to analyze:', content);
        if (!content) {
            alert('Please enter some content first');
            return;
        }
        await detectPIIWithML();
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

    // Show placeholder initially
    showPlaceholder();

    /**
     * Initialize ML detector with loading UI
     */
    async function initializeMLDetector() {
        try {
            // Show ML loading status
            showMLLoadingStatus('Initializing ML detector...');

            // Load ONNX Runtime Web
            if (typeof ort === 'undefined') {
                await loadONNXRuntime();
            }

            // Create ML detector instance if not already created
            if (!mlDetector) {
                mlDetector = new ClientSideMLDetector();
            }

            // Try to load the model
            const success = await mlDetector.loadModel();

            if (success) {
                showMLLoadingStatus('ML detector ready!', 'success');
                setTimeout(hideMLLoadingStatus, 3000);
            } else {
                showMLLoadingStatus('ML detector unavailable - using server detection', 'warning');
                setTimeout(hideMLLoadingStatus, 5000);
            }

        } catch (error) {
            console.error('Failed to initialize ML detector:', error);
            showMLLoadingStatus('ML initialization failed - using server detection', 'error');
            setTimeout(hideMLLoadingStatus, 5000);
        }
    }

    /**
     * Load ONNX Runtime Web dynamically
     */
    async function loadONNXRuntime() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.16.3/dist/ort.min.js';
            script.onload = resolve;
            script.onerror = () => reject(new Error('Failed to load ONNX Runtime'));
            document.head.appendChild(script);
        });
    }

    /**
     * Detect PII using ML + server hybrid approach
     */
    async function detectPIIWithML() {
        const content = markdownInput.value;
        
        console.log('🔍 Starting PII detection with content:', content);
        console.log('🤖 ML Detector status:', {
            exists: typeof ClientSideMLDetector !== 'undefined',
            instance: mlDetector,
            loaded: mlDetector?.modelLoaded,
            tokenizer: mlDetector?.tokenizer,
            session: mlDetector?.session
        });
        console.log('⚙️ Detection method:', detectionMethod);
        console.log('🌐 Available global objects:', {
            BertTokenizer: typeof BertTokenizer !== 'undefined',
            ort: typeof ort !== 'undefined',
            ClientSideMLDetector: typeof ClientSideMLDetector !== 'undefined'
        });
        
        try {
            showDetectionProgress('Detecting PII...');

            let detectionResults;
            
            if (mlDetector && mlDetector.modelLoaded && detectionMethod !== 'server-only') {
                console.log('Using ML detection...');
                // Try ML detection first
                try {
                    detectionResults = await mlDetector.detectPII(content, {
                        minConfidence: 0.7,
                        includePatterns: true,
                        maxLength: 512
                    });
                    console.log('ML detection completed:', detectionResults);
                    
                    // In hybrid mode, fall back to server if ML returns no entities
                    if (detectionMethod === 'hybrid' && (!detectionResults.entities || detectionResults.entities.length === 0)) {
                        console.log('ML returned no entities, falling back to server detection...');
                        detectionResults = await detectPIIServer(content);
                    }
                } catch (mlError) {
                    console.error('ML detection failed:', mlError);
                    if (detectionMethod === 'hybrid') {
                        console.log('ML error, falling back to server detection...');
                        // Fallback to server
                        detectionResults = await detectPIIServer(content);
                    } else {
                        throw mlError;
                    }
                }
            } else {
                console.log('Using server detection...');
                console.log('Reasons for server detection:', {
                    noMlDetector: !mlDetector,
                    modelNotLoaded: mlDetector && !mlDetector.modelLoaded,
                    serverOnlyMode: detectionMethod === 'server-only'
                });
                // Use server detection
                detectionResults = await detectPIIServer(content);
            }

            // Ensure results have the expected structure
            if (!detectionResults.hasOwnProperty('success')) {
                detectionResults.success = true;
            }
            
            console.log('✅ Detection complete. Results:', {
                success: detectionResults.success,
                entityCount: detectionResults.entities?.length || 0,
                entities: detectionResults.entities,
                method: detectionResults.detection_method || 'server',
                processing_time: detectionResults.processing_time || detectionResults.detection_time_ms
            });

            hideDetectionProgress();

            // Process and display results
            displayPIIResults(detectionResults);
            
            // Show redaction UI
            redactionSection.style.display = 'block';
            redactionSection.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            hideDetectionProgress();
            console.error('PII detection error:', error);
            alert('Error detecting PII: ' + (error.message || 'Unknown error'));
        }
    }

    /**
     * Server-side PII detection
     */
    async function detectPIIServer(content) {
        const response = await fetch('/api/detect-pii', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                text: content,
                min_confidence: 0.5
            })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Server detection failed');
        }

        return data;
    }

    /**
     * Display PII detection results
     */
    window.displayPIIResults = function(results) {
        const entities = results.entities || [];
        
        console.log('📋 Displaying PII results:', {
            totalEntities: entities.length,
            entities: entities,
            entitiesByType: entities.map(e => ({ type: e.type, text: e.text, confidence: e.confidence }))
        });
        
        // Group entities by type
        const groupedEntities = {
            names: [],
            emails: [],
            phones: [],
            addresses: [],
            ssns: [],
            cards: [],
            other: []
        };

        entities.forEach(entity => {
            console.log('🔍 Processing entity:', entity);
            switch (entity.type) {
                case 'PERSON':
                case 'ORGANIZATION':
                    console.log('➕ Adding to names:', entity.text);
                    groupedEntities.names.push(entity);
                    break;
                case 'EMAIL':
                    console.log('➕ Adding to emails:', entity.text);
                    groupedEntities.emails.push(entity);
                    break;
                case 'PHONE_UK':
                case 'PHONE':
                    console.log('➕ Adding to phones:', entity.text);
                    groupedEntities.phones.push(entity);
                    break;
                case 'ADDRESS':
                case 'LOCATION':
                    console.log('➕ Adding to addresses:', entity.text);
                    groupedEntities.addresses.push(entity);
                    break;
                case 'SSN_US':
                case 'SSN':
                    console.log('➕ Adding to ssns:', entity.text);
                    groupedEntities.ssns.push(entity);
                    break;
                case 'CREDIT_CARD':
                    console.log('➕ Adding to cards:', entity.text);
                    groupedEntities.cards.push(entity);
                    break;
                default:
                    console.log('➕ Adding to other:', entity.text, 'type:', entity.type);
                    groupedEntities.other.push(entity);
            }
        });

        console.log('📊 Grouped entities:', groupedEntities);

        // Display names with confidence indicators
        displayEntityList(namesListEl, groupedEntities.names, 'name');
        
        // Display emails with confidence indicators
        displayEntityList(emailsListEl, groupedEntities.emails, 'email');
        
        // Display phones
        const phonesListEl = document.getElementById('phones-list');
        if (phonesListEl) {
            displayEntityList(phonesListEl, groupedEntities.phones, 'phone');
        }
        
        // Display sensitive data (SSNs, cards, etc.)
        const sensitiveListEl = document.getElementById('sensitive-list');
        if (sensitiveListEl) {
            const allSensitive = [...groupedEntities.ssns, ...groupedEntities.cards, ...groupedEntities.other];
            displayEntityList(sensitiveListEl, allSensitive, 'sensitive');
        }

        // Show detection method and stats
        showDetectionStats(results);
    }

    /**
     * Display entity list with confidence visualization
     */
    function displayEntityList(containerEl, entities, type) {
        if (entities.length > 0) {
            const uniqueTexts = new Set();
            const uniqueEntities = entities.filter(e => {
                if (uniqueTexts.has(e.text)) return false;
                uniqueTexts.add(e.text);
                return true;
            });

            containerEl.innerHTML = uniqueEntities.map(entity => 
                `<div class="pii-item" data-confidence="${entity.confidence}">
                    <label>
                        <input type="checkbox" value="${escapeHtml(entity.text)}" checked>
                        <span class="pii-text">${escapeHtml(entity.text)}</span>
                        <span class="confidence-indicator ${getConfidenceClass(entity.confidence)}" 
                              title="Confidence: ${(entity.confidence * 100).toFixed(0)}%">
                            ${getConfidenceIcon(entity.confidence)}
                        </span>
                    </label>
                    ${entity.source === 'ml_model' ? '<span class="ml-badge">ML</span>' : ''}
                </div>`
            ).join('');
        } else {
            containerEl.innerHTML = `<p class="no-items">No ${type}s detected</p>`;
        }
    }

    /**
     * Get confidence class for styling
     */
    function getConfidenceClass(confidence) {
        if (confidence >= 0.9) return 'confidence-high';
        if (confidence >= 0.7) return 'confidence-medium';
        return 'confidence-low';
    }

    /**
     * Get confidence icon
     */
    function getConfidenceIcon(confidence) {
        if (confidence >= 0.9) return '✓✓';
        if (confidence >= 0.7) return '✓';
        return '?';
    }

    /**
     * Show detection statistics
     */
    function showDetectionStats(results) {
        const statsEl = document.getElementById('detection-stats');
        if (!statsEl) {
            // Create stats element if it doesn't exist
            const statsDiv = document.createElement('div');
            statsDiv.id = 'detection-stats';
            statsDiv.className = 'detection-stats';
            redactionSection.insertBefore(statsDiv, redactionSection.firstChild);
        }

        const stats = results.stats || {};
        const processingTime = results.processing_time || results.detection_time_ms || 0;
        const method = results.detection_method || 'server';

        document.getElementById('detection-stats').innerHTML = `
            <div class="stats-row">
                <span class="stat-label">Detection Method:</span>
                <span class="stat-value">${method === 'client-ml' ? 'Local ML' : 'Server'}</span>
            </div>
            <div class="stats-row">
                <span class="stat-label">Processing Time:</span>
                <span class="stat-value">${processingTime.toFixed(0)}ms</span>
            </div>
            <div class="stats-row">
                <span class="stat-label">Total Entities:</span>
                <span class="stat-value">${stats.total_entities || 0}</span>
            </div>
        `;
    }

    /**
     * Apply redaction with ML-detected entities
     */
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
                
                // Submit feedback if ML was used
                if (mlDetector && mlDetector.modelLoaded) {
                    submitDetectionFeedback('success', selectedNames, selectedEmails);
                }
            } else {
                alert('Error applying redaction: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to apply redaction. Please try again.');
        }
    }

    /**
     * Submit feedback for ML improvement
     */
    async function submitDetectionFeedback(type, confirmedNames, confirmedEmails) {
        if (!mlDetector || !mlDetector.modelLoaded) return;

        try {
            // Prepare feedback data
            const feedbackData = {
                feedback_type: type,
                confirmed_entities: [
                    ...confirmedNames.map(name => ({ text: name, type: 'PERSON', confirmed: true })),
                    ...confirmedEmails.map(email => ({ text: email, type: 'EMAIL', confirmed: true }))
                ],
                timestamp: new Date().toISOString()
            };

            // Send to server
            await fetch('/api/submit-feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feedbackData)
            });

        } catch (error) {
            console.error('Failed to submit feedback:', error);
        }
    }

    /**
     * Convert markdown to HTML
     */
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

    /**
     * Copy content to clipboard
     */
    async function copyContent() {
        try {
            const outputContent = output.innerHTML;
            
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

    /**
     * UI Helper Functions
     */
    function showMLLoadingStatus(message, type = 'info') {
        let statusEl = document.getElementById('ml-status');
        if (!statusEl) {
            statusEl = document.createElement('div');
            statusEl.id = 'ml-status';
            statusEl.className = 'ml-status';
            document.querySelector('.container').insertBefore(statusEl, document.querySelector('.main-content'));
        }

        statusEl.className = `ml-status ml-status-${type}`;
        statusEl.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : type === 'error' ? 'times-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        statusEl.style.display = 'block';
    }

    function hideMLLoadingStatus() {
        const statusEl = document.getElementById('ml-status');
        if (statusEl) {
            statusEl.style.display = 'none';
        }
    }

    function showMLDownloadUI() {
        let downloadUI = document.getElementById('ml-download-ui');
        if (!downloadUI) {
            downloadUI = document.createElement('div');
            downloadUI.id = 'ml-download-ui';
            downloadUI.className = 'ml-download-ui';
            downloadUI.innerHTML = `
                <div class="download-content">
                    <h3>Downloading ML Model</h3>
                    <p>First-time setup: downloading PII detection model (104MB)</p>
                    <div class="progress-bar">
                        <div class="progress-fill" id="ml-progress-fill"></div>
                    </div>
                    <div class="progress-text" id="ml-progress-text">0%</div>
                    <p class="download-note">This is a one-time download. The model will be cached for offline use.</p>
                </div>
            `;
            document.body.appendChild(downloadUI);
        }
        downloadUI.style.display = 'flex';
    }

    function hideMLDownloadUI() {
        const downloadUI = document.getElementById('ml-download-ui');
        if (downloadUI) {
            downloadUI.style.display = 'none';
        }
    }

    function updateMLProgress(progress) {
        const fillEl = document.getElementById('ml-progress-fill');
        const textEl = document.getElementById('ml-progress-text');
        if (fillEl && textEl) {
            const percentage = Math.round(progress.percentage);
            fillEl.style.width = percentage + '%';
            textEl.textContent = `${percentage}% (${formatBytes(progress.loaded)} / ${formatBytes(progress.total)})`;
        }
    }

    function updateChunkProgress(current, total) {
        showDetectionProgress(`Processing document... (${current}/${total} chunks)`);
    }

    function showDetectionProgress(message) {
        let progressEl = document.getElementById('detection-progress');
        if (!progressEl) {
            progressEl = document.createElement('div');
            progressEl.id = 'detection-progress';
            progressEl.className = 'detection-progress';
            redactionSection.insertBefore(progressEl, redactionSection.firstChild);
        }
        progressEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
        progressEl.style.display = 'block';
    }

    function hideDetectionProgress() {
        const progressEl = document.getElementById('detection-progress');
        if (progressEl) {
            progressEl.style.display = 'none';
        }
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
                <div class="placeholder-icon">
                    <i class="fas fa-file-text"></i>
                </div>
                <p>Your converted markdown will appear here</p>
                <p class="placeholder-hint">Start typing markdown in the editor to see the preview</p>
            </div>
        `;
        output.className = 'output';
    }

    function showError(message) {
        output.innerHTML = `
            <div class="placeholder">
                <div class="placeholder-icon">
                    <i class="fas fa-exclamation-triangle" style="color: #ef4444;"></i>
                </div>
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

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    // Make convertMarkdown function globally available
    window.convertMarkdown = convertMarkdown;
}); 