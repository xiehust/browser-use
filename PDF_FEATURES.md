# PDF Handling Features in browser-use

This document outlines the enhanced PDF handling capabilities that have been added to browser-use to address common issues when interacting with PDF documents in web browsers.

## Overview

The browser-use agent now includes two major enhancements for PDF handling:

1. **Automatic PDF Download** - When the agent navigates to a PDF page, it can automatically download the PDF file
2. **Enhanced PDF Scrolling** - Improved scrolling functionality that works specifically with PDF viewers

## Features

### 1. Automatic PDF Download

When the agent navigates to a URL that displays a PDF in the browser, it will automatically detect the PDF viewer and download the PDF file to the configured downloads directory.

#### How it works:
- Detects PDF viewers using multiple methods:
  - Chrome's built-in PDF viewer (`embed[type="application/pdf"]`)
  - PDF.js viewer (`#viewer` element)
  - Window-level PDF detection (`window.isPdfViewer`)
  - URL and title analysis (`.pdf` extensions)
- Automatically triggers download when a PDF is detected
- Uses Chrome DevTools Protocol (CDP) to capture the PDF as it's rendered
- Falls back to JavaScript-based download triggers if CDP fails
- Tracks downloaded files in the browser session

#### Configuration:
```python
from browser_use.browser import BrowserProfile, BrowserSession

browser_session = BrowserSession(
    browser_profile=BrowserProfile(
        downloads_path="/path/to/downloads"  # Required for auto-download
    )
)
```

### 2. Enhanced PDF Scrolling

The scroll action has been enhanced to handle PDF viewers specifically, addressing the common issue where standard scrolling doesn't work inside PDF documents.

#### How it works:
- Detects when the current page is a PDF viewer
- Uses PDF-specific scrolling methods:
  1. **Chrome PDF Viewer**: Focuses the embed element and sends Page Down/Up keyboard events
  2. **PDF.js Viewer**: Direct scrolling on the viewer container
  3. **Generic PDF Containers**: Searches for scrollable PDF-related elements
  4. **Fallback**: Standard window scrolling
- Falls back to normal scrolling for non-PDF pages

#### Improvements:
- More reliable scrolling in Chrome's built-in PDF viewer
- Better handling of PDF.js-based viewers
- Keyboard event simulation for more natural PDF navigation
- Maintains compatibility with regular web page scrolling

### 3. Manual PDF Download Action

A new action `download_pdf` has been added for explicit PDF downloading when needed.

#### Usage:
```python
# The agent can now use this action:
# "Use the download_pdf action to save the current PDF"
```

#### Features:
- Validates that the current page is a PDF viewer
- Provides clear error messages if downloads are not configured
- Multiple download methods with fallbacks
- Integrates with browser session file tracking

## Technical Implementation

### PDF Detection

The system uses multiple detection methods to ensure reliable PDF identification:

```javascript
// Chrome's built-in PDF viewer
document.body.querySelector('embed[type="application/pdf"]')

// PDF.js viewer
document.querySelector('#viewer')

// Window-level detection (set by browser-use init script)
window.isPdfViewer

// URL and title analysis
document.title.toLowerCase().includes('.pdf')
window.location.href.toLowerCase().includes('.pdf')
```

### Enhanced Scrolling

The scroll action now includes PDF-specific logic:

```javascript
// Method 1: Chrome PDF viewer with keyboard events
pdfEmbed.focus();
pdfEmbed.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'PageDown', // or 'PageUp'
    code: 'PageDown',
    bubbles: true
}));

// Method 2: PDF.js direct scrolling
pdfViewer.scrollBy({ top: dy, behavior: 'auto' });

// Method 3: Container-based scrolling
container.scrollBy({ top: dy, behavior: 'auto' });
```

### Auto-Download Process

1. **Detection**: After navigation, check if the page is a PDF viewer
2. **Filename Generation**: Extract filename from URL, sanitize for filesystem
3. **CDP Download**: Use Chrome DevTools Protocol to capture rendered PDF
4. **Fallback Methods**: JavaScript-based download triggers if CDP fails
5. **File Tracking**: Add downloaded file to session tracking

## Error Handling

- **No Downloads Path**: Clear error message when downloads_path is not configured
- **CDP Failures**: Automatic fallback to JavaScript-based download methods
- **Detection Failures**: Graceful degradation to standard scrolling behavior
- **File System Errors**: Proper error reporting for download failures

## Testing

A comprehensive test suite (`test_pdf_features.py`) is provided to verify:

1. Auto-download functionality
2. PDF scrolling behavior
3. Manual download action
4. Error handling scenarios

### Running Tests

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Run the test script
python test_pdf_features.py
```

## Benefits

1. **Improved User Experience**: PDFs are automatically downloaded for offline access
2. **Better Navigation**: Reliable scrolling within PDF documents
3. **Reduced Failures**: Agents no longer get stuck on PDF pages with no clickable elements
4. **Flexible Options**: Both automatic and manual download capabilities
5. **Robust Implementation**: Multiple fallback methods ensure reliability

## Backward Compatibility

All changes are backward compatible:
- Existing scroll functionality works as before on non-PDF pages
- No breaking changes to existing APIs
- PDF features only activate when PDFs are detected
- All new functionality is opt-in through configuration

## Future Enhancements

Potential future improvements could include:
- PDF text extraction for content analysis
- Page-specific scrolling within multi-page PDFs
- PDF form interaction capabilities
- Integration with PDF processing libraries
- Custom PDF viewer support