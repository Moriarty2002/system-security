# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Ensure basic tools are present (curl, jq, wget) for the CA installer and AWS helper
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
	&& apt-get install -y --no-install-recommends ca-certificates curl jq wget \
	&& rm -rf /var/lib/apt/lists/*

# Install AWS Roles Anywhere credential helper 
ADD https://rolesanywhere.amazonaws.com/releases/1.7.2/X86_64/Linux/Amzn2023/aws_signing_helper /usr/local/bin/aws_signing_helper
RUN chmod +x /usr/local/bin/aws_signing_helper || \
	echo "Warning: Could not make aws_signing_helper executable, will use fallback credentials"

# Copy the dependencies file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Copy entrypoint script and make executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY scripts/install_ca.sh /usr/local/bin/install_ca.sh
RUN chmod +x /usr/local/bin/install_ca.sh

# Create non-root user and set ownership
# Note: CA installation requires write access to system directories
RUN groupadd -r flaskuser && useradd -r -g flaskuser flaskuser && \
    chown -R flaskuser:flaskuser /app /usr/local/bin/entrypoint.sh /usr/local/bin/install_ca.sh && \
    mkdir -p /usr/local/share/ca-certificates && \
    chown -R flaskuser:flaskuser /usr/local/share/ca-certificates /etc/ssl/certs

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables
ENV FLASK_APP=src/be.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONPATH=/app

# Switch to non-root user
USER flaskuser

# Entrypoint will install CA (if available) then exec the CMD
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["flask", "run"]