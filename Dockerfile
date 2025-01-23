# Step to build the Docker image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy necessary files into the image
COPY . /app
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install cron
RUN apt-get update && apt-get install -y cron

# Copy the crontab file and set the appropriate permissions
COPY crontab /etc/cron.d/crontab
RUN chmod 0644 /etc/cron.d/crontab

# Copy the entrypoint script and set the correct permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
