# Markdown Display

A beautiful Flask web application that converts markdown text into HTML and displays it with various beautiful fonts. Perfect for previewing how your markdown content will look with different typography.

## Features

- ✨ **Real-time markdown conversion** - See your markdown transform instantly
- 🎨 **10 beautiful font options** - From elegant serif to modern sans-serif and creative fonts
- 📱 **Responsive design** - Works perfectly on desktop, tablet, and mobile
- 🔒 **Secure HTML sanitization** - Safe rendering of user input
- ⚡ **Fast and lightweight** - Built with Flask for quick performance
- 🎯 **Live preview** - Auto-converts as you type (with debouncing)
- ⌨️ **Keyboard shortcuts** - Ctrl+Enter to convert manually
- 🔍 **PII Detection** - Built-in personal information detection and extraction

## Font Options

1. **Default** - Clean system fonts
2. **Serif** - Classic Georgia and Times New Roman
3. **Monospace** - Perfect for code and technical content
4. **Elegant** - Sophisticated Playfair Display
5. **Modern** - Contemporary Inter font
6. **Creative** - Friendly Comfortaa
7. **Handwriting** - Stylish Dancing Script
8. **Tech** - Developer-friendly Fira Code
9. **Classic** - Readable Merriweather
10. **Minimal** - Clean Lato

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/mplandersen/markdown_display.git
   cd markdown_display
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python3 app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:8080`

## Usage

1. **Enter your markdown** in the left panel
2. **Choose a font** from the dropdown menu
3. **Watch the magic happen** - the converted HTML appears instantly in the right panel
4. **Try different fonts** to see how they affect your content's appearance
5. **Use PII Detection** - Click "Extract PII" to identify personal information in your text

### Keyboard Shortcuts

- `Ctrl + Enter` - Manually trigger conversion
- Auto-conversion happens 500ms after you stop typing

## Supported Markdown Features

- Headers (H1-H6)
- **Bold** and *italic* text
- `Inline code` and code blocks with syntax highlighting
- [Links](https://example.com)
- Unordered and ordered lists
- > Blockquotes
- Horizontal rules
- Images (with alt text)
- Tables
- Strikethrough text

## Technical Details

### Backend
- **Flask** - Lightweight Python web framework
- **python-markdown** - Markdown to HTML conversion
- **bleach** - HTML sanitization for security
- **Pygments** - Syntax highlighting for code blocks
- **re (regex)** - PII detection patterns

### Frontend
- **Modern CSS Grid** - Responsive layout
- **Google Fonts** - Beautiful typography
- **Vanilla JavaScript** - No heavy frameworks
- **CSS animations** - Smooth transitions and loading states

### Security Features
- HTML sanitization prevents XSS attacks
- Only safe HTML tags and attributes are allowed
- Input validation on both client and server side

## API Endpoints

- `GET /` - Main application interface
- `POST /convert` - Convert markdown to HTML
- `POST /extract_pii` - Extract personally identifiable information from text

## Project Structure

```
markdown_display/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Styles and animations
    └── js/
        ├── script.js     # Main frontend JavaScript
        └── enhanced.js   # Enhanced features and utilities
```

## Development

The application runs on port 8080 and binds to all addresses (0.0.0.0) for easy access across your network.

To modify the port or host, edit the bottom of `app.py`:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
```

## Contributing

Feel free to fork this project and submit pull requests for any improvements!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

---

**Enjoy creating beautiful markdown displays! 📝✨** 