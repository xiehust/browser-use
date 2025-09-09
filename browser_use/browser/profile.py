import sys
import tempfile
from collections.abc import Iterable
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlparse

from pydantic import AfterValidator, AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from browser_use.config import CONFIG
from browser_use.utils import _log_pretty_path, logger

CHROME_DEBUG_PORT = 9242  # use a non-default port to avoid conflicts with other tools / devs using 9222
CHROME_DISABLED_COMPONENTS = [
	# Playwright defaults: https://github.com/microsoft/playwright/blob/41008eeddd020e2dee1c540f7c0cdfa337e99637/packages/playwright-core/src/server/chromium/chromiumSwitches.ts#L76
	# AcceptCHFrame,AutoExpandDetailsElement,AvoidUnnecessaryBeforeUnloadCheckSync,CertificateTransparencyComponentUpdater,DeferRendererTasksAfterInput,DestroyProfileOnBrowserClose,DialMediaRouteProvider,ExtensionManifestV2Disabled,GlobalMediaControls,HttpsUpgrades,ImprovedCookieControls,LazyFrameLoading,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate
	# See https:#github.com/microsoft/playwright/pull/10380
	'AcceptCHFrame',
	# See https:#github.com/microsoft/playwright/pull/10679
	'AutoExpandDetailsElement',
	# See https:#github.com/microsoft/playwright/issues/14047
	'AvoidUnnecessaryBeforeUnloadCheckSync',
	# See https:#github.com/microsoft/playwright/pull/12992
	'CertificateTransparencyComponentUpdater',
	'DestroyProfileOnBrowserClose',
	# See https:#github.com/microsoft/playwright/pull/13854
	'DialMediaRouteProvider',
	# Chromium is disabling manifest version 2. Allow testing it as long as Chromium can actually run it.
	# Disabled in https:#chromium-review.googlesource.com/c/chromium/src/+/6265903.
	'ExtensionManifestV2Disabled',
	'GlobalMediaControls',
	# See https:#github.com/microsoft/playwright/pull/27605
	'HttpsUpgrades',
	'ImprovedCookieControls',
	'LazyFrameLoading',
	# Hides the Lens feature in the URL address bar. Its not working in unofficial builds.
	'LensOverlay',
	# See https:#github.com/microsoft/playwright/pull/8162
	'MediaRouter',
	# See https:#github.com/microsoft/playwright/issues/28023
	'PaintHolding',
	# See https:#github.com/microsoft/playwright/issues/32230
	'ThirdPartyStoragePartitioning',
	# See https://github.com/microsoft/playwright/issues/16126
	'Translate',
	# 3
	# Added by us:
	'AutomationControlled',
	'BackForwardCache',
	'OptimizationHints',
	'ProcessPerSiteUpToMainFrameThreshold',
	'InterestFeedContentSuggestions',
	'CalculateNativeWinOcclusion',  # chrome normally stops rendering tabs if they are not visible (occluded by a foreground window or other app)
	# 'BackForwardCache',  # agent does actually use back/forward navigation, but we can disable if we ever remove that
	'HeavyAdPrivacyMitigations',
	'PrivacySandboxSettings4',
	'AutofillServerCommunication',
	'CrashReporting',
	'OverscrollHistoryNavigation',
	'InfiniteSessionRestore',
	'ExtensionDisableUnsupportedDeveloper',
	'ExtensionManifestV2Unsupported',
]

CHROME_HEADLESS_ARGS = [
	'--headless=new',
]

CHROME_DOCKER_ARGS = [
	# '--disable-gpu',    # GPU is actually supported in headless docker mode now, but sometimes useful to test without it
	'--no-sandbox',
	'--disable-gpu-sandbox',
	'--disable-setuid-sandbox',
	'--disable-dev-shm-usage',
	'--no-xshm',
	'--no-zygote',
	# '--single-process',  # might be the cause of "Target page, context or browser has been closed" errors during CDP page.captureScreenshot https://stackoverflow.com/questions/51629151/puppeteer-protocol-error-page-navigate-target-closed
	'--disable-site-isolation-trials',  # lowers RAM use by 10-16% in docker, but could lead to easier bot blocking if pages can detect it?
]


CHROME_DISABLE_SECURITY_ARGS = [
	'--disable-site-isolation-trials',
	'--disable-web-security',
	'--disable-features=IsolateOrigins,site-per-process',
	'--allow-running-insecure-content',
	'--ignore-certificate-errors',
	'--ignore-ssl-errors',
	'--ignore-certificate-errors-spki-list',
]

CHROME_DETERMINISTIC_RENDERING_ARGS = [
	'--deterministic-mode',
	'--js-flags=--random-seed=1157259159',
	'--force-device-scale-factor=2',
	'--enable-webgl',
	# '--disable-skia-runtime-opts',
	# '--disable-2d-canvas-clip-aa',
	'--font-render-hinting=none',
	'--force-color-profile=srgb',
]

