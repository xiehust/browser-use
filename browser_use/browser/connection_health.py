"""Connection health monitoring and recovery utilities for browser-use."""

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from browser_use.browser.session import BrowserSession


class ConnectionHealthMonitor:
	"""Monitors CDP connection health and provides recovery mechanisms."""
	
	def __init__(self, browser_session: 'BrowserSession'):
		self.browser_session = browser_session
		self.logger = browser_session.logger
		self.last_successful_request = time.time()
		self.consecutive_failures = 0
		self.max_consecutive_failures = 3
		
	async def check_connection_health(self) -> bool:
		"""Check if the CDP connection is healthy by sending a simple request.
		
		Returns:
			True if connection is healthy, False if broken
		"""
		try:
			if not self.browser_session.agent_focus:
				self.logger.debug('🔍 No agent focus available for health check')
				return False
				
			# Simple runtime evaluation to test connection
			test_result = await asyncio.wait_for(
				self.browser_session.agent_focus.cdp_client.send.Runtime.evaluate(
					params={'expression': '1 + 1', 'returnByValue': True}, 
					session_id=self.browser_session.agent_focus.session_id
				),
				timeout=2.0
			)
			
			if test_result.get('result', {}).get('value') == 2:
				self.last_successful_request = time.time()
				self.consecutive_failures = 0
				self.logger.debug('✅ Connection health check passed')
				return True
			else:
				self.logger.debug('❌ Connection health check failed - unexpected result')
				return False
				
		except asyncio.TimeoutError:
			self.consecutive_failures += 1
			self.logger.warning(f'⏱️ Connection health check timed out (failures: {self.consecutive_failures})')
			return False
		except Exception as e:
			self.consecutive_failures += 1
			self.logger.warning(f'❌ Connection health check failed: {e} (failures: {self.consecutive_failures})')
			return False
	
	async def is_connection_broken(self) -> bool:
		"""Determine if the connection is broken and needs recovery.
		
		Returns:
			True if connection is broken and needs recovery
		"""
		# Check basic health first
		is_healthy = await self.check_connection_health()
		if is_healthy:
			return False
			
		# If we have too many consecutive failures, connection is broken
		if self.consecutive_failures >= self.max_consecutive_failures:
			self.logger.warning(f'🚨 Connection appears broken after {self.consecutive_failures} failures')
			return True
			
		# Check time since last successful request
		time_since_success = time.time() - self.last_successful_request
		if time_since_success > 30.0:  # 30 seconds without success
			self.logger.warning(f'🚨 Connection appears broken - no success for {time_since_success:.1f}s')
			return True
			
		return False
	
	async def attempt_connection_recovery(self) -> bool:
		"""Attempt to recover the broken connection.
		
		Returns:
			True if recovery was successful, False if failed
		"""
		self.logger.info('🔧 Attempting connection recovery...')
		
		try:
			# Step 1: Try to refresh the page to restore connection
			await self._refresh_page_for_recovery()
			
			# Step 2: Wait for page to stabilize
			await asyncio.sleep(2.0)
			
			# Step 3: Check if connection is now healthy
			is_healthy = await self.check_connection_health()
			
			if is_healthy:
				self.logger.info('✅ Connection recovery successful')
				self.consecutive_failures = 0
				return True
			else:
				self.logger.warning('❌ Connection recovery failed')
				return False
				
		except Exception as e:
			self.logger.error(f'❌ Connection recovery failed with error: {e}')
			return False
	
	async def _refresh_page_for_recovery(self) -> None:
		"""Refresh the current page to recover from broken connection."""
		try:
			if self.browser_session.agent_focus:
				# Try to refresh using the current session first
				try:
					await asyncio.wait_for(
						self.browser_session.agent_focus.cdp_client.send.Page.reload(
							session_id=self.browser_session.agent_focus.session_id
						),
						timeout=3.0
					)
					self.logger.debug('📄 Page refreshed successfully')
					return
				except (asyncio.TimeoutError, Exception) as e:
					self.logger.debug(f'Page refresh via CDP failed: {e}, trying alternative methods')
			
			# If CDP refresh fails, try to get a new session and refresh
			try:
				cdp_session = await asyncio.wait_for(
					self.browser_session.get_or_create_cdp_session(focus=True),
					timeout=5.0
				)
				await asyncio.wait_for(
					cdp_session.cdp_client.send.Page.reload(session_id=cdp_session.session_id),
					timeout=3.0
				)
				self.logger.debug('📄 Page refreshed with new session')
			except Exception as recovery_error:
				self.logger.warning(f'All refresh methods failed: {recovery_error}')
				raise
				
		except Exception as e:
			self.logger.error(f'Failed to refresh page for recovery: {e}')
			raise
	
	def should_check_connection_before_action(self) -> bool:
		"""Determine if we should check connection health before the next action.
		
		Returns:
			True if we should check connection health first
		"""
		# Always check if we've had recent failures
		if self.consecutive_failures > 0:
			return True
			
		# Check periodically even without failures
		time_since_check = time.time() - self.last_successful_request
		if time_since_check > 60.0:  # Check every minute
			return True
			
		return False