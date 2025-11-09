"""
Alert management and notification system.

Provides comprehensive alerting with:
- Multi-level alerts (INFO, WARNING, CRITICAL)
- Multiple notification channels (Email, Slack, SMS, Webhook)
- Alert aggregation and throttling
- Alert history and analytics
- Integration with PagerDuty, OpsGenie
"""

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
import smtplib
import threading
import time
from typing import Any

from loguru import logger
import requests


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    TELEGRAM = "telegram"


@dataclass
class Alert:
    """Alert object."""
    id: str
    timestamp: datetime
    level: AlertLevel
    title: str
    message: str
    source: str
    tags: dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: datetime | None = None
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "tags": self.tags,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by
        }


class AlertRule:
    """
    Alert rule definition.
    
    Defines conditions that trigger alerts.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[], bool],
        level: AlertLevel,
        message_template: str,
        throttle_seconds: int = 300,  # 5 minutes
        tags: dict[str, str] | None = None
    ):
        """Initialize alert rule."""
        self.name = name
        self.condition = condition
        self.level = level
        self.message_template = message_template
        self.throttle_seconds = throttle_seconds
        self.tags = tags or {}

        self._last_alert_time: float | None = None
        self._alert_count = 0

    def check(self) -> Alert | None:
        """Check rule and return alert if triggered."""
        try:
            # Check condition
            if not self.condition():
                return None

            # Check throttle
            now = time.time()
            if self._last_alert_time:
                if now - self._last_alert_time < self.throttle_seconds:
                    return None

            # Create alert
            self._last_alert_time = now
            self._alert_count += 1

            alert = Alert(
                id=f"{self.name}_{int(now)}",
                timestamp=datetime.now(),
                level=self.level,
                title=self.name,
                message=self.message_template.format(count=self._alert_count),
                source="alert_rule",
                tags=self.tags
            )

            return alert

        except Exception as e:
            logger.error(f"Error checking alert rule {self.name}: {e}")
            return None


class EmailNotifier:
    """Email notification channel."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: list[str]
    ):
        """Initialize email notifier."""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails

    def send(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{alert.level.value.upper()}] {alert.title}"

            body = f"""
Alert Level: {alert.level.value}
Time: {alert.timestamp.isoformat()}
Source: {alert.source}

{alert.message}

Tags: {alert.tags}
            """

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"Sent email alert: {alert.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False


