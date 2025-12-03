# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Ensure basic tools are present (curl, jq, wget) for the CA installer and AWS helper
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
	&& apt-get install -y --no-install-recommends ca-certificates curl jq wget \
	&& rm -rf /var/lib/apt/lists/*

# Install AWS Roles Anywhere credential helper (optional but recommended)
RUN wget -q "https://rolesanywhere.amazonaws.com/releases/1.1.1/X86_64/Linux/aws_signing_helper" \
    -O /usr/local/bin/aws_signing_helper \
    && chmod +x /usr/local/bin/aws_signing_helper \
    || echo "Warning: Could not install aws_signing_helper, will use fallback credentials"

# Copy the dependencies file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Copy entrypoint script and make executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY scripts/install_ca.sh /usr/local/bin/install_ca.sh
RUN chmod +x /usr/local/bin/install_ca.sh

# Define environment variables
ENV FLASK_APP=src/be.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONPATH=/app

# Entrypoint will install CA (if available) then exec the CMD
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["flask", "run"]