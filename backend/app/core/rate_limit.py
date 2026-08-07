from fastapi import Request, HTTPException
import time
from collections import defaultdict

# Simple in-memory sliding window cache: client_ip -> list of timestamps
rate_limit_records = defaultdict(list)


def rate_limiter(limit: int, window: int):
    """
    FastAPI dependency factory for simple in-memory sliding window rate limiting.
    limit: Max number of requests allowed within the window.
    window: Time window in seconds.
    """
    def dependency(request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Filter out records outside the sliding window
        timestamps = rate_limit_records[client_ip]
        timestamps = [t for t in timestamps if now - t < window]
        rate_limit_records[client_ip] = timestamps

        if len(timestamps) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )

        rate_limit_records[client_ip].append(now)

    return dependency
