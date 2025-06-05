// Enhanced functionality for markdown display
class MarkdownEnhancer {
    constructor() {
        this.folders = new Map();
        this.currentFolder = 'default';
        this.redactionMap = new Map();
        this.originalText = '';
        this.initializeUI();
        this.initializeEventListeners();
    }

    initializeUI() {
        // Create folder system UI
        this.createFolderSystem();
        // Create redaction controls
        this.createRedactionControls();
        // Create copy button
        this.createCopyButton();
    }

    createFolderSystem() {
        const folderSystem = document.createElement('div');
        folderSystem.className = 'folder-system';
        folderSystem.innerHTML = `
            <div class="folder-controls">
                <button id="manage-folders-btn" class="btn">Manage Folders</button>
                <button id="save-display-btn" class="btn">Save Display</button>
            </div>
        `;
        document.querySelector('.input-section').insertBefore(folderSystem, document.querySelector('.editor-container'));
    }

    createRedactionControls() {
        const redactionControls = document.createElement('div');
        redactionControls.className = 'redaction-controls';
        redactionControls.innerHTML = `
            <div class="redaction-header">
                <h3>PII Redaction</h3>
                <label class="switch">
                    <input type="checkbox" id="redaction-toggle">
                    <span class="slider"></span>
                </label>
            </div>
            <div class="redaction-options">
                <label>
                    <input type="checkbox" id="redact-emails" checked> Emails
                </label>
                <label>
                    <input type="checkbox" id="redact-phones" checked> Phone Numbers
                </label>
                <label>
                    <input type="checkbox" id="redact-names" checked> Names
                </label>
            </div>
            <div class="redaction-actions">
                <button id="preview-redaction" class="btn">Preview Redaction</button>
                <button id="revert-redaction" class="btn" style="display: none;">Revert Changes</button>
            </div>
        `;
        document.querySelector('.output-section').insertBefore(redactionControls, document.querySelector('.output'));
    }

    createCopyButton() {
        const copyButton = document.createElement('button');
        copyButton.id = 'copy-all-btn';
        copyButton.className = 'btn copy-btn';
        copyButton.innerHTML = '📋 Copy All';
        document.querySelector('.output-header').appendChild(copyButton);
    }

    // PII Redaction Methods
    redactText(text) {
        if (!document.getElementById('redaction-toggle').checked) {
            return text;
        }

        // Store original text if not already stored
        if (!this.originalText) {
            this.originalText = text;
        }

        let redactedText = text;
        this.redactionMap.clear();

        // Email redaction
        if (document.getElementById('redact-emails').checked) {
            redactedText = this.redactEmails(redactedText);
        }

        // Phone number redaction
        if (document.getElementById('redact-phones').checked) {
            redactedText = this.redactPhoneNumbers(redactedText);
        }

        // Name redaction
        if (document.getElementById('redact-names').checked) {
            redactedText = this.redactNames(redactedText);
        }

        return redactedText;
    }

    redactEmails(text) {
        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
        return text.replace(emailRegex, (email) => {
            if (!this.redactionMap.has(email)) {
                this.redactionMap.set(email, `REDACTED_EMAIL_${this.redactionMap.size + 1}`);
            }
            return this.redactionMap.get(email);
        });
    }

    redactPhoneNumbers(text) {
        const phoneRegex = /(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g;
        return text.replace(phoneRegex, (phone) => {
            if (!this.redactionMap.has(phone)) {
                this.redactionMap.set(phone, `REDACTED_PHONE_${this.redactionMap.size + 1}`);
            }
            return this.redactionMap.get(phone);
        });
    }

    redactNames(text) {
        // Enhanced name detection
        const nameRegex = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g;
        return text.replace(nameRegex, (name) => {
            if (!this.redactionMap.has(name)) {
                this.redactionMap.set(name, `REDACTED_NAME_${this.redactionMap.size + 1}`);
            }
            return this.redactionMap.get(name);
        });
    }

    revertRedaction() {
        if (this.originalText) {
            document.getElementById('markdown-input').value = this.originalText;
            this.originalText = '';
            document.getElementById('convert-btn').click();
            document.getElementById('revert-redaction').style.display = 'none';
        }
    }

    showManageFolders() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Manage Folders</h2>
                    <button class="close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="folder-list">
                        ${this.generateFolderList()}
                    </div>
                    <div class="folder-actions">
                        <button id="new-folder-btn" class="btn">New Folder</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Event listeners for modal
        modal.querySelector('.close-btn').addEventListener('click', () => modal.remove());
        modal.querySelector('#new-folder-btn').addEventListener('click', () => this.createNewFolder());
    }