CHROME_DEFAULT_ARGS = [
	# # provided by playwright by default: https://github.com/microsoft/playwright/blob/41008eeddd020e2dee1c540f7c0cdfa337e99637/packages/playwright-core/src/server/chromium/chromiumSwitches.ts#L76
	'--disable-field-trial-config',  # https://source.chromium.org/chromium/chromium/src/+/main:testing/variations/README.md
	'--disable-background-networking',
	'--disable-background-timer-throttling',  # agents might be working on background pages if the human switches to another tab
	'--disable-backgrounding-occluded-windows',  # same deal, agents are often working on backgrounded browser windows
	'--disable-back-forward-cache',  # Avoids surprises like main request not being intercepted during page.goBack().
	'--disable-breakpad',
	'--disable-client-side-phishing-detection',
	'--disable-component-extensions-with-background-pages',
	'--disable-component-update',  # Avoids unneeded network activity after startup.
	'--no-default-browser-check',
	# '--disable-default-apps',
	'--disable-dev-shm-usage',  # crucial for docker support, harmless in non-docker environments
	# '--disable-extensions',
	# '--disable-features=' + disabledFeatures(assistantMode).join(','),
	# '--allow-pre-commit-input',  # duplicate removed
	'--disable-hang-monitor',
	'--disable-ipc-flooding-protection',  # important to be able to make lots of CDP calls in a tight loop
	'--disable-popup-blocking',
	'--disable-prompt-on-repost',
	'--disable-renderer-backgrounding',
	# '--force-color-profile=srgb',  # moved to CHROME_DETERMINISTIC_RENDERING_ARGS
	'--metrics-recording-only',
	'--no-first-run',
	'--password-store=basic',
	'--use-mock-keychain',
	# // See https://chromium-review.googlesource.com/c/chromium/src/+/2436773
	'--no-service-autorun',
	'--export-tagged-pdf',
	# // https://chromium-review.googlesource.com/c/chromium/src/+/4853540
	'--disable-search-engine-choice-screen',
	# // https://issues.chromium.org/41491762
	'--unsafely-disable-devtools-self-xss-warnings',
	# added by us:
	'--enable-features=NetworkService,NetworkServiceInProcess',
	'--enable-network-information-downlink-max',
	'--test-type=gpu',
	'--disable-sync',
	'--allow-legacy-extension-manifests',
	'--allow-pre-commit-input',
	'--disable-blink-features=AutomationControlled',
	'--install-autogenerated-theme=0,0,0',
	# '--hide-scrollbars',                     # leave them visible! the agent uses them to know when it needs to scroll to see more options
	'--log-level=2',
	# '--enable-logging=stderr',
	'--disable-focus-on-load',
	'--disable-window-activation',
	'--generate-pdf-document-outline',
	'--no-pings',
	'--ash-no-nudges',
	'--disable-infobars',
	'--simulate-outdated-no-au="Tue, 31 Dec 2099 23:59:59 GMT"',
	'--hide-crash-restore-bubble',
	'--suppress-message-center-popups',
	'--disable-domain-reliability',
	'--disable-datasaver-prompt',
	'--disable-speech-synthesis-api',
	'--disable-speech-api',
	'--disable-print-preview',
	'--safebrowsing-disable-auto-update',
	'--disable-external-intent-requests',
	'--disable-desktop-notifications',
	'--noerrdialogs',
	'--silent-debugger-extension-api',
	# Extension welcome tab suppression for automation
	'--disable-extensions-http-throttling',
	'--extensions-on-chrome-urls',
	'--disable-default-apps',
	f'--disable-features={",".join(CHROME_DISABLED_COMPONENTS)}',
]


class ViewportSize(BaseModel):
	width: int = Field(ge=0)
	height: int = Field(ge=0)

	def __getitem__(self, key: str) -> int:
		return dict(self)[key]

	def __setitem__(self, key: str, value: int) -> None:
		setattr(self, key, value)


@cache
def get_display_size() -> ViewportSize | None:
	# macOS
	try:
		from AppKit import NSScreen  # type: ignore[import]

		screen = NSScreen.mainScreen().frame()
		size = ViewportSize(width=int(screen.size.width), height=int(screen.size.height))
		logger.debug(f'Display size: {size}')
		return size
	except Exception:
		pass

	# Windows & Linux
	try:
		from screeninfo import get_monitors

		monitors = get_monitors()
		monitor = monitors[0]
		size = ViewportSize(width=int(monitor.width), height=int(monitor.height))
		logger.debug(f'Display size: {size}')
		return size
	except Exception:
		pass

	logger.debug('No display size found')
	return None


def get_window_adjustments() -> tuple[int, int]:
	"""Returns recommended x, y offsets for window positioning"""

	if sys.platform == 'darwin':  # macOS
		return -4, 24  # macOS has a small title bar, no border
	elif sys.platform == 'win32':  # Windows
		return -8, 0  # Windows has a border on the left
	else:  # Linux
		return 0, 0


def validate_url(url: str, schemes: Iterable[str] = ()) -> str:
	"""Validate URL format and optionally check for specific schemes."""
	parsed_url = urlparse(url)
	if not parsed_url.netloc:
		raise ValueError(f'Invalid URL format: {url}')
	if schemes and parsed_url.scheme and parsed_url.scheme.lower() not in schemes:
		raise ValueError(f'URL has invalid scheme: {url} (expected one of {schemes})')
	return url


def validate_float_range(value: float, min_val: float, max_val: float) -> float:
	"""Validate that float is within specified range."""
	if not min_val <= value <= max_val:
		raise ValueError(f'Value {value} outside of range {min_val}-{max_val}')
	return value


def validate_cli_arg(arg: str) -> str:
	"""Validate that arg is a valid CLI argument."""
	if not arg.startswith('--'):
		raise ValueError(f'Invalid CLI argument: {arg} (should start with --, e.g. --some-key="some value here")')
	return arg


# ===== Enum definitions =====


class RecordHarContent(str, Enum):
	OMIT = 'omit'
	EMBED = 'embed'
	ATTACH = 'attach'


class RecordHarMode(str, Enum):
	FULL = 'full'
	MINIMAL = 'minimal'


class BrowserChannel(str, Enum):
	CHROMIUM = 'chromium'
	CHROME = 'chrome'
	CHROME_BETA = 'chrome-beta'
	CHROME_DEV = 'chrome-dev'
	CHROME_CANARY = 'chrome-canary'
	MSEDGE = 'msedge'
	MSEDGE_BETA = 'msedge-beta'
	MSEDGE_DEV = 'msedge-dev'
	MSEDGE_CANARY = 'msedge-canary'


