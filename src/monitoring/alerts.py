"""
告警管理系统
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class AlertChannel:
    """告警渠道基类"""
    
    async def send(self, alert: Alert) -> bool:
        """发送告警"""
        raise NotImplementedError


class EmailChannel(AlertChannel):
    """邮件告警渠道"""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
    
    async def send(self, alert: Alert) -> bool:
        """发送邮件告警"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            body = f"""
            Alert Level: {alert.level.value}
            Source: {alert.source}
            Time: {alert.timestamp}
            
            {alert.message}
            
            Additional Data:
            {alert.data}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Failed to send email alert: {e}")
            return False


class SlackChannel(AlertChannel):
    """Slack告警渠道"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, alert: Alert) -> bool:
        """发送Slack告警"""
        try:
            # 颜色映射
            colors = {
                AlertLevel.INFO: "#36a64f",
                AlertLevel.WARNING: "#ff9900",
                AlertLevel.ERROR: "#ff0000",
                AlertLevel.CRITICAL: "#8B0000"
            }
            
            payload = {
                "attachments": [{
                    "color": colors.get(alert.level, "#808080"),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Level", "value": alert.level.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Time", "value": alert.timestamp.isoformat(), "short": False}
                    ]
                }]
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
            return False


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.channels: List[AlertChannel] = []
        self.alerts: List[Alert] = []
        self.rules: List[Dict[str, Any]] = []
        self.handlers: Dict[str, List[Callable]] = {}
        
        # 统计
        self.stats = {
            "total_alerts": 0,
            "by_level": {level: 0 for level in AlertLevel},
            "sent": 0,
            "failed": 0
        }
    
    def add_channel(self, channel: AlertChannel):
        """添加告警渠道"""
        self.channels.append(channel)
    
    def add_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        level: AlertLevel,
        message_template: str
    ):
        """添加告警规则"""
        self.rules.append({
            "name": name,
            "condition": condition,
            "level": level,
            "message_template": message_template
        })
    
    def register_handler(self, level: AlertLevel, handler: Callable):
        """注册告警处理器"""
        if level not in self.handlers:
            self.handlers[level] = []
        self.handlers[level].append(handler)
    
    async def create_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        data: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """创建告警"""
        import uuid
        
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            level=level,
            title=title,
            message=message,
            source=source,
            data=data or {}
        )
        
        # 保存告警
        self.alerts.append(alert)
        
        # 更新统计
        self.stats["total_alerts"] += 1
        self.stats["by_level"][level] += 1
        
        # 发送告警
        await self._send_alert(alert)
        
        # 调用处理器
        await self._handle_alert(alert)
        
        return alert
    
    async def _send_alert(self, alert: Alert):
        """发送告警到所有渠道"""
        for channel in self.channels:
            try:
                success = await channel.send(alert)
                if success:
                    self.stats["sent"] += 1
                else:
                    self.stats["failed"] += 1
            except Exception as e:
                print(f"Error sending alert to channel: {e}")
                self.stats["failed"] += 1
    
    async def _handle_alert(self, alert: Alert):
        """调用告警处理器"""
        handlers = self.handlers.get(alert.level, [])
        for handler in handlers:
            try:
                await handler(alert)
            except Exception as e:
                print(f"Error in alert handler: {e}")
    
    def check_rules(self, data: Dict[str, Any]) -> List[Alert]:
        """检查告警规则"""
        triggered_alerts = []
        
        for rule in self.rules:
            try:
                if rule["condition"](data):
                    message = rule["message_template"].format(**data)
                    alert = Alert(
                        alert_id=str(uuid.uuid4()),
                        level=rule["level"],
                        title=rule["name"],
                        message=message,
                        source="rule_engine",
                        data=data
                    )
                    triggered_alerts.append(alert)
            except Exception as e:
                print(f"Error checking rule {rule['name']}: {e}")
        
        return triggered_alerts
    
    def get_recent_alerts(
        self,
        level: Optional[AlertLevel] = None,
        limit: int = 100
    ) -> List[Alert]:
        """获取最近的告警"""
        alerts = self.alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "total_channels": len(self.channels),
            "total_rules": len(self.rules),
            "unacknowledged": sum(1 for a in self.alerts if not a.acknowledged)
        }
