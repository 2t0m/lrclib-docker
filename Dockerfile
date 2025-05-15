# Step to build the Docker image
FROM python:3.9-slim

# Install cron
RUN apt-get update && apt-get install -y --no-install-recommends cron && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . /app

# Copy the crontab file and set the appropriate permissions
COPY crontab /etc/cron.d/crontab
RUN chmod 0644 /etc/cron.d/crontab

# Copy the entrypoint script and set the correct permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]