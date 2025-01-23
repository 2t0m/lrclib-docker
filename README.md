# lrclib-docker
Music Lyrics Synchronizer - Dockerized

### Environment Variables

The application supports the following environment variables for customization:

| Variable Name   | Default Value                        | Description                                                                 |
|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `USER_AGENT`   | `lrclib-docker v0.0.1 (https://github.com/2t0m/lrclib-docker)` | A custom `User-Agent` header for API requests. It should include your application's name, version, and homepage link. |
| `RUN_ONCE`      | `False`                             | If set to `True`, the script runs once at startup.                         |
| `RUN_SCHEDULED` | `False`                             | If set to `True`, the script runs on a schedule configured via `CRON_SCHEDULE`. |
| `CRON_SCHEDULE` | `0 * * * *`                         | The cron schedule (in [CRON syntax](https://crontab.guru/)) for execution. |
| `API_SLEEP_TIME`| `25`                                | The delay (in seconds) between API calls to avoid rate limiting.           |
| `MP3_LIMIT`     | `100`                               | The maximum number of MP3 files to process per execution.                  |
| `LOG_LEVEL`     | `INFO`                              | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                       |
| `USER_AGENT`    | `lrclib-docker v0.0.1`              | The User-Agent string for API requests.                                    |

### Notes on `USER_AGENT`
Including a meaningful `User-Agent` is encouraged when interacting with the LrcLib API. For example:  
`lrclib-docker v0.0.1 (https://github.com/2t0m/lrclib-docker)`.  
This helps LrcLib identify your application and provide better support or analytics. While it is not mandatory, it's a recommended practice when developing applications that interact with the API.

### Example YAML File

```yaml
services:
  lrclib-docker:
    image: 2t0m/lrclib-docker:latest
    container_name: lrclib-docker
    volumes:
      - /path/to/your/music:/app/music
    environment:
      USER_AGENT: "lrclib-docker v0.0.1 (https://github.com/2t0m/lrclib-docker)"
      RUN_ONCE: "True"            # Run the script once
      RUN_SCHEDULED: "False"      # Disable scheduled execution
      CRON_SCHEDULE: "0 * * * *"  # Schedule (e.g., every hour)
      API_SLEEP_TIME: "20"        # Time between API calls
      MP3_LIMIT: "100"            # Limit number of MP3 files processed
      LOG_LEVEL: "DEBUG"          # Debugging logs
    restart: always
```

## Special Thanks
Special thanks to [LrcLib](https://github.com/tranxuanthang/lrclib) for powering the lyrics synchronization.