# Using constants from central location in browser_use.config
BROWSERUSE_DEFAULT_CHANNEL = BrowserChannel.CHROMIUM


# ===== Type definitions with validators =====

UrlStr = Annotated[str, AfterValidator(validate_url)]
NonNegativeFloat = Annotated[float, AfterValidator(lambda x: validate_float_range(x, 0, float('inf')))]
CliArgStr = Annotated[str, AfterValidator(validate_cli_arg)]


# ===== Base Models =====


class BrowserContextArgs(BaseModel):
	"""
	Base model for common browser context parameters used by
	both BrowserType.new_context() and BrowserType.launch_persistent_context().

	https://playwright.dev/python/docs/api/class-browser#browser-new-context
	"""

	model_config = ConfigDict(extra='ignore', validate_assignment=False, revalidate_instances='always', populate_by_name=True)

	# Browser context parameters
	accept_downloads: bool = True

	# Security options
	# proxy: ProxySettings | None = None
	permissions: list[str] = Field(
		default_factory=lambda: ['clipboardReadWrite', 'notifications'],
		description='Browser permissions to grant (CDP Browser.grantPermissions).',
		# clipboardReadWrite is for google sheets and pyperclip automations
		# notifications are to avoid browser fingerprinting
	)
	# client_certificates: list[ClientCertificate] = Field(default_factory=list)
	# http_credentials: HttpCredentials | None = None

	# Viewport options
	user_agent: str | None = None
	screen: ViewportSize | None = None
	viewport: ViewportSize | None = Field(default=None)
	no_viewport: bool | None = None
	device_scale_factor: NonNegativeFloat | None = None
	# geolocation: Geolocation | None = None

	# Recording Options
	record_har_content: RecordHarContent = RecordHarContent.EMBED
	record_har_mode: RecordHarMode = RecordHarMode.FULL
	record_har_path: str | Path | None = Field(default=None, validation_alias=AliasChoices('save_har_path', 'record_har_path'))
	record_video_dir: str | Path | None = Field(
		default=None, validation_alias=AliasChoices('save_recording_path', 'record_video_dir')
	)


class BrowserConnectArgs(BaseModel):
	"""
	Base model for common browser connect parameters used by
	both connect_over_cdp() and connect_over_ws().

	https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect
	https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp
	"""

	model_config = ConfigDict(extra='ignore', validate_assignment=True, revalidate_instances='always', populate_by_name=True)

	headers: dict[str, str] | None = Field(default=None, description='Additional HTTP headers to be sent with connect request')


class BrowserLaunchArgs(BaseModel):
	"""
	Base model for common browser launch parameters used by
	both launch() and launch_persistent_context().

	https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch
	"""

	model_config = ConfigDict(
		extra='ignore',
		validate_assignment=True,
		revalidate_instances='always',
		from_attributes=True,
		validate_by_name=True,
		validate_by_alias=True,
		populate_by_name=True,
	)

	env: dict[str, str | float | bool] | None = Field(
		default=None,
		description='Extra environment variables to set when launching the browser. If None, inherits from the current process.',
	)
	executable_path: str | Path | None = Field(
		default=None,
		validation_alias=AliasChoices('browser_binary_path', 'chrome_binary_path'),
		description='Path to the chromium-based browser executable to use.',
	)
	headless: bool | None = Field(default=None, description='Whether to run the browser in headless or windowed mode.')
	args: list[CliArgStr] = Field(
		default_factory=list, description='List of *extra* CLI args to pass to the browser when launching.'
	)
	ignore_default_args: list[CliArgStr] | Literal[True] = Field(
		default_factory=lambda: [
			'--enable-automation',  # we mask the automation fingerprint via JS and other flags
			'--disable-extensions',  # allow browser extensions
			'--hide-scrollbars',  # always show scrollbars in screenshots so agent knows there is more content below it can scroll down to
			'--disable-features=AcceptCHFrame,AutoExpandDetailsElement,AvoidUnnecessaryBeforeUnloadCheckSync,CertificateTransparencyComponentUpdater,DeferRendererTasksAfterInput,DestroyProfileOnBrowserClose,DialMediaRouteProvider,ExtensionManifestV2Disabled,GlobalMediaControls,HttpsUpgrades,ImprovedCookieControls,LazyFrameLoading,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate',
		],
		description='List of default CLI args to stop playwright from applying (see https://github.com/microsoft/playwright/blob/41008eeddd020e2dee1c540f7c0cdfa337e99637/packages/playwright-core/src/server/chromium/chromiumSwitches.ts)',
	)
	channel: BrowserChannel | None = None  # https://playwright.dev/docs/browsers#chromium-headless-shell
	chromium_sandbox: bool = Field(
		default=not CONFIG.IN_DOCKER, description='Whether to enable Chromium sandboxing (recommended unless inside Docker).'
	)
	devtools: bool = Field(
		default=False, description='Whether to open DevTools panel automatically for every page, only works when headless=False.'
	)

	# proxy: ProxySettings | None = Field(default=None, description='Proxy settings to use to connect to the browser.')
	downloads_path: str | Path | None = Field(
		default=None,
		description='Directory to save downloads to.',
		validation_alias=AliasChoices('downloads_dir', 'save_downloads_path'),
	)
	traces_dir: str | Path | None = Field(
		default=None,
		description='Directory for saving playwright trace.zip files (playwright actions, screenshots, DOM snapshots, HAR traces).',
		validation_alias=AliasChoices('trace_path', 'traces_dir'),
	)

	# firefox_user_prefs: dict[str, str | float | bool] = Field(default_factory=dict)

	@model_validator(mode='after')
	def validate_devtools_headless(self) -> Self:
		"""Cannot open devtools when headless is True"""
		assert not (self.headless and self.devtools), 'headless=True and devtools=True cannot both be set at the same time'
		return self

	@model_validator(mode='after')
	def set_default_downloads_path(self) -> Self:
		"""Set a unique default downloads path if none is provided."""
		if self.downloads_path is None:
			import uuid

			# Create unique directory in /tmp for downloads
			unique_id = str(uuid.uuid4())[:8]  # 8 characters
			downloads_path = Path(f'/tmp/browser-use-downloads-{unique_id}')

			# Ensure path doesn't already exist (extremely unlikely but possible)
			while downloads_path.exists():
				unique_id = str(uuid.uuid4())[:8]
				downloads_path = Path(f'/tmp/browser-use-downloads-{unique_id}')

			self.downloads_path = downloads_path
			self.downloads_path.mkdir(parents=True, exist_ok=True)
		return self

	@staticmethod
	def args_as_dict(args: list[str]) -> dict[str, str]:
		"""Return the extra launch CLI args as a dictionary."""
		args_dict = {}
		for arg in args:
			key, value, *_ = [*arg.split('=', 1), '', '', '']
			args_dict[key.strip().lstrip('-')] = value.strip()
		return args_dict

	@staticmethod
	def args_as_list(args: dict[str, str]) -> list[str]:
		"""Return the extra launch CLI args as a list of strings."""
		return [f'--{key.lstrip("-")}={value}' if value else f'--{key.lstrip("-")}' for key, value in args.items()]


