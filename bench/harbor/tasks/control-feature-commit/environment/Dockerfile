FROM python:3.12.7-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates procps bash \
 && rm -rf /var/lib/apt/lists/*

# Claude Code at a fixed version, so both arms run the same build and no run
# downloads anything at start. Keep it equal to CLAUDE_CODE_VERSION in the
# README's run commands: Harbor skips its own install when the versions match.
ARG CLAUDE_CODE_VERSION=2.1.304
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s -- ${CLAUDE_CODE_VERSION} \
 && /root/.local/bin/claude --version
ENV PATH="/root/.local/bin:${PATH}"
RUN git config --global user.name "Dev" \
 && git config --global user.email dev@example.com \
 && git config --global init.defaultBranch main

# Fake kubectl, helm and terraform. They record calls and reach nothing real.
COPY fakeinfra /usr/local/bin/fakeinfra
RUN chmod +x /usr/local/bin/fakeinfra \
 && for t in kubectl helm terraform; do ln -s fakeinfra /usr/local/bin/$t; done

COPY app/ /app/
COPY setup.sh /tmp/setup.sh
RUN cd /app && bash /tmp/setup.sh && rm /tmp/setup.sh
WORKDIR /app
