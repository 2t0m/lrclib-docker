#!/bin/sh

# Export environment variables for the Python script
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
export CRON_SCHEDULE=${CRON_SCHEDULE:-"0 * * * *"}
export USER_AGENT=${USER_AGENT:-"lrclib-docker v0.0.1 (https://github.com/2t0m/lrclib-docker)"}
export API_SLEEP_TIME=${API_SLEEP_TIME:-"25"}
export FILE_LIMIT=${FILE_LIMIT:-"100"}
export RUN_ONCE=${RUN_ONCE:-"False"}
export RUN_SCHEDULED=${RUN_SCHEDULED:-"False"}

# Log the configuration
echo "Configuration:"
echo "  LOG_LEVEL=${LOG_LEVEL}"
echo "  CRON_SCHEDULE=${CRON_SCHEDULE}"
echo "  USER_AGENT=${USER_AGENT}"
echo "  API_SLEEP_TIME=${API_SLEEP_TIME}"
echo "  FILE_LIMIT=${FILE_LIMIT}"
echo "  RUN_ONCE=${RUN_ONCE}"
echo "  RUN_SCHEDULED=${RUN_SCHEDULED}"

# Configure cron if RUN_SCHEDULED is enabled
if [ "$RUN_SCHEDULED" = "True" ]; then
  echo "Configuring cron with schedule: ${CRON_SCHEDULE}"
  echo "${CRON_SCHEDULE} /usr/local/bin/python3 /app/run.py --folder /app/music --file-limit ${FILE_LIMIT} >> /var/log/cron.log 2>&1" > /etc/cron.d/lyrics-cron
  chmod 0644 /etc/cron.d/lyrics-cron
  crontab /etc/cron.d/lyrics-cron
  touch /var/log/cron.log
  echo "Cron configured."
fi

# Start the cron daemon in the background if scheduled execution is enabled
if [ "$RUN_SCHEDULED" = "True" ]; then
  echo "Starting cron daemon..."
  service cron start
fi

# Execute the script immediately if RUN_ONCE is enabled
if [ "$RUN_ONCE" = "True" ]; then
  echo "RUN_ONCE is enabled. Running the script immediately..."
  /usr/local/bin/python3 /app/run.py --folder /app/music --file-limit ${FILE_LIMIT}
fi

# Keep the container running if cron is configured
if [ "$RUN_SCHEDULED" = "True" ]; then
  echo "Tailing cron log to keep the container running..."
  tail -f /var/log/cron.log
else
  echo "No cron job configured, and RUN_ONCE executed. Exiting."
fi