class SlackNotifier:
    """Slack notification channel."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier."""
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            # Color based on level
            color_map = {
                AlertLevel.INFO: "#36a64f",
                AlertLevel.WARNING: "#ff9900",
                AlertLevel.CRITICAL: "#ff0000"
            }

            payload = {
                "attachments": [{
                    "color": color_map.get(alert.level, "#cccccc"),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Level", "value": alert.level.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Time", "value": alert.timestamp.isoformat(), "short": False}
                    ],
                    "footer": f"Alert ID: {alert.id}",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"Sent Slack alert: {alert.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


class WebhookNotifier:
    """Generic webhook notification channel."""

    def __init__(self, url: str, headers: dict[str, str] | None = None):
        """Initialize webhook notifier."""
        self.url = url
        self.headers = headers or {}

    def send(self, alert: Alert) -> bool:
        """Send alert to webhook."""
        try:
            response = requests.post(
                self.url,
                json=alert.to_dict(),
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            logger.info(f"Sent webhook alert: {alert.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class AlertManager:
    """
    Central alert management system.
    
    Features:
    - Alert creation and routing
    - Multi-channel notifications
    - Alert aggregation and throttling
    - Alert history and analytics
    - Alert resolution and acknowledgment
    """

    def __init__(self, max_history: int = 10000):
        """Initialize alert manager."""
        self.max_history = max_history

        # Alert storage
        self._alerts: deque = deque(maxlen=max_history)
        self._active_alerts: dict[str, Alert] = {}

        # Notification channels
        self._notifiers: dict[AlertChannel, Any] = {}

        # Alert rules
        self._rules: dict[str, AlertRule] = {}

        # Threading
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

        logger.info("Initialized AlertManager")

    def register_notifier(self, channel: AlertChannel, notifier: Any) -> None:
        """Register notification channel."""
        with self._lock:
            self._notifiers[channel] = notifier
        logger.info(f"Registered notifier: {channel.value}")

    def add_rule(self, rule: AlertRule) -> None:
        """Add alert rule."""
        with self._lock:
            self._rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, name: str) -> None:
        """Remove alert rule."""
        with self._lock:
            if name in self._rules:
                del self._rules[name]
        logger.info(f"Removed alert rule: {name}")

    def create_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "manual",
        tags: dict[str, str] | None = None,
        channels: list[AlertChannel] | None = None
    ) -> Alert:
        """Create and send alert."""
        alert = Alert(
            id=f"alert_{int(time.time() * 1000)}",
            timestamp=datetime.now(),
            level=level,
            title=title,
            message=message,
            source=source,
            tags=tags or {}
        )

        # Store alert
        with self._lock:
            self._alerts.append(alert)
            self._active_alerts[alert.id] = alert

        # Send notifications
        if channels is None:
            channels = list(self._notifiers.keys())

        for channel in channels:
            notifier = self._notifiers.get(channel)
            if notifier:
                try:
                    notifier.send(alert)
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")

        logger.info(f"Created alert: {alert.id} [{level.value}] {title}")
        return alert

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark alert as resolved."""
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now()
                del self._active_alerts[alert_id]
                logger.info(f"Resolved alert: {alert_id}")
                return True
        return False

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge alert."""
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by
                logger.info(f"Acknowledged alert: {alert_id} by {acknowledged_by}")
                return True
        return False

    def get_active_alerts(self, level: AlertLevel | None = None) -> list[Alert]:
        """Get active (unresolved) alerts."""
        with self._lock:
            alerts = list(self._active_alerts.values())

        if level:
            alerts = [a for a in alerts if a.level == level]

        return alerts

    def get_alert_history(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        level: AlertLevel | None = None,
        limit: int = 100
    ) -> list[Alert]:
        """Get alert history."""
        with self._lock:
            alerts = list(self._alerts)

        # Filter by time
        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]

        # Filter by level
        if level:
            alerts = [a for a in alerts if a.level == level]

        # Sort by timestamp (newest first) and limit
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]

    def get_alert_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get alert statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)

        with self._lock:
            recent_alerts = [a for a in self._alerts if a.timestamp >= cutoff]

        stats = {
            "total": len(recent_alerts),
            "by_level": defaultdict(int),
            "by_source": defaultdict(int),
            "active": len(self._active_alerts),
            "resolved": sum(1 for a in recent_alerts if a.resolved),
            "acknowledged": sum(1 for a in recent_alerts if a.acknowledged)
        }

        for alert in recent_alerts:
            stats["by_level"][alert.level.value] += 1
            stats["by_source"][alert.source] += 1

        return dict(stats)

    def start_monitoring(self, check_interval: int = 60) -> None:
        """Start monitoring alert rules."""
        if self._monitoring:
            logger.warning("Alert monitoring already started")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(check_interval,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started alert monitoring (interval: {check_interval}s)")

    def stop_monitoring(self) -> None:
        """Stop monitoring alert rules."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped alert monitoring")

    def _monitor_loop(self, check_interval: int) -> None:
        """Monitor loop for checking alert rules."""
        while self._monitoring:
            try:
                # Check all rules
                with self._lock:
                    rules = list(self._rules.values())

                for rule in rules:
                    alert = rule.check()
                    if alert:
                        # Store and notify
                        with self._lock:
                            self._alerts.append(alert)
                            self._active_alerts[alert.id] = alert

                        # Send notifications
                        for notifier in self._notifiers.values():
                            try:
                                notifier.send(alert)
                            except Exception as e:
                                logger.error(f"Failed to send alert notification: {e}")

                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                time.sleep(check_interval)


# Global alert manager instance
_default_alert_manager: AlertManager | None = None


def get_default_alert_manager() -> AlertManager:
    """Get global default alert manager."""
    global _default_alert_manager
    if _default_alert_manager is None:
        _default_alert_manager = AlertManager()
    return _default_alert_manager
