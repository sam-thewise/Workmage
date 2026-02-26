# Agent sandbox base image - Python 3.11, LiteLLM, DSPy, MCP client
FROM python:3.11-slim

WORKDIR /sandbox

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    litellm>=1.30.0 \
    dspy-ai>=2.4.0 \
    mcp>=1.0.0

# Default entrypoint: run agent with manifest and input
COPY run_agent.py mcp_client.py /sandbox/
ENV PYTHONPATH=/sandbox

# Resource limits when run (configurable in docker run)
# CPU: --cpus=1, Memory: --memory=512m, Timeout: handled by orchestration
ENTRYPOINT ["python", "/sandbox/run_agent.py"]
