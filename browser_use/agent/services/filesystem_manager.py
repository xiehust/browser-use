"""
File system management service for the browser-use agent.

This module provides centralized file system functionality including
initialization, state management, and download tracking.
"""

import logging
import os
import tempfile
from typing import TYPE_CHECKING

from browser_use.filesystem.file_system import FileSystem

if TYPE_CHECKING:
	from browser_use.agent.service import Agent

logger = logging.getLogger(__name__)


class FileSystemManager:
	"""Service for managing agent file system operations"""

	def __init__(self, agent: 'Agent'):
		self.agent = agent

	def initialize_file_system(self, file_system_path: str | None = None) -> None:
		"""Initialize the agent's file system with conflict checking"""
		# Check for conflicting parameters
		if self.agent.state.file_system_state and file_system_path:
			raise ValueError(
				'Cannot provide both file_system_state (from agent state) and file_system_path. '
				'Either restore from existing state or create new file system at specified path, not both.'
			)

		# Check if we should restore from existing state first
		if self.agent.state.file_system_state:
			try:
				# Restore file system from state at the exact same location
				self.agent.file_system = FileSystem.from_state(self.agent.state.file_system_state)
				# The parent directory of base_dir is the original file_system_path
				self.agent.file_system_path = str(self.agent.file_system.base_dir)
				logger.info(f'💾 File system restored from state to: {self.agent.file_system_path}')
				return
			except Exception as e:
				logger.error(f'💾 Failed to restore file system from state: {e}')
				raise e

		# Initialize new file system
		try:
			if file_system_path:
				self.agent.file_system = FileSystem(file_system_path)
				self.agent.file_system_path = file_system_path
			else:
				# create a temporary file system using agent ID
				base_tmp = tempfile.gettempdir()  # e.g., /tmp on Unix
				self.agent.file_system_path = os.path.join(base_tmp, f'browser_use_agent_{self.agent.id}')
				self.agent.file_system = FileSystem(self.agent.file_system_path)
		except Exception as e:
			logger.error(f'💾 Failed to initialize file system: {e}.')
			raise e

		# Save file system state to agent state
		self.agent.state.file_system_state = self.agent.file_system.get_state()
		logger.info(f'💾 File system path: {self.agent.file_system_path}')

	def save_file_system_state(self) -> None:
		"""Save current file system state to agent state"""
		if self.agent.file_system:
			self.agent.state.file_system_state = self.agent.file_system.get_state()
		else:
			logger.error('💾 File system is not set up. Cannot save state.')
			raise ValueError('File system is not set up. Cannot save state.')

	def update_available_file_paths(self, downloads: list[str]) -> None:
		"""Update available_file_paths with downloaded files"""
		if not self.agent.has_downloads_path:
			return

		current_files = set(self.agent.settings.available_file_paths or [])
		new_files = set(downloads) - current_files

		if new_files:
			self.agent.settings.available_file_paths = list(current_files | new_files)
			# Update message manager with new file paths
			if self.agent._message_manager is not None:
				self.agent._message_manager.available_file_paths = self.agent.settings.available_file_paths

			self.agent.logger.info(
				f'📁 Added {len(new_files)} downloaded files to available_file_paths '
				f'(total: {len(self.agent.settings.available_file_paths)} files)'
			)
			for file_path in new_files:
				self.agent.logger.info(f'📄 New file available: {file_path}')
		else:
			self.agent.logger.info(f'📁 No new downloads detected (tracking {len(current_files)} files)')

	def track_downloads_if_enabled(self) -> None:
		"""Check for new downloads and update file paths if download tracking is enabled"""
		if not self.agent.has_downloads_path:
			return

		try:
			assert self.agent.browser_session is not None, 'BrowserSession is not set up'
			current_downloads = self.agent.browser_session.downloaded_files
			if current_downloads != self.agent._last_known_downloads:
				self.update_available_file_paths(current_downloads)
				self.agent._last_known_downloads = current_downloads
		except Exception as e:
			self.agent.logger.debug(f'📁 Failed to check for new downloads: {type(e).__name__}: {e}')