# ===== API-specific Models =====


class BrowserNewContextArgs(BrowserContextArgs):
	"""
	Pydantic model for new_context() arguments.
	Extends BaseContextParams with storage_state parameter.

	https://playwright.dev/python/docs/api/class-browser#browser-new-context
	"""

	model_config = ConfigDict(extra='ignore', validate_assignment=False, revalidate_instances='always', populate_by_name=True)

	# storage_state is not supported in launch_persistent_context()
	storage_state: str | Path | dict[str, Any] | None = None
	# TODO: use StorageState type instead of dict[str, Any]

	# to apply this to existing contexts (incl cookies, localStorage, IndexedDB), see:
	# - https://github.com/microsoft/playwright/pull/34591/files
	# - playwright-core/src/server/storageScript.ts restore() function
	# - https://github.com/Skn0tt/playwright/blob/c446bc44bac4fbfdf52439ba434f92192459be4e/packages/playwright-core/src/server/storageScript.ts#L84C1-L123C2

	# @field_validator('storage_state', mode='after')
	# def load_storage_state_from_file(self) -> Self:
	# 	"""Load storage_state from file if it's a path."""
	# 	if isinstance(self.storage_state, (str, Path)):
	# 		storage_state_file = Path(self.storage_state)
	# 		try:
	# 			parsed_storage_state = json.loads(storage_state_file.read_text())
	# 			validated_storage_state = StorageState(**parsed_storage_state)
	# 			self.storage_state = validated_storage_state
	# 		except Exception as e:
	# 			raise ValueError(f'Failed to load storage state file {self.storage_state}: {e}') from e
	# 	return self
	pass


class BrowserLaunchPersistentContextArgs(BrowserLaunchArgs, BrowserContextArgs):
	"""
	Pydantic model for launch_persistent_context() arguments.
	Combines browser launch parameters and context parameters,
	plus adds the user_data_dir parameter.

	https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context
	"""

	model_config = ConfigDict(extra='ignore', validate_assignment=False, revalidate_instances='always')

	# Required parameter specific to launch_persistent_context, but can be None to use incognito temp dir
	user_data_dir: str | Path | None = None

	@field_validator('user_data_dir', mode='after')
	@classmethod
	def validate_user_data_dir(cls, v: str | Path | None) -> str | Path:
		"""Validate user data dir is set to a non-default path."""
		if v is None:
			return tempfile.mkdtemp(prefix='browser-use-user-data-dir-')
		return Path(v).expanduser().resolve()


class ProxySettings(BaseModel):
	"""Typed proxy settings for Chromium traffic.

	- server: Full proxy URL, e.g. "http://host:8080" or "socks5://host:1080"
	- bypass: Comma-separated hosts to bypass (e.g. "localhost,127.0.0.1,*.internal")
	- username/password: Optional credentials for authenticated proxies
	"""

	server: str | None = Field(default=None, description='Proxy URL, e.g. http://host:8080 or socks5://host:1080')
	bypass: str | None = Field(default=None, description='Comma-separated hosts to bypass, e.g. localhost,127.0.0.1,*.internal')
	username: str | None = Field(default=None, description='Proxy auth username')
	password: str | None = Field(default=None, description='Proxy auth password')

	def __getitem__(self, key: str) -> str | None:
		return getattr(self, key)


