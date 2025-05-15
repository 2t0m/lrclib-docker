# lrclib-docker
Music Lyrics Synchronizer - Dockerized

### Environment Variables

The application supports the following environment variables for customization:

| Variable Name   | Default Value                        | Description                                                                 |
|-----------------|--------------------------------------|-----------------------------------------------------------------------------|
| `RUN_ONCE`      | `False`                             | If set to `True`, the script runs once at startup.                         |
| `RUN_SCHEDULED` | `False`                             | If set to `True`, the script runs on a schedule configured via `CRON_SCHEDULE`. |
| `CRON_SCHEDULE` | `0 * * * *`                         | The cron schedule (in [CRON syntax](https://crontab.guru/)) for execution. |
| `API_SLEEP_TIME`| `25`                                | The delay (in seconds) between API calls to avoid rate limiting.           |
| `FILE_LIMIT`    | `100`                              | The maximum number of audio files to process per execution.                  |
| `MAX_PARALLEL`  | `1`                                 | The maximum number of parallel threads or processes used for processing files. Increasing this value can speed up execution but may consume more system resources. |
| `LOG_LEVEL`     | `INFO`                              | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                       |
| `USER_AGENT`    | `lrclib-docker v0.0.1`              | The User-Agent string for API requests.                                    |

### Notes on `USER_AGENT`
Including a meaningful `User-Agent` is encouraged when interacting with the LrcLib API. For example:  
`lrclib-docker`.  
This helps LrcLib identify your application and provide better support or analytics. While it is not mandatory, it's a recommended practice when developing applications that interact with the API.

## Special Thanks
Special thanks to [LrcLib](https://github.com/tranxuanthang/lrclib) for powering the lyrics synchronization.
