FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nmap \
    arp-scan \
    net-tools \
    iputils-ping \
    iproute2 \
    libpcap-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /agent

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Agent needs NET_ADMIN + NET_RAW for raw socket access
# These are set in docker-compose.yml

CMD ["python", "-u", "main.py"]
