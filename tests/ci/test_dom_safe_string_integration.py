"""Test integration of DOM tree with SafeString/UnsafeString for secret masking."""

import pytest
from browser_use.agent.message_manager.safe_string import MessagePart, SafeString, UnsafeString
from browser_use.dom.views import DOMElementNode, DOMTextNode


def test_dom_tree_uses_safe_string_for_indices():
	"""Test that DOM tree formatting uses SafeString for element indices."""
	# Create a simple DOM tree
	root = DOMElementNode(
		tag_name='div',
		xpath='//div',
		attributes={},
		children=[],
		highlight_index=None,
		is_visible=True,
		is_top_element=True,
		parent=None,
		is_new=False
	)
	
	# Add child with index 26 (which could be confused with year '26')
	child1 = DOMElementNode(
		tag_name='button',
		xpath='//div/button',
		attributes={'type': 'submit'},
		children=[],
		highlight_index=26,
		is_visible=True,
		is_top_element=False,
		parent=root,
		is_new=False
	)
	# Add text to button
	text1 = DOMTextNode(
		text='Submit',
		is_visible=True,
		parent=child1
	)
	child1.children = [text1]
	
	# Add another child with index 27
	child2 = DOMElementNode(
		tag_name='input',
		xpath='//div/input',
		attributes={'type': 'text', 'name': 'expiry'},
		children=[],
		highlight_index=27,
		is_visible=True,
		is_top_element=False,
		parent=root,
		is_new=False
	)
	
	root.children = [child1, child2]
	
	# Test the new MessagePart version
	if hasattr(root, 'clickable_elements_to_message_part'):
		message_part = root.clickable_elements_to_message_part()
		
		# Apply secret masking
		sensitive_values = {
			'card_expiry_last2': '26',  # This should NOT mask [26]
		}
		
		masked_result = message_part.apply_secret_masking(sensitive_values)
		
		# Check that indices are preserved
		assert '[26]<button' in masked_result, "DOM index [26] should not be masked"
		assert '[27]<input' in masked_result, "DOM index [27] should not be masked"
		
		# Check that indices are not replaced with secrets
		assert '[<secret>' not in masked_result, "DOM indices should never be masked"
	
	# Also test the legacy string version still works
	dom_string = root.clickable_elements_to_string()
	assert '[26]<button' in dom_string
	assert '[27]<input' in dom_string


def test_dom_tree_masks_attribute_values():
	"""Test that DOM tree attribute values are properly masked."""
	# Create a DOM tree with attributes that contain sensitive data
	root = DOMElementNode(
		tag_name='form',
		xpath='//form',
		attributes={},
		children=[],
		highlight_index=None,
		is_visible=True,
		is_top_element=True,
		parent=None,
		is_new=False
	)
	
	# Add input with value that should be masked
	child = DOMElementNode(
		tag_name='input',
		xpath='//form/input',
		attributes={
			'type': 'text',
			'value': '1234',  # This should be masked if it's sensitive
			'placeholder': 'Last 4 digits'
		},
		children=[],
		highlight_index=1,
		is_visible=True,
		is_top_element=False,
		parent=root,
		is_new=False
	)
	
	root.children = [child]
	
	# Test the new MessagePart version
	if hasattr(root, 'clickable_elements_to_message_part'):
		message_part = root.clickable_elements_to_message_part(include_attributes=['type', 'value', 'placeholder'])
		
		# Apply secret masking
		sensitive_values = {
			'card_last4': '1234',
		}
		
		masked_result = message_part.apply_secret_masking(sensitive_values)
		
		# Check that the index is preserved
		assert '[1]<input' in masked_result, "DOM index [1] should not be masked"
		
		# Check that the attribute value is masked
		assert 'value=<secret>card_last4</secret>' in masked_result, "Attribute value should be masked"
		
		# Check that placeholder is not masked (it doesn't contain the sensitive value)
		assert 'placeholder=Last 4 digits' in masked_result, "Placeholder should not be masked"