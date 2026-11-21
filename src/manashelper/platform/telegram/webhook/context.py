from contextvars import ContextVar

# The polling error observer logs errors. Webhooks must also propagate them so
# Telegram retries instead of acknowledging a rolled-back handler as successful.
webhook_processing: ContextVar[bool] = ContextVar("webhook_processing", default=False)
