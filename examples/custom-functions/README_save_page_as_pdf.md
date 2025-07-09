# Save Page as PDF Example

This example demonstrates how to create a custom function that saves the current web page as a PDF file using the `NoParams` pattern.

## Features

- **NoParams Pattern**: The function accepts no parameters from the LLM
- **Browser Downloads Directory**: Saves PDF to the configured browser downloads directory
- **Automatic File Tracking**: Adds the saved PDF to the model's `available_file_paths`
- **Unique Filenames**: Uses URL and timestamp to create unique PDF filenames
- **Error Handling**: Gracefully handles cases where downloads directory is not configured

## How It Works

1. **Custom Function Registration**: The `save_page_as_pdf` function is registered using the `@controller.action()` decorator with `param_model=NoParamsAction`

2. **No Parameters Required**: Since it uses `NoParamsAction`, the LLM can call this function without providing any parameters

3. **PDF Generation**: Uses Playwright's `page.pdf()` method to generate a PDF of the current page

4. **File Management**: 
   - Saves to the browser's configured downloads directory
   - Creates unique filenames using URL slugification and timestamps
   - Adds the PDF path to browser session's downloaded files tracking

5. **Model Integration**: The saved PDF is automatically made available to the model via `available_file_paths` through the `attachments` field in `ActionResult`

## Usage

```python
from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile
from browser_use.controller.views import NoParamsAction

controller = Controller()

@controller.action('Save the current page as a PDF file to downloads directory', param_model=NoParamsAction)
async def save_page_as_pdf(params: NoParamsAction, page: Page, browser_session: BrowserSession, available_file_paths: List[str]):
    # Implementation here...
    pass

# Configure browser with downloads directory
browser_profile = BrowserProfile(
    downloads_path="./downloads",
    headless=False
)

agent = Agent(
    task="Go to https://example.com and save the page as PDF",
    llm=model,
    controller=controller,
    browser_profile=browser_profile
)
```

## Example Task

The example includes a task that:
1. Navigates to The Pioneer Woman's chocolate almond sheet cake recipe
2. Uses the custom `save_page_as_pdf` function to save the recipe as a PDF
3. The PDF becomes available in the model's `available_file_paths` for further processing

## Key Points

- **NoParamsAction**: This is a special Pydantic model that accepts any input and ignores it, allowing functions that don't need parameters
- **Downloads Directory**: Must be configured in the `BrowserProfile` for the function to work
- **File Tracking**: The browser-use system automatically tracks downloaded files and makes them available to the model
- **Unique Names**: Timestamp-based naming prevents filename conflicts

## Running the Example

```bash
cd examples/custom-functions
python save_page_as_pdf.py
```

The script will:
1. Create a downloads directory in the current working directory
2. Navigate to the specified recipe page
3. Save the page as a PDF using the custom function
4. Print the task completion result