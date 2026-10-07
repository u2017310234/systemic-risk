FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY risk_mcp ./risk_mcp
COPY loc ./loc
RUN pip install --no-cache-dir .
COPY data ./data
ENV MCP_HOST=0.0.0.0 MCP_PORT=8000
EXPOSE 8000
CMD ["uvicorn", "risk_mcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
