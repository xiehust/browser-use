"""Watchdog for handling JavaScript dialogs (alert, confirm, prompt) automatically."""

from typing import ClassVar

from bubus import BaseEvent
from pydantic import PrivateAttr

from browser_use.browser.events import DialogOpenedEvent, TabCreatedEvent
from browser_use.browser.watchdog_base import BaseWatchdog


class PopupsWatchdog(BaseWatchdog):
	"""Handles JavaScript dialogs (alert, confirm, prompt) by automatically accepting them."""

	# Events this watchdog listens to and emits
	LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [TabCreatedEvent]
	EMITS: ClassVar[list[type[BaseEvent]]] = [DialogOpenedEvent]

	# Track which targets have dialog handlers registered
	_dialog_listeners_registered: set[str] = PrivateAttr(default_factory=set)

	async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
		"""Set up JavaScript dialog handling when a new tab is created."""
		target_id = event.target_id
		
		# Skip if we've already registered for this target
		if target_id in self._dialog_listeners_registered:
			return
		
		try:
			# Create or get CDP session for this target
			cdp_session = await self.browser_session.get_or_create_cdp_session(target_id, focus=False)
			
			# Enable Page domain to receive dialog events
			await cdp_session.cdp_client.send.Page.enable(session_id=cdp_session.session_id)
			
			# Enable file chooser dialog interception
			# Note: Page.fileChooserOpened events should be handled by a separate file upload watchdog
			# await cdp_session.cdp_client.send.Page.setInterceptFileChooserDialog(
			# 	params={'enabled': True},
			# 	session_id=cdp_session.session_id
			# )
			
			# Set up handler for JavaScript dialogs
			def handle_dialog(event_data, session_id=None):
				"""Handle JavaScript dialog events - must be sync function that creates async task."""
				# Create async task to handle the dialog
				task = asyncio.create_task(self._handle_dialog_async(event_data, cdp_session, target_id))
				# Track the task (optional, for cleanup)
				task.add_done_callback(lambda t: None)  # Discard when done
			
			# Register the handler for Page.javascriptDialogOpening events
			self.logger.debug(f"Registering Page.javascriptDialogOpening handler for session {cdp_session.session_id}")
			# Note: register API automatically handles the session context
			cdp_session.cdp_client.register.Page.javascriptDialogOpening(handle_dialog)
			self.logger.debug(f"Successfully registered Page.javascriptDialogOpening handler")
			
			# Mark this target as having dialog handling set up
			self._dialog_listeners_registered.add(target_id)
			
			self.logger.info(f"✅ Set up JavaScript dialog handling for tab {target_id}")
			
		except Exception as e:
			self.logger.warning(f"Failed to set up dialog handling for tab {target_id}: {e}")
