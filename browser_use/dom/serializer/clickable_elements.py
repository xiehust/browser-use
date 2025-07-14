from browser_use.dom.views import EnhancedDOMTreeNode, NodeType


class ClickableElementDetector:
	@staticmethod
	def is_interactive(node: EnhancedDOMTreeNode) -> bool:
		"""Check if this node is clickable/interactive using enhanced scoring."""

		# Skip non-element nodes
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		# remove html and body nodes
		if node.tag_name in {'html', 'body'}:
			return False

		# Fast path: intrinsically interactive HTML elements (most common case)
		# Note: iframe is removed - only iframe content should be interactive, not the iframe container
		interactive_tags = {
			'button',
			'input',
			'select',
			'textarea',
			'a',
			'label',
			'details',
			'summary',
			'option',
			'optgroup',
		}
		if node.tag_name in interactive_tags:
			return True

		# Fast path: elements with interactive attributes (check common ones first)
		if node.attributes:
			# Check for event handlers or interactive attributes (most common indicators)
			if any(attr in node.attributes for attr in ('onclick', 'tabindex', 'onmousedown', 'onmouseup', 'onkeydown', 'onkeyup')):
				return True

			# Check for interactive ARIA roles
			role = node.attributes.get('role')
			if role in {'button', 'link', 'menuitem', 'option', 'radio', 'checkbox', 'tab', 'textbox', 'combobox', 'slider', 'spinbutton'}:
				return True

		# Check cursor style for pointer (indicates clickability)
		if (node.snapshot_node and 
			node.snapshot_node.cursor_style == 'pointer'):
			return True

		# Accessibility tree role check (faster than property iteration)
		if (node.ax_node and 
			node.ax_node.role in {'button', 'link', 'menuitem', 'option', 'radio', 'checkbox', 'tab', 'textbox', 'combobox', 'slider', 'spinbutton', 'listbox'}):
			return True

		# Enhanced accessibility property checks - only when needed
		if node.ax_node and node.ax_node.properties:
			# Pre-define sets for faster lookup
			interactive_props = {'focusable', 'editable', 'settable'}
			state_props = {'checked', 'expanded', 'pressed', 'selected'}
			form_props = {'required', 'autocomplete'}
			
			for prop in node.ax_node.properties:
				try:
					prop_name = prop.name
					prop_value = prop.value
					
					# Early exit conditions (most likely to short-circuit)
					if prop_name == 'disabled' and prop_value:
						return False
					if prop_name == 'hidden' and prop_value:
						return False

					# Interactive indicators (check in order of likelihood)
					if prop_name in interactive_props and prop_value:
						return True
					if prop_name in state_props:  # presence indicates interactive widget
						return True
					if prop_name in form_props and prop_value:
						return True
					if prop_name == 'keyshortcuts' and prop_value:
						return True
						
				except (AttributeError, ValueError):
					# Skip properties we can't process
					continue

		return False
