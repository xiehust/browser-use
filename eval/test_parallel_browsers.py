#!/usr/bin/env python3
"""
Test script to validate parallel browser execution fixes.
This script spawns multiple browser sessions in parallel to test for TargetClosedError.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the parent directory to sys.path to import browser_use modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.service import create_isolated_browser_profile, cleanup_browser_safe
from browser_use.browser.session import BrowserSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_single_browser(task_id: str, test_url: str = "https://httpbin.org/html") -> dict:
    """Test a single browser session"""
    start_time = time.time()
    browser_session = None
    
    try:
        logger.info(f"🚀 Starting browser test for task {task_id}")
        
        # Create isolated browser profile
        profile = create_isolated_browser_profile(task_id, headless=True, highlight_elements=False)
        browser_session = BrowserSession(browser_profile=profile)
        
        # Start browser with timeout
        await asyncio.wait_for(browser_session.start(), timeout=120)
        logger.info(f"✅ Browser started successfully for task {task_id}")
        
        # Navigate to test URL
        await asyncio.wait_for(browser_session.navigate(test_url), timeout=30)
        logger.info(f"✅ Navigation successful for task {task_id}")
        
        # Take a screenshot to verify browser is working
        screenshot_path = await browser_session.take_screenshot()
        logger.info(f"✅ Screenshot taken for task {task_id}: {screenshot_path}")
        
        # Small delay to simulate work
        await asyncio.sleep(2)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'task_id': task_id,
            'success': True,
            'duration': duration,
            'error': None
        }
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"❌ Browser test failed for task {task_id}: {type(e).__name__}: {e}")
        return {
            'task_id': task_id,
            'success': False,
            'duration': duration,
            'error': str(e)
        }
    
    finally:
        if browser_session:
            try:
                logger.info(f"🧹 Cleaning up browser for task {task_id}")
                await cleanup_browser_safe(browser_session)
                logger.info(f"✅ Cleanup completed for task {task_id}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed for task {task_id}: {e}")


async def test_parallel_browsers(num_browsers: int = 20) -> dict:
    """Test multiple browser sessions in parallel"""
    logger.info(f"🚀 Starting parallel browser test with {num_browsers} browsers")
    start_time = time.time()
    
    # Create semaphore to limit concurrent browser starts
    semaphore = asyncio.Semaphore(min(10, num_browsers))  # Limit to 10 concurrent startups
    
    async def run_browser_with_semaphore(task_id: str):
        async with semaphore:
            return await test_single_browser(task_id)
    
    # Create tasks for all browsers
    tasks = [
        run_browser_with_semaphore(f"test_task_{i:03d}")
        for i in range(num_browsers)
    ]
    
    # Run all browsers in parallel
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"❌ Parallel test failed: {e}")
        return {'success': False, 'error': str(e)}
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Process results
    successful = 0
    failed = 0
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed += 1
            errors.append(f"Task {i}: {type(result).__name__}: {result}")
            logger.error(f"❌ Task {i} failed with exception: {result}")
        elif isinstance(result, dict):
            if result.get('success', False):
                successful += 1
            else:
                failed += 1
                errors.append(f"Task {result.get('task_id', i)}: {result.get('error', 'Unknown error')}")
        else:
            failed += 1
            errors.append(f"Task {i}: Unexpected result type: {type(result)}")
    
    success_rate = (successful / num_browsers) * 100
    
    logger.info(f"📊 Test Results:")
    logger.info(f"   Total browsers: {num_browsers}")
    logger.info(f"   Successful: {successful}")
    logger.info(f"   Failed: {failed}")
    logger.info(f"   Success rate: {success_rate:.1f}%")
    logger.info(f"   Total duration: {total_duration:.2f}s")
    logger.info(f"   Average per browser: {total_duration/num_browsers:.2f}s")
    
    if errors:
        logger.info("❌ Errors encountered:")
        for error in errors[:10]:  # Show first 10 errors
            logger.info(f"   {error}")
        if len(errors) > 10:
            logger.info(f"   ... and {len(errors) - 10} more errors")
    
    return {
        'success': success_rate >= 90,  # Consider successful if 90%+ browsers work
        'total_browsers': num_browsers,
        'successful': successful,
        'failed': failed,
        'success_rate': success_rate,
        'total_duration': total_duration,
        'errors': errors
    }


async def main():
    """Main test function"""
    logger.info("🧪 Starting browser parallelization tests")
    
    try:
        # Test 1: Small parallel test (5 browsers)
        logger.info("\n" + "="*50)
        logger.info("TEST 1: Small parallel test (5 browsers)")
        logger.info("="*50)
        result_small = await test_parallel_browsers(5)
        
        if not result_small['success']:
            logger.error("❌ Small parallel test failed - stopping tests")
            return False
        
        # Test 2: Medium parallel test (10 browsers)
        logger.info("\n" + "="*50)
        logger.info("TEST 2: Medium parallel test (10 browsers)")
        logger.info("="*50)
        result_medium = await test_parallel_browsers(10)
        
        if not result_medium['success']:
            logger.warning("⚠️ Medium parallel test failed - continuing with caution")
        
        # Test 3: Large parallel test (20 browsers)
        logger.info("\n" + "="*50)
        logger.info("TEST 3: Large parallel test (20 browsers)")
        logger.info("="*50)
        result_large = await test_parallel_browsers(20)
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("FINAL SUMMARY")
        logger.info("="*50)
        logger.info(f"Small test (5 browsers): {'✅ PASS' if result_small['success'] else '❌ FAIL'} ({result_small['success_rate']:.1f}%)")
        logger.info(f"Medium test (10 browsers): {'✅ PASS' if result_medium['success'] else '❌ FAIL'} ({result_medium['success_rate']:.1f}%)")
        logger.info(f"Large test (20 browsers): {'✅ PASS' if result_large['success'] else '❌ FAIL'} ({result_large['success_rate']:.1f}%)")
        
        overall_success = result_small['success'] and result_medium['success'] and result_large['success']
        logger.info(f"\nOverall result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)