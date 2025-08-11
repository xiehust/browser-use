	async def cdp_client_for_frame(self, frame_id: str) -> Any:
		"""Get a CDP client attached to the target containing the specified frame.

		Builds a unified frame hierarchy from all targets to find the correct target
		for any frame, including OOPIFs (Out-of-Process iframes).

		Args:
			frame_id: The frame ID to search for

		Returns:
			Tuple of (cdp_client, session_id, target_id) for the target containing the frame

		Raises:
			ValueError: If the frame is not found in any target
		"""
		# Build unified frame hierarchy from all targets
		all_frames = {}  # frame_id -> FrameInfo dict
		target_sessions = {}  # target_id -> session_id (keep sessions alive during collection)
		
		# Get all targets
		targets = await self.cdp_client.send.Target.getTargets()
		all_targets = targets.get('targetInfos', [])
		
		# First pass: collect frame trees from ALL targets
		for target in all_targets:
			target_id = target.get('targetId')
			
			if not target_id:
				continue
			
			# Attach to target
			session = await self.cdp_client.send.Target.attachToTarget(
				params={'targetId': target_id, 'flatten': True}
			)
			session_id = session['sessionId']
			target_sessions[target_id] = session_id
			
			try:
				# Set auto-attach to get related targets
				await self.cdp_client.send.Target.setAutoAttach(
					params={
						'autoAttach': True,
						'waitForDebuggerOnStart': False,
						'flatten': True
					},
					session_id=session_id
				)
				
				# Try to get frame tree (not all target types support this)
				try:
					await self.cdp_client.send.Page.enable(session_id=session_id)
					frame_tree_result = await self.cdp_client.send.Page.getFrameTree(session_id=session_id)
					
					# Process the frame tree recursively
					def process_frame_tree(node, parent_frame_id=None):
						"""Recursively process frame tree and add to all_frames."""
						frame = node.get('frame', {})
						current_frame_id = frame.get('id')
						
						if current_frame_id:
							# Create frame info with all CDP response data plus our additions
							frame_info = {
								**frame,  # Include all original frame data
								'frameTargetId': target_id,  # Target that can access this frame
								'parentFrameId': parent_frame_id,  # Parent frame ID if any
								'childFrameIds': [],  # Will be populated below
								'isCrossOrigin': False,  # Will be determined based on context
							}
							
							# Check if frame is cross-origin based on crossOriginIsolatedContextType
							cross_origin_type = frame.get('crossOriginIsolatedContextType')
							if cross_origin_type and cross_origin_type != 'NotIsolated':
								frame_info['isCrossOrigin'] = True
							
							# For iframe targets, the frame itself is likely cross-origin
							if target.get('type') == 'iframe':
								frame_info['isCrossOrigin'] = True
							
							# Add child frame IDs (note: OOPIFs won't appear here)
							child_frames = node.get('childFrames', [])
							for child in child_frames:
								child_frame = child.get('frame', {})
								child_frame_id = child_frame.get('id')
								if child_frame_id:
									frame_info['childFrameIds'].append(child_frame_id)
							
							# Store or merge frame info
							if current_frame_id in all_frames:
								# Frame already seen from another target, merge info
								existing = all_frames[current_frame_id]
								# If this is an iframe target, it has direct access to the frame
								if target.get('type') == 'iframe':
									existing['frameTargetId'] = target_id
									existing['isCrossOrigin'] = True
							else:
								all_frames[current_frame_id] = frame_info
							
							# Process child frames recursively
							for child in child_frames:
								process_frame_tree(child, current_frame_id)
					
					# Process the entire frame tree
					process_frame_tree(frame_tree_result.get('frameTree', {}))
					
				except Exception:
					# Target doesn't support Page domain or has no frames
					pass
					
			except Exception:
				# Error processing this target
				pass
		
		# Second pass: populate backend node IDs and parent target IDs
		for frame_id_iter, frame_info in all_frames.items():
			parent_frame_id = frame_info.get('parentFrameId')
			
			if parent_frame_id and parent_frame_id in all_frames:
				parent_frame_info = all_frames[parent_frame_id]
				parent_target_id = parent_frame_info.get('frameTargetId')
				
				# Store parent target ID
				frame_info['parentTargetId'] = parent_target_id
				
				# Try to get backend node ID from parent context
				if parent_target_id in target_sessions:
					parent_session_id = target_sessions[parent_target_id]
					try:
						# Enable DOM domain
						await self.cdp_client.send.DOM.enable(session_id=parent_session_id)
						
						# Get frame owner info to find backend node ID
						frame_owner = await self.cdp_client.send.DOM.getFrameOwner(
							params={'frameId': frame_id_iter},
							session_id=parent_session_id
						)
						
						if frame_owner:
							frame_info['backendNodeId'] = frame_owner.get('backendNodeId')
							frame_info['nodeId'] = frame_owner.get('nodeId')
							
					except Exception:
						# Frame owner not available (likely cross-origin)
						pass
		
		# Find the requested frame and return appropriate client
		if frame_id in all_frames:
			frame_info = all_frames[frame_id]
			target_id = frame_info.get('frameTargetId')
			
			if target_id in target_sessions:
				# Use existing session
				session_id = target_sessions[target_id]
				
				# Clean up other sessions before returning
				for tid, sid in target_sessions.items():
					if tid != target_id:
						try:
							await self.cdp_client.send.Target.detachFromTarget(
								params={'sessionId': sid}
							)
						except Exception:
							pass
				
				# Return the client with session attached (caller must detach)
				return self.cdp_client, session_id, target_id
		
		# Clean up all sessions before raising error
		for target_id, session_id in target_sessions.items():
			try:
				await self.cdp_client.send.Target.detachFromTarget(
					params={'sessionId': session_id}
				)
			except Exception:
				pass
		
		# Frame not found
		raise ValueError(f"Frame with ID '{frame_id}' not found in any target")