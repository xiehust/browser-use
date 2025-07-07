#!/usr/bin/env python3
"""
Test script for PDF handling features in browser-use.

This script tests:
1. Auto-download of PDFs when navigating to PDF URLs
2. Enhanced PDF scrolling functionality
3. Manual PDF download action

@file purpose: Tests the new PDF handling features including auto-download and improved scrolling
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize controller with our enhanced actions
controller = Controller()


async def test_pdf_auto_download():
    """Test auto-download functionality when navigating to a PDF"""
    logger.info("🧪 Testing PDF auto-download functionality...")
    
    # Create a temporary downloads directory
    with tempfile.TemporaryDirectory() as temp_dir:
        downloads_path = Path(temp_dir) / "downloads"
        downloads_path.mkdir()
        
        # Create browser session with downloads enabled
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                headless=True,
                downloads_path=str(downloads_path)
            )
        )
        
        await browser_session.start()
        
        try:
            # Test with a known PDF URL
            pdf_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
            
            # Create an agent that navigates to a PDF
            agent = Agent(
                task=f"Navigate to {pdf_url} and observe what happens",
                llm=ChatOpenAI(model="gpt-4o-mini"),
                controller=controller,
                browser_session=browser_session,
            )
            
            # Run the agent
            result = await agent.run()
            
            # Check if PDF was downloaded
            pdf_files = list(downloads_path.glob("*.pdf"))
            if pdf_files:
                logger.info(f"✅ PDF auto-download successful! Downloaded: {pdf_files[0]}")
            else:
                logger.warning("⚠️ PDF auto-download did not occur")
            
            logger.info(f"Agent result: {result}")
            
        finally:
            await browser_session.close()


async def test_pdf_scrolling():
    """Test enhanced PDF scrolling functionality"""
    logger.info("🧪 Testing PDF scrolling functionality...")
    
    # Create browser session
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(headless=True)
    )
    
    await browser_session.start()
    
    try:
        # Test with a known PDF URL
        pdf_url = "https://www.adobe.com/support/products/enterprise/knowledgecenter/media/c4611_sample_explain.pdf"
        
        # Create an agent that tests PDF scrolling
        agent = Agent(
            task=f"""
            Navigate to {pdf_url} and test scrolling functionality:
            1. Go to the PDF URL
            2. Scroll down the PDF document several times
            3. Scroll back up 
            4. Report on the scrolling experience
            """,
            llm=ChatOpenAI(model="gpt-4o-mini"),
            controller=controller,
            browser_session=browser_session,
        )
        
        # Run the agent
        result = await agent.run()
        logger.info(f"✅ PDF scrolling test completed. Agent result: {result}")
        
    finally:
        await browser_session.close()


async def test_manual_pdf_download():
    """Test manual PDF download action"""
    logger.info("🧪 Testing manual PDF download action...")
    
    # Create a temporary downloads directory
    with tempfile.TemporaryDirectory() as temp_dir:
        downloads_path = Path(temp_dir) / "downloads"
        downloads_path.mkdir()
        
        # Create browser session with downloads enabled
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                headless=True,
                downloads_path=str(downloads_path)
            )
        )
        
        await browser_session.start()
        
        try:
            # Test with a known PDF URL
            pdf_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
            
            # Create an agent that manually downloads a PDF
            agent = Agent(
                task=f"""
                Navigate to {pdf_url} and manually download the PDF:
                1. Go to the PDF URL
                2. Use the download_pdf action to download the current PDF
                3. Confirm the download was successful
                """,
                llm=ChatOpenAI(model="gpt-4o-mini"),
                controller=controller,
                browser_session=browser_session,
            )
            
            # Run the agent
            result = await agent.run()
            
            # Check if PDF was downloaded
            pdf_files = list(downloads_path.glob("*.pdf"))
            if pdf_files:
                logger.info(f"✅ Manual PDF download successful! Downloaded: {pdf_files[0]}")
            else:
                logger.warning("⚠️ Manual PDF download did not occur")
            
            logger.info(f"Agent result: {result}")
            
        finally:
            await browser_session.close()


async def main():
    """Run all PDF tests"""
    logger.info("🚀 Starting PDF features test suite...")
    
    # Check if OpenAI API key is available
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("❌ OPENAI_API_KEY environment variable not set. Please set it to run tests.")
        return
    
    try:
        # Test 1: Auto-download functionality
        await test_pdf_auto_download()
        await asyncio.sleep(2)
        
        # Test 2: PDF scrolling
        await test_pdf_scrolling()
        await asyncio.sleep(2)
        
        # Test 3: Manual download
        await test_manual_pdf_download()
        
        logger.info("✅ All PDF tests completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())