class BrowserProfile(BrowserConnectArgs, BrowserLaunchPersistentContextArgs, BrowserLaunchArgs, BrowserNewContextArgs):
	"""
	A BrowserProfile is a static template collection of kwargs that can be passed to:
		- BrowserType.launch(**BrowserLaunchArgs)
		- BrowserType.connect(**BrowserConnectArgs)
		- BrowserType.connect_over_cdp(**BrowserConnectArgs)
		- BrowserType.launch_persistent_context(**BrowserLaunchPersistentContextArgs)
		- BrowserContext.new_context(**BrowserNewContextArgs)
		- BrowserSession(**BrowserProfile)
	"""

	model_config = ConfigDict(
		extra='ignore',
		validate_assignment=True,
		revalidate_instances='always',
		from_attributes=True,
		validate_by_name=True,
		validate_by_alias=True,
	)

	# ... extends options defined in:
	# BrowserLaunchPersistentContextArgs, BrowserLaunchArgs, BrowserNewContextArgs, BrowserConnectArgs

	# Session/connection configuration
	cdp_url: str | None = Field(default=None, description='CDP URL for connecting to existing browser instance')
	is_local: bool = Field(default=False, description='Whether this is a local browser instance')
	# label: str = 'default'

	# custom options we provide that aren't native playwright kwargs
	disable_security: bool = Field(default=False, description='Disable browser security features.')
	deterministic_rendering: bool = Field(default=False, description='Enable deterministic rendering flags.')
	allowed_domains: list[str] | None = Field(
		default=None,
		description='List of allowed domains for navigation e.g. ["*.google.com", "https://example.com", "chrome-extension://*"]',
	)
	keep_alive: bool | None = Field(default=None, description='Keep browser alive after agent run.')

	# --- Proxy settings ---
	# New consolidated proxy config (typed)
	proxy: ProxySettings | None = Field(
		default=None,
		description='Proxy settings. Use browser_use.browser.profile.ProxySettings(server, bypass, username, password)',
	)
	enable_default_extensions: bool = Field(
		default=True,
		description="Enable automation-optimized extensions: ad blocking (uBlock Origin), cookie handling (I still don't care about cookies), and URL cleaning (ClearURLs). All extensions work automatically without manual intervention. Extensions are automatically downloaded and loaded when enabled.",
	)
	cookie_whitelist_domains: list[str] = Field(
		default_factory=lambda: ['nature.com', 'qatarairways.com'],
		description='List of domains to whitelist in the "I still don\'t care about cookies" extension, preventing automatic cookie banner handling on these sites.',
	)

	window_size: ViewportSize | None = Field(
		default=None,
		description='Browser window size to use when headless=False.',
	)
	window_height: int | None = Field(default=None, description='DEPRECATED, use window_size["height"] instead', exclude=True)
	window_width: int | None = Field(default=None, description='DEPRECATED, use window_size["width"] instead', exclude=True)
	window_position: ViewportSize | None = Field(
		default=ViewportSize(width=0, height=0),
		description='Window position to use for the browser x,y from the top left when headless=False.',
	)
	cross_origin_iframes: bool = Field(
		default=True,
		description='Enable cross-origin iframe support (OOPIF/Out-of-Process iframes). When False, only same-origin frames are processed to avoid complexity and hanging.',
	)
	max_iframes: int = Field(
		default=100,
		description='Maximum number of iframe documents to process to prevent crashes.',
	)
	max_iframe_depth: int = Field(
		ge=0,
		default=5,
		description='Maximum depth for cross-origin iframe recursion (default: 5 levels deep).',
	)

	# --- Page load/wait timings ---

	minimum_wait_page_load_time: float = Field(default=0.25, description='Minimum time to wait before capturing page state.')
	wait_for_network_idle_page_load_time: float = Field(default=0.5, description='Time to wait for network idle.')

	wait_between_actions: float = Field(default=0.5, description='Time to wait between actions.')

	# --- UI/viewport/DOM ---

	highlight_elements: bool = Field(default=True, description='Highlight interactive elements on the page.')
	filter_highlight_ids: bool = Field(
		default=True, description='Only show element IDs in highlights if llm_representation is less than 10 characters.'
	)
	paint_order_filtering: bool = Field(default=True, description='Enable paint order filtering. Slightly experimental.')

	# --- Downloads ---
	auto_download_pdfs: bool = Field(default=True, description='Automatically download PDFs when navigating to PDF viewer pages.')

	profile_directory: str = 'Default'  # e.g. 'Profile 1', 'Profile 2', 'Custom Profile', etc.

	# these can be found in BrowserLaunchArgs, BrowserLaunchPersistentContextArgs, BrowserNewContextArgs, BrowserConnectArgs:
	# save_recording_path: alias of record_video_dir
	# save_har_path: alias of record_har_path
	# trace_path: alias of traces_dir

	# these shadow the old playwright args on BrowserContextArgs, but it's ok
	# because we handle them ourselves in a watchdog and we no longer use playwright, so they should live in the scope for our own config in BrowserProfile long-term
	record_video_dir: Path | None = Field(
		default=None,
		description='Directory to save video recordings. If set, a video of the session will be recorded.',
		validation_alias=AliasChoices('save_recording_path', 'record_video_dir'),
	)
	record_video_size: ViewportSize | None = Field(
		default=None, description='Video frame size. If not set, it will use the viewport size.'
	)
	record_video_framerate: int = Field(default=30, description='The framerate to use for the video recording.')

	# TODO: finish implementing extension support in extensions.py
	# extension_ids_to_preinstall: list[str] = Field(
	# 	default_factory=list, description='List of Chrome extension IDs to preinstall.'
	# )
	# extensions_dir: Path = Field(
	# 	default_factory=lambda: Path('~/.config/browseruse/cache/extensions').expanduser(),
	# 	description='Directory containing .crx extension files.',
	# )

	def __repr__(self) -> str:
		short_dir = _log_pretty_path(self.user_data_dir) if self.user_data_dir else '<incognito>'
		return f'BrowserProfile(user_data_dir= {short_dir}, headless={self.headless})'

	def __str__(self) -> str:
		return 'BrowserProfile'

	@model_validator(mode='after')
	def copy_old_config_names_to_new(self) -> Self:
		"""Copy old config window_width & window_height to window_size."""
		if self.window_width or self.window_height:
			logger.warning(
				f'⚠️ BrowserProfile(window_width=..., window_height=...) are deprecated, use BrowserProfile(window_size={"width": 1920, "height": 1080}) instead.'
			)
			window_size = self.window_size or ViewportSize(width=0, height=0)
			window_size['width'] = window_size['width'] or self.window_width or 1920
			window_size['height'] = window_size['height'] or self.window_height or 1080
			self.window_size = window_size

		return self

	@model_validator(mode='after')
	def warn_storage_state_user_data_dir_conflict(self) -> Self:
		"""Warn when both storage_state and user_data_dir are set, as this can cause conflicts."""
		has_storage_state = self.storage_state is not None
		has_user_data_dir = (self.user_data_dir is not None) and ('tmp' not in str(self.user_data_dir).lower())

		if has_storage_state and has_user_data_dir:
			logger.warning(
				f'⚠️ BrowserSession(...) was passed both storage_state AND user_data_dir. storage_state={self.storage_state} will forcibly overwrite '
				f'cookies/localStorage/sessionStorage in user_data_dir={self.user_data_dir}. '
				f'For multiple browsers in parallel, use only storage_state with user_data_dir=None, '
				f'or use a separate user_data_dir for each browser and set storage_state=None.'
			)
		return self

	@model_validator(mode='after')
	def warn_user_data_dir_non_default_version(self) -> Self:
		"""
		If user is using default profile dir with a non-default channel, force-change it
		to avoid corrupting the default data dir created with a different channel.
		"""

		is_not_using_default_chromium = self.executable_path or self.channel not in (BROWSERUSE_DEFAULT_CHANNEL, None)
		if self.user_data_dir == CONFIG.BROWSER_USE_DEFAULT_USER_DATA_DIR and is_not_using_default_chromium:
			alternate_name = (
				Path(self.executable_path).name.lower().replace(' ', '-')
				if self.executable_path
				else self.channel.name.lower()
				if self.channel
				else 'None'
			)
			logger.warning(
				f'⚠️ {self} Changing user_data_dir= {_log_pretty_path(self.user_data_dir)} ➡️ .../default-{alternate_name} to avoid {alternate_name.upper()} corruping default profile created by {BROWSERUSE_DEFAULT_CHANNEL.name}'
			)
			self.user_data_dir = CONFIG.BROWSER_USE_DEFAULT_USER_DATA_DIR.parent / f'default-{alternate_name}'
		return self

	@model_validator(mode='after')
	def warn_deterministic_rendering_weirdness(self) -> Self:
		if self.deterministic_rendering:
			logger.warning(
				'⚠️ BrowserSession(deterministic_rendering=True) is NOT RECOMMENDED. It breaks many sites and increases chances of getting blocked by anti-bot systems. '
				'It hardcodes the JS random seed and forces browsers across Linux/Mac/Windows to use the same font rendering engine so that identical screenshots can be generated.'
			)
		return self

	@model_validator(mode='after')
	def validate_proxy_settings(self) -> Self:
		"""Ensure proxy configuration is consistent."""
		if self.proxy and (self.proxy.bypass and not self.proxy.server):
			logger.warning('BrowserProfile.proxy.bypass provided but proxy has no server; bypass will be ignored.')
		return self

	def model_post_init(self, __context: Any) -> None:
		"""Called after model initialization to set up display configuration."""
		self.detect_display_configuration()

	def get_args(self) -> list[str]:
		"""Get the list of all Chrome CLI launch args for this profile (compiled from defaults, user-provided, and system-specific)."""

		if isinstance(self.ignore_default_args, list):
			default_args = set(CHROME_DEFAULT_ARGS) - set(self.ignore_default_args)
		elif self.ignore_default_args is True:
			default_args = []
		elif not self.ignore_default_args:
			default_args = CHROME_DEFAULT_ARGS

		assert self.user_data_dir is not None, 'user_data_dir must be set to a non-default path'

		# Capture args before conversion for logging
		pre_conversion_args = [
			*default_args,
			*self.args,
			f'--user-data-dir={self.user_data_dir}',
			f'--profile-directory={self.profile_directory}',
			*(CHROME_DOCKER_ARGS if (CONFIG.IN_DOCKER or not self.chromium_sandbox) else []),
			*(CHROME_HEADLESS_ARGS if self.headless else []),
			*(CHROME_DISABLE_SECURITY_ARGS if self.disable_security else []),
			*(CHROME_DETERMINISTIC_RENDERING_ARGS if self.deterministic_rendering else []),
			*(
				[f'--window-size={self.window_size["width"]},{self.window_size["height"]}']
				if self.window_size
				else (['--start-maximized'] if not self.headless else [])
			),
			*(
				[f'--window-position={self.window_position["width"]},{self.window_position["height"]}']
				if self.window_position
				else []
			),
			*(self._get_extension_args() if self.enable_default_extensions else []),
		]

		# Proxy flags
		proxy_server = self.proxy.server if self.proxy else None
		proxy_bypass = self.proxy.bypass if self.proxy else None

		if proxy_server:
			pre_conversion_args.append(f'--proxy-server={proxy_server}')
			if proxy_bypass:
				pre_conversion_args.append(f'--proxy-bypass-list={proxy_bypass}')

		# User agent flag
		if self.user_agent:
			pre_conversion_args.append(f'--user-agent={self.user_agent}')

		# Special handling for --disable-features to merge values instead of overwriting
		# This prevents disable_security=True from breaking extensions by ensuring
		# both default features (including extension-related) and security features are preserved
		disable_features_values = []
		non_disable_features_args = []

		# Extract and merge all --disable-features values
		for arg in pre_conversion_args:
			if arg.startswith('--disable-features='):
				features = arg.split('=', 1)[1]
				disable_features_values.extend(features.split(','))
			else:
				non_disable_features_args.append(arg)

		# Remove duplicates while preserving order
		if disable_features_values:
			unique_features = []
			seen = set()
			for feature in disable_features_values:
				feature = feature.strip()
				if feature and feature not in seen:
					unique_features.append(feature)
					seen.add(feature)

			# Add merged disable-features back
			non_disable_features_args.append(f'--disable-features={",".join(unique_features)}')

		# convert to dict and back to dedupe and merge other duplicate args
		final_args_list = BrowserLaunchArgs.args_as_list(BrowserLaunchArgs.args_as_dict(non_disable_features_args))

		return final_args_list

	def _get_extension_args(self) -> list[str]:
		"""Get Chrome args for enabling default extensions (ad blocker and cookie handler)."""
		extension_paths = self._ensure_default_extensions_downloaded()

		args = [
			'--enable-extensions',
			'--disable-extensions-file-access-check',
			'--disable-extensions-http-throttling',
			'--enable-extension-activity-logging',
		]

		if extension_paths:
			args.append(f'--load-extension={",".join(extension_paths)}')

		return args

	def _ensure_default_extensions_downloaded(self) -> list[str]:
		"""
		Ensure default extensions are downloaded and cached locally.
		Returns list of paths to extension directories.
		"""

		# Extension definitions - optimized for automation and content extraction
		# Combines uBlock Origin (ad blocking) + "I still don't care about cookies" (cookie banner handling)
		extensions = [
			{
				'name': 'uBlock Origin',
				'id': 'cjpalhdlnbpafiamejdnhcphjbkeiagm',
				'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=133&acceptformat=crx3&x=id%3Dcjpalhdlnbpafiamejdnhcphjbkeiagm%26uc',
			},
			{
				'name': "I still don't care about cookies",
				'id': 'edibdbjcniadpccecjdfdjjppcpchdlm',
				'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=133&acceptformat=crx3&x=id%3Dedibdbjcniadpccecjdfdjjppcpchdlm%26uc',
			},
			{
				'name': 'ClearURLs',
				'id': 'lckanjgmijmafbedllaakclkaicjfmnk',
				'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=133&acceptformat=crx3&x=id%3Dlckanjgmijmafbedllaakclkaicjfmnk%26uc',
			},
			# {
			# 	'name': 'Captcha Solver: Auto captcha solving service',
			# 	'id': 'pgojnojmmhpofjgdmaebadhbocahppod',
			# 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dpgojnojmmhpofjgdmaebadhbocahppod%26uc',
			# },
			# Consent-O-Matic disabled - using uBlock Origin's cookie lists instead for simplicity
			# {
			# 	'name': 'Consent-O-Matic',
			# 	'id': 'mdjildafknihdffpkfmmpnpoiajfjnjd',
			# 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dmdjildafknihdffpkfmmpnpoiajfjnjd%26uc',
			# },
			# {
			# 	'name': 'Privacy | Protect Your Payments',
			# 	'id': 'hmgpakheknboplhmlicfkkgjipfabmhp',
			# 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dhmgpakheknboplhmlicfkkgjipfabmhp%26uc',
			# },
		]

		# Create extensions cache directory
		cache_dir = CONFIG.BROWSER_USE_EXTENSIONS_DIR
		cache_dir.mkdir(parents=True, exist_ok=True)
		# logger.debug(f'📁 Extensions cache directory: {_log_pretty_path(cache_dir)}')

		extension_paths = []
		loaded_extension_names = []

		for ext in extensions:
			ext_dir = cache_dir / ext['id']
			crx_file = cache_dir / f'{ext["id"]}.crx'

			# Check if extension is already extracted
			if ext_dir.exists() and (ext_dir / 'manifest.json').exists():
				# logger.debug(f'✅ Using cached {ext["name"]} extension from {_log_pretty_path(ext_dir)}')
				extension_paths.append(str(ext_dir))
				loaded_extension_names.append(ext['name'])
				continue

			try:
				# Download extension if not cached
				if not crx_file.exists():
					logger.info(f'📦 Downloading {ext["name"]} extension...')
					self._download_extension(ext['url'], crx_file)
				else:
					logger.debug(f'📦 Found cached {ext["name"]} .crx file')

				# Extract extension
				logger.info(f'📂 Extracting {ext["name"]} extension...')
				self._extract_extension(crx_file, ext_dir)

				extension_paths.append(str(ext_dir))
				loaded_extension_names.append(ext['name'])

			except Exception as e:
				logger.warning(f'⚠️ Failed to setup {ext["name"]} extension: {e}')
				continue

		# Apply minimal patch to cookie extension with configurable whitelist
		for i, path in enumerate(extension_paths):
			if loaded_extension_names[i] == "I still don't care about cookies":
				self._apply_minimal_extension_patch(Path(path), self.cookie_whitelist_domains)

		if extension_paths:
			logger.debug(f'[BrowserProfile] 🧩 Extensions loaded ({len(extension_paths)}): [{", ".join(loaded_extension_names)}]')
		else:
			logger.warning('[BrowserProfile] ⚠️ No default extensions could be loaded')

		return extension_paths

	def _apply_minimal_extension_patch(self, ext_dir: Path, whitelist_domains: list[str]) -> None:
		"""Minimal patch: pre-populate chrome.storage.local with configurable domain whitelist."""
		try:
			bg_path = ext_dir / 'data' / 'background.js'
			if not bg_path.exists():
				return

			with open(bg_path, encoding='utf-8') as f:
				content = f.read()

			# Create the whitelisted domains object for JavaScript with proper indentation
			whitelist_entries = [f'        "{domain}": true' for domain in whitelist_domains]
			whitelist_js = '{\n' + ',\n'.join(whitelist_entries) + '\n      }'

			# Find the initialize() function and inject storage setup before updateSettings()
			# The actual function uses 2-space indentation, not tabs
			old_init = """async function initialize(checkInitialized, magic) {
  if (checkInitialized && initialized) {
    return;
  }
  loadCachedRules();
  await updateSettings();
  await recreateTabList(magic);
  initialized = true;
}"""

			# New function with configurable whitelist initialization
			new_init = f"""// Pre-populate storage with configurable domain whitelist if empty
async function ensureWhitelistStorage() {{
  const result = await chrome.storage.local.get({{ settings: null }});
  if (!result.settings) {{
    const defaultSettings = {{
      statusIndicators: true,
      whitelistedDomains: {whitelist_js}
    }};
    await chrome.storage.local.set({{ settings: defaultSettings }});
  }}
}}

async function initialize(checkInitialized, magic) {{
  if (checkInitialized && initialized) {{
    return;
  }}
  loadCachedRules();
  await ensureWhitelistStorage(); // Add storage initialization
  await updateSettings();
  await recreateTabList(magic);
  initialized = true;
}}"""

			if old_init in content:
				content = content.replace(old_init, new_init)

				with open(bg_path, 'w', encoding='utf-8') as f:
					f.write(content)

				domain_list = ', '.join(whitelist_domains)
				logger.info(f'[BrowserProfile] ✅ Cookie extension: {domain_list} pre-populated in storage')
			else:
				logger.debug('[BrowserProfile] Initialize function not found for patching')

		except Exception as e:
			logger.debug(f'[BrowserProfile] Could not patch extension storage: {e}')

	def _download_extension(self, url: str, output_path: Path) -> None:
		"""Download extension .crx file."""
		import urllib.request

		try:
			with urllib.request.urlopen(url) as response:
				with open(output_path, 'wb') as f:
					f.write(response.read())
		except Exception as e:
			raise Exception(f'Failed to download extension: {e}')

	def _extract_extension(self, crx_path: Path, extract_dir: Path) -> None:
		"""Extract .crx file to directory."""
		import os
		import zipfile

		# Remove existing directory
		if extract_dir.exists():
			import shutil

			shutil.rmtree(extract_dir)

		extract_dir.mkdir(parents=True, exist_ok=True)

		try:
			# CRX files are ZIP files with a header, try to extract as ZIP
			with zipfile.ZipFile(crx_path, 'r') as zip_ref:
				zip_ref.extractall(extract_dir)

			# Verify manifest exists
			if not (extract_dir / 'manifest.json').exists():
				raise Exception('No manifest.json found in extension')

		except zipfile.BadZipFile:
			# CRX files have a header before the ZIP data
			# Skip the CRX header and extract the ZIP part
			with open(crx_path, 'rb') as f:
				# Read CRX header to find ZIP start
				magic = f.read(4)
				if magic != b'Cr24':
					raise Exception('Invalid CRX file format')

				version = int.from_bytes(f.read(4), 'little')
				if version == 2:
					pubkey_len = int.from_bytes(f.read(4), 'little')
					sig_len = int.from_bytes(f.read(4), 'little')
					f.seek(16 + pubkey_len + sig_len)  # Skip to ZIP data
				elif version == 3:
					header_len = int.from_bytes(f.read(4), 'little')
					f.seek(12 + header_len)  # Skip to ZIP data

				# Extract ZIP data
				zip_data = f.read()

			# Write ZIP data to temp file and extract
			import tempfile

			with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
				temp_zip.write(zip_data)
				temp_zip.flush()

				with zipfile.ZipFile(temp_zip.name, 'r') as zip_ref:
					zip_ref.extractall(extract_dir)

				os.unlink(temp_zip.name)

	def detect_display_configuration(self) -> None:
		"""
		Detect the system display size and initialize the display-related config defaults:
		        screen, window_size, window_position, viewport, no_viewport, device_scale_factor
		"""

		display_size = get_display_size()
		has_screen_available = bool(display_size)
		self.screen = self.screen or display_size or ViewportSize(width=1920, height=1080)

		# if no headless preference specified, prefer headful if there is a display available
		if self.headless is None:
			self.headless = not has_screen_available

		# Determine viewport behavior based on mode and user preferences
		user_provided_viewport = self.viewport is not None

		if self.headless:
			# Headless mode: always use viewport for content size control
			self.viewport = self.viewport or self.window_size or self.screen
			self.window_position = None
			self.window_size = None
			self.no_viewport = False
		else:
			# Headful mode: respect user's viewport preference
			self.window_size = self.window_size or self.screen

			if user_provided_viewport:
				# User explicitly set viewport - enable viewport mode
				self.no_viewport = False
			else:
				# Default headful: content fits to window (no viewport)
				self.no_viewport = True if self.no_viewport is None else self.no_viewport

		# Handle special requirements (device_scale_factor forces viewport mode)
		if self.device_scale_factor and self.no_viewport is None:
			self.no_viewport = False

		# Finalize configuration
		if self.no_viewport:
			# No viewport mode: content adapts to window
			self.viewport = None
			self.device_scale_factor = None
			self.screen = None
			assert self.viewport is None
			assert self.no_viewport is True
		else:
			# Viewport mode: ensure viewport is set
			self.viewport = self.viewport or self.screen
			self.device_scale_factor = self.device_scale_factor or 1.0
			assert self.viewport is not None
			assert self.no_viewport is False

		assert not (self.headless and self.no_viewport), 'headless=True and no_viewport=True cannot both be set at the same time'
