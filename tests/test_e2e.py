"""
E2E тесты для MoFrame Streamlit UI.

Использует Playwright для автоматизации браузера.
Проверяет базовую загрузку страницы.
"""

import pytest
import time
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, expect


def check_streamlit_running():
    """Check if Streamlit is running."""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8501", method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        urllib.request.urlopen(req, timeout=2)
        return True
    except:
        return False


def start_streamlit():
    """Start Streamlit in background."""
    import subprocess
    
    env = os.environ.copy()
    env['STREAMLIT_SERVER_HEADLESS'] = 'true'
    env['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    
    process = subprocess.Popen(
        ["python3", "-m", "streamlit", "run", "ui/app.py",
         "--server.port=8501",
         "--server.address=localhost"],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )
    
    # Wait for startup
    for i in range(30):
        time.sleep(1)
        if check_streamlit_running():
            return process
    
    process.terminate()
    return None


@pytest.fixture(scope="session")
def browser():
    """Launch browser once for all tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create new page for each test."""
    # Start Streamlit if not running
    streamlit_process = None
    if not check_streamlit_running():
        streamlit_process = start_streamlit()
        if streamlit_process is None:
            pytest.skip("Streamlit не запустился")
        time.sleep(3)
    
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    yield page
    context.close()
    
    # Stop Streamlit if we started it
    if streamlit_process:
        streamlit_process.terminate()
        streamlit_process.wait(timeout=5)


def test_streamlit_loads(page: Page):
    """Test that Streamlit app loads."""
    page.goto("http://localhost:8501")
    
    # Wait for app to load
    page.wait_for_selector("text=MoFrame", timeout=10000)
    
    # Check title
    expect(page.locator("text=🎬 MoFrame")).to_be_visible()
    
    # Check step indicator
    expect(page.locator("text=📁 Upload")).to_be_visible()
    expect(page.locator("text=🔍 Panels")).to_be_visible()
    expect(page.locator("text=✏️ Edit")).to_be_visible()
    expect(page.locator("text=🎬 Render")).to_be_visible()


def test_file_uploader_exists(page: Page):
    """Test that file uploader is present."""
    page.goto("http://localhost:8501")
    
    page.wait_for_selector("[data-testid='stFileUploader']", timeout=10000)
    expect(page.locator("[data-testid='stFileUploader']")).to_be_visible()


def test_render_button_exists(page: Page):
    """Test that render step has the expected elements."""
    page.goto("http://localhost:8501")
    
    page.wait_for_selector("text=🎬 Render", timeout=10000)
    
    # Check that render step text exists
    expect(page.locator("text=🎬 Render")).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