    generateFolderList() {
        let html = '';
        this.folders.forEach((items, folderName) => {
            html += `
                <div class="folder-item">
                    <h3>${folderName}</h3>
                    <div class="folder-files">
                        ${items.map((item, index) => `
                            <div class="file-item">
                                <span>${item.name || 'Unnamed Display'}</span>
                                <span>${new Date(item.timestamp).toLocaleString()}</span>
                                <div class="file-actions">
                                    <button onclick="markdownEnhancer.loadFromFolder('${folderName}', ${index})">Load</button>
                                    <button onclick="markdownEnhancer.deleteFromFolder('${folderName}', ${index})">Delete</button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        });
        return html;
    }

    saveDisplay() {
        const name = prompt('Enter a name for this display:');
        if (!name) return;

        const markdown = document.getElementById('markdown-input').value;
        const folder = this.folders.get(this.currentFolder) || [];
        folder.push({
            name: name,
            content: markdown,
            timestamp: new Date().toISOString()
        });
        this.folders.set(this.currentFolder, folder);
        
        // Show feedback
        const btn = document.getElementById('save-display-btn');
        const originalText = btn.textContent;
        btn.textContent = '✓ Saved!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    }

    // Folder System Methods
    createNewFolder() {
        const folderName = prompt('Enter folder name:');
        if (folderName && !this.folders.has(folderName)) {
            this.folders.set(folderName, []);
            this.updateFolderSelect();
            this.saveToCurrentFolder();
        }
    }

    updateFolderSelect() {
        const select = document.getElementById('folder-select');
        select.innerHTML = '';
        this.folders.forEach((_, folderName) => {
            const option = document.createElement('option');
            option.value = folderName;
            option.textContent = folderName;
            select.appendChild(option);
        });
    }

    saveToCurrentFolder() {
        const markdown = document.getElementById('markdown-input').value;
        const folder = this.folders.get(this.currentFolder) || [];
        folder.push({
            content: markdown,
            timestamp: new Date().toISOString()
        });
        this.folders.set(this.currentFolder, folder);
        this.updateFolderList();
    }

    updateFolderList() {
        const list = document.getElementById('folder-list');
        list.innerHTML = '';
        const folder = this.folders.get(this.currentFolder) || [];
        folder.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'folder-item';
            div.innerHTML = `
                <span>${new Date(item.timestamp).toLocaleString()}</span>
                <button onclick="markdownEnhancer.loadFromFolder(${index})">Load</button>
                <button onclick="markdownEnhancer.deleteFromFolder(${index})">Delete</button>
            `;
            list.appendChild(div);
        });
    }

    loadFromFolder(index) {
        const folder = this.folders.get(this.currentFolder);
        if (folder && folder[index]) {
            document.getElementById('markdown-input').value = folder[index].content;
            // Trigger conversion
            document.getElementById('convert-btn').click();
        }
    }

    deleteFromFolder(index) {
        const folder = this.folders.get(this.currentFolder);
        if (folder) {
            folder.splice(index, 1);
            this.updateFolderList();
        }
    }

    // Copy Functionality
    copyToClipboard() {
        const output = document.getElementById('output').innerHTML;
        navigator.clipboard.writeText(output).then(() => {
            const btn = document.getElementById('copy-all-btn');
            btn.innerHTML = '✓ Copied!';
            setTimeout(() => {
                btn.innerHTML = '📋 Copy All';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            alert('Failed to copy to clipboard');
        });
    }

    initializeEventListeners() {
        // Folder system events
        document.getElementById('manage-folders-btn').addEventListener('click', () => this.showManageFolders());
        document.getElementById('save-display-btn').addEventListener('click', () => this.saveDisplay());

        // Redaction events
        document.getElementById('preview-redaction').addEventListener('click', () => {
            const markdown = document.getElementById('markdown-input').value;
            const redacted = this.redactText(markdown);
            document.getElementById('markdown-input').value = redacted;
            document.getElementById('convert-btn').click();
            document.getElementById('revert-redaction').style.display = 'inline-block';
        });

        document.getElementById('revert-redaction').addEventListener('click', () => this.revertRedaction());

        // Copy button event
        document.getElementById('copy-all-btn').addEventListener('click', () => this.copyToClipboard());

        // Modify existing convert function to include redaction
        const originalConvertMarkdown = window.convertMarkdown;
        window.convertMarkdown = async function() {
            const markdown = document.getElementById('markdown-input').value;
            const redactedMarkdown = this.redactText(markdown);
            document.getElementById('markdown-input').value = redactedMarkdown;
            await originalConvertMarkdown();
        };
    }
}

// Initialize the enhancer when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.markdownEnhancer = new MarkdownEnhancer();
}); 