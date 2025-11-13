# src/utils/email.py
"""
Email utilities for sending notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import os
from ..core.config_loader import config

def send_email(to_emails: List[str], subject: str, html_content: str, text_content: str = None) -> bool:
    """Send email using SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{config.get('email.from_name', 'HR System')} <{config.get('email.from_email')}>"
        msg['To'] = ', '.join(to_emails)
        
        # Add text part
        if text_content:
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
        
        # Add HTML part
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(config.get('email.smtp_server'), config.get('email.smtp_port')) as server:
            server.starttls()
            server.login(config.get('email.smtp_username'), config.get('email.smtp_password'))
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def send_password_reset_email(email: str, token: str) -> bool:
    """Send password reset email"""
    reset_url = f"{config.get('app.frontend_url')}/reset-password?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Password Reset</title>
    </head>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Password Reset Request</h2>
            <p>You have requested to reset your password. Click the button below to reset it:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" 
                   style="background-color: #007bff; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Reset Password
                </a>
            </div>
            <p>Or copy and paste this link in your browser:</p>
            <p style="word-break: break-all;">{reset_url}</p>
            <p>This link will expire in {config.get('security.reset_token_expire_minutes', 15)} minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                This email was sent from {config.get('app.name', 'HR System')}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Reset Request
    
    You have requested to reset your password. Copy and paste this link in your browser to reset it:
    {reset_url}
    
    This link will expire in {config.get('security.reset_token_expire_minutes', 15)} minutes.
    
    If you didn't request this, please ignore this email.
    """
    
    return send_email(
        to_emails=[email],
        subject="Password Reset Request",
        html_content=html_content,
        text_content=text_content
    )

def send_welcome_email(email: str, username: str) -> bool:
    """Send welcome email to new users"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Welcome to HR System</title>
    </head>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Welcome to HR System!</h2>
            <p>Hello {username},</p>
            <p>Your account has been successfully created. You can now access the HR System using your credentials.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin: 20px 0;">
                <p><strong>Username:</strong> {username}</p>
                <p><strong>Email:</strong> {email}</p>
            </div>
            <p>If you have any questions, please contact the HR department.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                This email was sent from {config.get('app.name', 'HR System')}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to HR System!
    
    Hello {username},
    
    Your account has been successfully created. You can now access the HR System using your credentials.
    
    Username: {username}
    Email: {email}
    
    If you have any questions, please contact the HR department.
    """
    
    return send_email(
        to_emails=[email],
        subject="Welcome to HR System",
        html_content=html_content,
        text_content=text_content
    )

def send_document_processed_email(email: str, filename: str, category: str, success: bool) -> bool:
    """Send email notification when document processing is complete"""
    if success:
        subject = f"Document Processed: {filename}"
        status_text = "successfully processed"
        status_color = "#28a745"
    else:
        subject = f"Document Processing Failed: {filename}"
        status_text = "failed to process"
        status_color = "#dc3545"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{subject}</title>
    </head>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Document Processing Update</h2>
            <p>Your document <strong>{filename}</strong> has been {status_text}.</p>
            <div style="background-color: {status_color}; color: white; padding: 10px; border-radius: 4px; margin: 15px 0;">
                <strong>Status:</strong> {'Completed' if success else 'Failed'}
                {f"<br><strong>Category:</strong> {category}" if success else ""}
            </div>
            <p>The document is now available in the HR system and can be used for employee queries.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                This email was sent from {config.get('app.name', 'HR System')}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Document Processing Update
    
    Your document {filename} has been {status_text}.
    
    Status: {'Completed' if success else 'Failed'}
    {f"Category: {category}" if success else ""}
    
    The document is now available in the HR system and can be used for employee queries.
    """
    
    return send_email(
        to_emails=[email],
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )