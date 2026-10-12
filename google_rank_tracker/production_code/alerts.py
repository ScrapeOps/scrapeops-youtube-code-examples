#!/usr/bin/env python3
"""
Alert system for ranking changes

Send notifications when rankings change significantly.
"""

import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os


@dataclass
class RankingAlert:
    """Alert for a significant ranking change."""
    keyword: str
    target_url: str
    previous_position: int
    current_position: int
    change: int  # positive = improved, negative = dropped
    date: str


class AlertManager:
    """Manage and send ranking alerts."""
    
    def __init__(self, 
                 smtp_server: str = None,
                 smtp_port: int = 587,
                 smtp_user: str = None,
                 smtp_password: str = None,
                 slack_webhook: str = None):
        """
        Initialize alert manager.
        
        Supports email (SMTP) and Slack webhooks.
        """
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER")
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK_URL")
    
    def send_email_alert(self, alerts: List[RankingAlert], 
                         recipient: str, subject: str = None):
        """Send email alert for ranking changes."""
        if not all([self.smtp_server, self.smtp_user, self.smtp_password]):
            raise ValueError("SMTP credentials not configured")
        
        if not alerts:
            return
        
        subject = subject or f"Ranking Alert: {len(alerts)} significant changes"
        
        # Build email body
        body = self._build_email_body(alerts)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = recipient
        
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
    
    def send_slack_alert(self, alerts: List[RankingAlert]):
        """Send Slack alert for ranking changes."""
        if not self.slack_webhook:
            raise ValueError("Slack webhook not configured")
        
        if not alerts:
            return
        
        import requests
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Ranking Alert: {len(alerts)} changes"
                }
            },
            {"type": "divider"}
        ]
        
        for alert in alerts:
            emoji = "📈" if alert.change > 0 else "📉"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *{alert.keyword}*\n"
                        f"`{alert.target_url}`\n"
                        f"Position: {alert.previous_position} → {alert.current_position} "
                        f"({'+' if alert.change > 0 else ''}{alert.change})"
                    )
                }
            })
        
        payload = {"blocks": blocks}
        
        response = requests.post(self.slack_webhook, json=payload)
        response.raise_for_status()
    
    def _build_email_body(self, alerts: List[RankingAlert]) -> str:
        """Build HTML email body."""
        rows = ""
        for alert in alerts:
            color = "#22c55e" if alert.change > 0 else "#ef4444"
            arrow = "↑" if alert.change > 0 else "↓"
            
            rows += f"""
            <tr>
                <td>{alert.keyword}</td>
                <td><code>{alert.target_url}</code></td>
                <td>{alert.previous_position}</td>
                <td>{alert.current_position}</td>
                <td style="color: {color}; font-weight: bold;">
                    {arrow} {abs(alert.change)}
                </td>
            </tr>
            """
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Ranking Changes Detected</h2>
            <p>{len(alerts)} keywords had significant position changes:</p>
            
            <table border="1" cellpadding="8" cellspacing="0" 
                   style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f3f4f6;">
                    <th>Keyword</th>
                    <th>Target URL</th>
                    <th>Previous</th>
                    <th>Current</th>
                    <th>Change</th>
                </tr>
                {rows}
            </table>
            
            <p style="color: #6b7280; font-size: 12px; margin-top: 20px;">
                Generated by Google Rank Tracker
            </p>
        </body>
        </html>
        """


def check_and_alert(db, alert_manager: AlertManager,
                    threshold: int = 3, recipient: str = None):
    """
    Check for significant changes and send alerts.
    
    Args:
        db: RankTrackerDB instance
        alert_manager: AlertManager instance
        threshold: Minimum position change to trigger alert
        recipient: Email recipient (if sending email)
    """
    changes = db.get_position_changes(days=7)
    
    alerts = []
    for change in changes:
        if abs(change["change"]) >= threshold:
            alerts.append(RankingAlert(
                keyword=change["keyword"],
                target_url=change["target_url"],
                previous_position=change["prev_pos"],
                current_position=change["current_pos"],
                change=change["change"],
                date=change.get("date", "today"),
            ))
    
    if alerts:
        if recipient:
            alert_manager.send_email_alert(alerts, recipient)
        
        if alert_manager.slack_webhook:
            alert_manager.send_slack_alert(alerts)
    
    return alerts


# Example usage
if __name__ == "__main__":
    from database import init_tracker
    
    db = init_tracker("example_tracker.db")
    
    # Configure alerts (use env vars or pass directly)
    alert_mgr = AlertManager(
        slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
    )
    
    # Check and alert
    alerts = check_and_alert(db, alert_mgr, threshold=3)
    
    print(f"Generated {len(alerts)} alerts")
    for alert in alerts:
        print(f"  {alert.keyword}: {alert.previous_position} → "
              f"{alert.current_position} ({alert.change:+d})")
