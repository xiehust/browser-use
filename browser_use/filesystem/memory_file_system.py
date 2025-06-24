# @file purpose: Defines MemoryFileSystem - an in-memory, serializable filesystem that can create temp files on demand

"""
In-memory FileSystem Implementation

This module provides an in-memory filesystem that:
1. Stores all file content in memory (no disk I/O during operation)
2. Is fully serializable with Pydantic for AgentState persistence
3. Can materialize files to temporary directories on demand for attachments
4. Maintains the same interface as the original FileSystem for drop-in replacement
"""

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

INVALID_FILENAME_ERROR_MESSAGE = 'Error: Invalid filename format. Must be alphanumeric with .txt or .md extension.'


class MemoryFileSystem(BaseModel):
    """
    In-memory filesystem that stores file contents in a dictionary.
    
    This filesystem is:
    - Fully serializable for AgentState persistence
    - Memory-only during operation (no disk I/O)
    - Capable of creating temporary files on demand for attachments
    """
    
    # Store file contents in memory
    files: Dict[str, str] = Field(default_factory=dict, description="In-memory file storage")
    extracted_content_count: int = Field(default=0, description="Counter for extracted content files")
    
    # Temporary directory path (not serialized, created on demand)
    _temp_dir: Optional[Path] = PrivateAttr(default=None)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Initialize default files
        if 'results.md' not in self.files:
            self.files['results.md'] = ''
        if 'todo.md' not in self.files:
            self.files['todo.md'] = ''
    
    def _is_valid_filename(self, file_name: str) -> bool:
        """Check if filename matches the required pattern: name.extension"""
        pattern = r'^[a-zA-Z0-9_\-]+\.(txt|md)$'
        return bool(re.match(pattern, file_name))
    
    async def save_extracted_content(self, content: str) -> str:
        """Save extracted content to a numbered file"""
        extracted_content_file_name = f'extracted_content_{self.extracted_content_count}.md'
        result = await self.write_file(extracted_content_file_name, content)
        self.extracted_content_count += 1
        return result
    
    def display_file(self, file_name: str) -> str | None:
        """Display file content if it exists and is valid"""
        if not self._is_valid_filename(file_name):
            return None
        
        if file_name not in self.files:
            return None
        
        return self.files[file_name]
    
    async def read_file(self, file_name: str) -> str:
        """Read file content from memory"""
        if not self._is_valid_filename(file_name):
            return INVALID_FILENAME_ERROR_MESSAGE
        
        if file_name not in self.files:
            return f"File '{file_name}' not found."
        
        try:
            content = self.files[file_name]
            return f'Read from file {file_name}.\n<content>\n{content}\n</content>'
        except Exception:
            return f"Error: Could not read file '{file_name}'."
    
    async def write_file(self, file_name: str, content: str) -> str:
        """Write file content to memory"""
        if not self._is_valid_filename(file_name):
            return INVALID_FILENAME_ERROR_MESSAGE
        
        try:
            self.files[file_name] = content
            return f'Data written to {file_name} successfully.'
        except Exception:
            return f"Error: Could not write to file '{file_name}'."
    
    async def append_file(self, file_name: str, content: str) -> str:
        """Append content to file in memory"""
        if not self._is_valid_filename(file_name):
            return INVALID_FILENAME_ERROR_MESSAGE
        
        if file_name not in self.files:
            return f"File '{file_name}' not found."
        
        try:
            self.files[file_name] += content
            return f'Data appended to {file_name} successfully.'
        except Exception as e:
            return f"Error: Could not append to file '{file_name}'. {str(e)}"
    
    def describe(self) -> str:
        """List all files with their content information"""
        DISPLAY_CHARS = 400  # Total characters to display (split between start and end)
        description = ''
        
        for file_name in self.files:
            # Skip todo.md in description
            if file_name == 'todo.md':
                continue
            
            content = self.files[file_name]
            
            # Handle empty files
            if not content:
                description += f'<file>\n{file_name} - [empty file]\n</file>\n\n'
                continue
            
            lines = content.splitlines()
            line_count = len(lines)
            
            # For small files, display the entire content
            whole_file_description = f'<file>\n{file_name} - {line_count} lines\n<content>\n{content}\n</content>\n</file>\n'
            if len(content) < int(1.5 * DISPLAY_CHARS):
                description += whole_file_description
                continue
            
            # For larger files, display start and end previews
            half_display_chars = DISPLAY_CHARS // 2
            
            # Get start preview
            start_preview = ''
            start_line_count = 0
            chars_count = 0
            for line in lines:
                if chars_count + len(line) + 1 > half_display_chars:
                    break
                start_preview += line + '\n'
                chars_count += len(line) + 1
                start_line_count += 1
            
            # Get end preview
            end_preview = ''
            end_line_count = 0
            chars_count = 0
            for line in reversed(lines):
                if chars_count + len(line) + 1 > half_display_chars:
                    break
                end_preview = line + '\n' + end_preview
                chars_count += len(line) + 1
                end_line_count += 1
            
            # Calculate lines in between
            middle_line_count = line_count - start_line_count - end_line_count
            if middle_line_count <= 0:
                # display the entire file
                description += whole_file_description
                continue
            
            start_preview = start_preview.strip('\n').rstrip()
            end_preview = end_preview.strip('\n').rstrip()
            
            # Format output
            description += f'<file>\n{file_name} - {line_count} lines\n<content>\n{start_preview}\n'
            description += f'... {middle_line_count} more lines ...\n'
            description += f'{end_preview}\n'
            description += '</content>\n</file>\n'
        
        return description.strip('\n')
    
    def get_todo_contents(self) -> str:
        """Get todo.md file contents"""
        return self.files.get('todo.md', '')
    
    def get_dir(self) -> Path:
        """Get or create temporary directory for file materialization"""
        if self._temp_dir is None or not self._temp_dir.exists():
            self._temp_dir = Path(tempfile.mkdtemp(prefix='browser_use_memory_fs_'))
        return self._temp_dir
    
    def materialize_file(self, file_name: str) -> Optional[Path]:
        """
        Create a temporary file on disk with the content from memory.
        Returns the path to the temporary file, or None if file doesn't exist.
        Used for attachments that need to be shared as actual files.
        """
        if not self._is_valid_filename(file_name) or file_name not in self.files:
            return None
        
        temp_dir = self.get_dir()
        file_path = temp_dir / file_name
        
        try:
            file_path.write_text(self.files[file_name])
            return file_path
        except Exception:
            return None
    
    def materialize_files(self, file_names: list[str]) -> list[str]:
        """
        Materialize multiple files and return their paths.
        Used for attachment handling in the done action.
        """
        materialized_paths = []
        for file_name in file_names:
            if file_name == 'todo.md':
                continue  # Skip todo.md as per original logic
            
            file_path = self.materialize_file(file_name)
            if file_path:
                materialized_paths.append(str(file_path))
        
        return materialized_paths
    
    def cleanup_temp_files(self):
        """Clean up temporary directory and all materialized files"""
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
            except Exception:
                pass  # Ignore cleanup errors
    
    def __del__(self):
        """Cleanup temporary files when the object is destroyed"""
        try:
            self.cleanup_temp_files()
        except Exception:
            pass  # Ignore cleanup errors during destruction

    model_config = ConfigDict(arbitrary_types_allowed=True)