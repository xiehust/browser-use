#!/bin/bash

# Script to run browser-use evaluation with improved system
# Usage: ./run_improved_eval.sh [optional-arguments]

set -e

echo "🚀 Running Browser-Use Evaluation with Improved System"
echo "=================================================="

# Default parameters (can be overridden)
MODEL=${MODEL:-"gpt-4o-mini"}
EVAL_MODEL=${EVAL_MODEL:-"gpt-4o-mini"}
MAX_STEPS=${MAX_STEPS:-25}
PARALLEL_RUNS=${PARALLEL_RUNS:-3}
START_INDEX=${START_INDEX:-0}
END_INDEX=${END_INDEX:-20}
USER_MESSAGE=${USER_MESSAGE:-"Testing improved system with better prompts and timing guidance"}
DEVELOPER_ID=${DEVELOPER_ID:-"cursor-improvements"}

echo "📋 Configuration:"
echo "   Model: $MODEL"
echo "   Eval Model: $EVAL_MODEL"
echo "   Max Steps: $MAX_STEPS"
echo "   Parallel Runs: $PARALLEL_RUNS"
echo "   Tasks: $START_INDEX to $END_INDEX"
echo "   User Message: $USER_MESSAGE"
echo "   Developer ID: $DEVELOPER_ID"
echo ""

# Check if virtual environment exists or create one
if [ ! -d ".venv" ]; then
    echo "🔧 Setting up virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv --python 3.11
        source .venv/bin/activate
        uv sync
    else
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -e .
    fi
else
    echo "🔧 Activating existing virtual environment..."
    source .venv/bin/activate
fi

# Check environment variables
if [ -z "$EVALUATION_TOOL_URL" ] || [ -z "$EVALUATION_TOOL_SECRET_KEY" ]; then
    echo "⚠️  Warning: EVALUATION_TOOL_URL or EVALUATION_TOOL_SECRET_KEY not set"
    echo "    Make sure to set these environment variables before running"
fi

# Get current git info
BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT=$(git rev-parse --short HEAD)

echo "🌳 Running on branch: $BRANCH (commit: $COMMIT)"
echo "💡 This includes the following improvements:"
echo "   - Enhanced timing guidance for form interactions"
echo "   - Better element selection and error handling"
echo "   - Loop detection and prevention"
echo "   - Improved file system usage guidance"
echo "   - More specific action descriptions"
echo ""

# Run the evaluation
echo "🏃 Starting evaluation..."
python eval/service.py \
    --model "$MODEL" \
    --eval-model "$EVAL_MODEL" \
    --max-steps "$MAX_STEPS" \
    --parallel-runs "$PARALLEL_RUNS" \
    --start "$START_INDEX" \
    --end "$END_INDEX" \
    --headless \
    --user-message "$USER_MESSAGE" \
    --developer-id "$DEVELOPER_ID" \
    "$@"

echo ""
echo "✅ Evaluation completed!"
echo "📊 Check the results in your evaluation dashboard"
echo "🔄 To run again with different parameters, set environment variables:"
echo "   export MODEL=gpt-4o"
echo "   export MAX_STEPS=30"
echo "   export END_INDEX=50"
echo "   ./run_improved_eval.sh"