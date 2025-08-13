from browser_use.dom.views import EnhancedDOMTreeNode, NodeType


class ClickableElementDetector:
	@staticmethod
	def is_interactive(node: EnhancedDOMTreeNode) -> bool:
		"""Check if this node is clickable/interactive using enhanced scoring."""

		# Skip non-element nodes
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		# # if ax ignored skip
		# if node.ax_node and node.ax_node.ignored:
		# 	return False

		# remove html and body nodes
		if node.tag_name in {'html', 'body'}:
			return False

		# RELAXED SIZE CHECK: Allow all elements including size 0 (they might be interactive overlays, etc.)
		# Note: Size 0 elements can still be interactive (e.g., invisible clickable overlays)
		# Visibility is determined separately by CSS styles, not just bounding box size

		# Enhanced accessibility property checks with comprehensive coverage
		if node.ax_node and node.ax_node.properties:
			if node.ax_node.ignored:  # all ignored nodes are not interactive
				return False

			for prop in node.ax_node.properties:
				try:
					# EXCLUSION RULES: These properties prevent interactivity
					if prop.name == 'disabled' and prop.value:
						return False
					if prop.name == 'hidden' and prop.value:
						return False
					if prop.name == 'hiddenRoot' and prop.value:
						return False
					if prop.name == 'readonly' and prop.value:
						return False
					if prop.name == 'busy' and prop.value:
						return False

					# TIER 1: Always interactive (strong indicators)
					# Direct interaction capabilities
					if prop.name in ['focusable', 'editable', 'settable'] and prop.value:
						return True

					# Widget states (only interactive elements have these)
					if prop.name in ['checked', 'expanded', 'pressed', 'selected']:
						# These properties only exist on interactive elements
						return True

					# Interactive widget attributes
					if prop.name == 'hasPopup' and prop.value:
						return True
					if prop.name == 'multiselectable' and prop.value:
						return True

					# TIER 2: Contextually interactive (moderate indicators)
					# Form/input related
					if prop.name in ['required', 'autocomplete'] and prop.value:
						return True
					if prop.name in ['valuemin', 'valuemax', 'valuetext'] and prop.value:
						return True

					# Elements with keyboard shortcuts are interactive
					if prop.name == 'keyshortcuts' and prop.value:
						return True

				except (AttributeError, ValueError):
					# Skip properties we can't process
					continue

		# Enhanced tag check: Include truly interactive elements
		# interactive_tags = {
		# 	'button',
		# 	'input',
		# 	'select',
		# 	'textarea',
		# 	'a',
		# 	'label',
		# 	'details',
		# 	'summary',
		# 	'option',
		# 	'optgroup',
		# }
		# if node.tag_name in interactive_tags:
		# 	return True

		# Check for interactive attributes
		# if node.attributes:
		# 	# Event handlers or interactive attributes
		# 	interactive_attributes = {
		# 		'onclick',
		# 		'onmousedown',
		# 		'onmouseup',
		# 		'onkeydown',
		# 		'onkeyup',
		# 		'tabindex',
		# 		'contenteditable',
		# 	}
		# 	if any(attr in node.attributes for attr in interactive_attributes):
		# 		return True

		# Accessibility tree roles (fallback check)
		# if node.ax_node and node.ax_node.role:
		# 	interactive_ax_roles = {
		# 		'button',
		# 		'link',
		# 		'menuitem',
		# 		'option',
		# 		'radio',
		# 		'checkbox',
		# 		'tab',
		# 		'textbox',
		# 		'combobox',
		# 		'slider',
		# 		'spinbutton',
		# 		'listbox',
		# 		'search',
		# 		'searchbox',
		# 		'switch',
		# 	}
		# 	if node.ax_node.role in interactive_ax_roles:
		# 		return True

		# Enhanced cursor style detection
		# if node.snapshot_node and node.snapshot_node.cursor_style:
		# 	interactive_cursors = {
		# 		'pointer',
		# 		'move',
		# 		'text',
		# 		'grab',
		# 		'grabbing',
		# 		'cell',
		# 		'copy',
		# 		'alias',
		# 		'all-scroll',
		# 		'col-resize',
		# 		'context-menu',
		# 		'crosshair',
		# 		'help',
		# 		'zoom-in',
		# 		'zoom-out',
		# 	}
		# 	if node.snapshot_node.cursor_style in interactive_cursors:
		# 		return True

		return False
