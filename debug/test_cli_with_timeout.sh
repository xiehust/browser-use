#!/bin/bash

# Test the browser-use CLI with a timeout
echo "Testing browser-use CLI with Amazon search..."

# Run browser-use with a 20-second timeout
timeout 20s browser-use -p 'can you open amazon.com search for "laptop" and open the cheapest listing that isnt an ad in a new tab'

EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo "Command timed out after 20 seconds"
    exit 1
elif [ $EXIT_CODE -eq 0 ]; then
    echo "Command completed successfully"
    exit 0
else
    echo "Command failed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi