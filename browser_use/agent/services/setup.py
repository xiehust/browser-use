"""
Agent setup service for handling complex initialization logic.

This module provides centralized setup functionality for the browser-use agent,
including browser session setup, sensitive data validation, and service initialization.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bubus import EventBus
from uuid_extensions import uuid7str

from browser_use.agent.views import AgentState
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.session import DEFAULT_BROWSER_PROFILE
from browser_use.browser.types import Browser, BrowserContext, Page
from browser_use.config import CONFIG
from browser_use.controller.service import Controller
from browser_use.llm.base import BaseChatModel
from browser_use.sync import CloudSync
from browser_use.telemetry.service import ProductTelemetry
from browser_use.tokens.service import TokenCost
from browser_use.utils import _log_pretty_path

if TYPE_CHECKING:
	from browser_use.agent.service import Agent

logger = logging.getLogger(__name__)


class AgentSetupService:
	"""Service for handling complex agent initialization"""

	def __init__(self, agent: 'Agent'):
		self.agent = agent

	def validate_deprecated_parameters(self, **kwargs) -> dict[str, Any]:
		"""Validate and warn about deprecated parameters"""
		planner_llm = kwargs.get('planner_llm')
		use_vision_for_planner = kwargs.get('use_vision_for_planner', False)
		is_planner_reasoning = kwargs.get('is_planner_reasoning', False)
		extend_planner_system_message = kwargs.get('extend_planner_system_message')
		planner_interval = kwargs.get('planner_interval', 1)

		# Check for deprecated planner parameters
		planner_params = [planner_llm, use_vision_for_planner, is_planner_reasoning, extend_planner_system_message]
		if any(param is not None and param is not False for param in planner_params) or planner_interval != 1:
			logger.warning(
				'⚠️ Planner functionality has been removed in browser-use v0.3.3+. '
				'The planner_llm, use_vision_for_planner, planner_interval, is_planner_reasoning, '
				'and extend_planner_system_message parameters are deprecated and will be ignored. '
				'Please remove these parameters from your Agent() initialization.'
			)

		# Check for deprecated memory parameters
		if kwargs.get('enable_memory', False) or kwargs.get('memory_config') is not None:
			logger.warning(
				'Memory support has been removed as of version 0.3.2. '
				'The agent context for memory is significantly improved and no longer requires the old memory system. '
				"Please remove the 'enable_memory' and 'memory_config' parameters."
			)
			kwargs['enable_memory'] = False
			kwargs['memory_config'] = None

		return kwargs

	def setup_basic_components(
		self,
		task: str,
		llm: BaseChatModel,
		task_id: str | None = None,
		controller: Controller | None = None,
		display_files_in_done_text: bool = True,
		output_model_schema: Any = None,
	) -> tuple[str, str, str]:
		"""Setup basic agent components (IDs, core objects)"""

		# Setup IDs
		agent_id = task_id or uuid7str()
		task_id_final = agent_id
		session_id = uuid7str()

		# Setup core components
		self.agent.id = agent_id
		self.agent.task_id = task_id_final
		self.agent.session_id = session_id
		self.agent.task = task
		self.agent.llm = llm

		# Setup controller with structured output if needed
		self.agent.controller = (
			controller if controller is not None else Controller(display_files_in_done_text=display_files_in_done_text)
		)

		self.agent.output_model_schema = output_model_schema
		if output_model_schema is not None:
			self.agent.controller.use_structured_output_action(output_model_schema)

		return agent_id, task_id_final, session_id

	def setup_services(
		self,
		llm: BaseChatModel,
		page_extraction_llm: BaseChatModel,
		calculate_cost: bool,
		injected_agent_state: AgentState | None = None,
		cloud_sync: CloudSync | None = None,
	) -> None:
		"""Setup token cost service, telemetry, event bus, and cloud sync"""

		# Token cost service
		self.agent.token_cost_service = TokenCost(include_cost=calculate_cost)
		self.agent.token_cost_service.register_llm(llm)
		self.agent.token_cost_service.register_llm(page_extraction_llm)

		# Initialize state
		self.agent.state = injected_agent_state or AgentState()

		# Telemetry
		self.agent.telemetry = ProductTelemetry()

		# Event bus with WAL persistence
		wal_path = CONFIG.BROWSER_USE_CONFIG_DIR / 'events' / f'{self.agent.session_id}.jsonl'
		self.agent.eventbus = EventBus(name=f'Agent_{str(self.agent.id)[-4:]}', wal_path=wal_path)

		# Cloud sync service
		self.agent.enable_cloud_sync = CONFIG.BROWSER_USE_CLOUD_SYNC
		if self.agent.enable_cloud_sync or cloud_sync is not None:
			self.agent.cloud_sync = cloud_sync or CloudSync()
			# Register cloud sync handler
			self.agent.eventbus.on('*', self.agent.cloud_sync.handle_event)

	def setup_browser_session(
		self,
		page: Page | None = None,
		browser: Browser | BrowserSession | None = None,
		browser_context: BrowserContext | None = None,
		browser_profile: BrowserProfile | None = None,
		browser_session: BrowserSession | None = None,
	) -> None:
		"""Setup browser session with proper validation and copying"""

		if isinstance(browser, BrowserSession):
			browser_session = browser_session or browser

		browser_context = page.context if page else browser_context
		browser_profile = browser_profile or DEFAULT_BROWSER_PROFILE

		if browser_session:
			# Always copy sessions that are passed in to avoid agents overwriting each other
			if browser_session._owns_browser_resources:
				self.agent.browser_session = browser_session
			else:
				self.agent.logger.warning(
					'⚠️ Attempting to use multiple Agents with the same BrowserSession! '
					'This is not supported yet and will likely lead to strange behavior, '
					'use separate BrowserSessions for each Agent.'
				)
				self.agent.browser_session = browser_session.model_copy()
		else:
			if browser is not None:
				assert isinstance(browser, Browser), 'Browser is not set up'
			self.agent.browser_session = BrowserSession(
				browser_profile=browser_profile,
				browser=browser,
				browser_context=browser_context,
				agent_current_page=page,
				id=uuid7str()[:-4] + self.agent.id[-4:],  # re-use the same 4-char suffix
			)

	def validate_sensitive_data(self, sensitive_data: dict[str, str | dict[str, str]] | None) -> None:
		"""Validate sensitive data configuration and show security warnings"""
		if not sensitive_data:
			return

		self.agent.sensitive_data = sensitive_data

		# Check if sensitive_data has domain-specific credentials
		has_domain_specific_credentials = any(isinstance(v, dict) for v in sensitive_data.values())

		# If no allowed_domains are configured, show a security warning
		if not self.agent.browser_profile.allowed_domains:
			self.agent.logger.error(
				'⚠️⚠️⚠️ Agent(sensitive_data=••••••••) was provided but BrowserSession(allowed_domains=[...]) is not locked down! ⚠️⚠️⚠️\n'
				'          ☠️ If the agent visits a malicious website and encounters a prompt-injection attack, your sensitive_data may be exposed!\n\n'
				'             https://docs.browser-use.com/customize/browser-settings#restrict-urls\n'
				'Waiting 10 seconds before continuing... Press [Ctrl+C] to abort.'
			)
			if sys.stdin.isatty():
				try:
					time.sleep(10)
				except KeyboardInterrupt:
					print(
						'\n\n 🛑 Exiting now... set BrowserSession(allowed_domains=["example.com", "example.org"]) '
						'to only domains you trust to see your sensitive_data.'
					)
					sys.exit(0)
			else:
				pass  # no point waiting if we're not in an interactive shell
			self.agent.logger.warning(
				'‼️ Continuing with insecure settings for now... but this will become a hard error in the future!'
			)

		# If we're using domain-specific credentials, validate domain patterns
		elif has_domain_specific_credentials:
			domain_patterns = [k for k, v in sensitive_data.items() if isinstance(v, dict)]

			# Validate each domain pattern against allowed_domains
			for domain_pattern in domain_patterns:
				is_allowed = False
				for allowed_domain in self.agent.browser_profile.allowed_domains:
					# Special cases that don't require URL matching
					if domain_pattern == allowed_domain or allowed_domain == '*':
						is_allowed = True
						break

					# Extract the domain parts, ignoring scheme
					pattern_domain = domain_pattern.split('://')[-1] if '://' in domain_pattern else domain_pattern
					allowed_domain_part = allowed_domain.split('://')[-1] if '://' in allowed_domain else allowed_domain

					# Check if pattern is covered by an allowed domain
					if pattern_domain == allowed_domain_part or (
						allowed_domain_part.startswith('*.')
						and (pattern_domain == allowed_domain_part[2:] or pattern_domain.endswith('.' + allowed_domain_part[2:]))
					):
						is_allowed = True
						break

				if not is_allowed:
					self.agent.logger.warning(
						f'⚠️ Domain pattern "{domain_pattern}" in sensitive_data is not covered by any pattern '
						f'in allowed_domains={self.agent.browser_profile.allowed_domains}\n'
						f'   This may be a security risk as credentials could be used on unintended domains.'
					)

	def setup_download_tracking(self) -> None:
		"""Initialize download tracking if downloads path is configured"""
		assert self.agent.browser_session is not None, 'BrowserSession is not set up'

		self.agent.has_downloads_path = self.agent.browser_session.browser_profile.downloads_path is not None
		if self.agent.has_downloads_path:
			self.agent._last_known_downloads = []
			self.agent.logger.info('📁 Initialized download tracking for agent')

	def setup_conversation_saving(self, save_conversation_path: str | Path | None) -> None:
		"""Setup conversation saving if path is provided"""
		if save_conversation_path:
			self.agent.settings.save_conversation_path = Path(save_conversation_path).expanduser().resolve()
			self.agent.logger.info(f'💬 Saving conversation to {_log_pretty_path(self.agent.settings.save_conversation_path)}')

	def setup_pause_control(self) -> None:
		"""Setup pause/resume control event"""
		self.agent._external_pause_event = asyncio.Event()
		self.agent._external_pause_event.set()

	def handle_model_specific_settings(self, llm: BaseChatModel) -> None:
		"""Handle model-specific settings and warnings"""

		# Handle DeepSeek models
		if 'deepseek' in llm.model.lower():
			self.agent.logger.warning('⚠️ DeepSeek models do not support use_vision=True yet. Setting use_vision=False for now...')
			self.agent.settings.use_vision = False

		# Handle XAI models
		if 'grok' in llm.model.lower():
			self.agent.logger.warning('⚠️ XAI models do not support use_vision=True yet. Setting use_vision=False for now...')
			self.agent.settings.use_vision = False
