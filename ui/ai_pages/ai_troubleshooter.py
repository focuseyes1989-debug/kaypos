# ui/ai_pages/ai_troubleshooter.py
"""
AI Troubleshooter for common POS issues
"""

import platform
import subprocess
import os
from typing import Dict, List, Optional
from loguru import logger


class AITroubleshooter:
    """AI-powered troubleshooting for POS system"""
    
    @classmethod
    def troubleshoot(cls, issue: str) -> Dict:
        """
        Get solution for common POS issues
        
        Returns:
            {
                'issue': str,
                'solutions': List[str],
                'steps': List[str],
                'severity': 'critical' | 'warning' | 'info'
            }
        """
        issue_lower = issue.lower()
        
        # Check for specific issues
        if 'printer' in issue_lower and ('offline' in issue_lower or 'not working' in issue_lower):
            return cls._printer_offline()
        
        elif 'database' in issue_lower and ('lock' in issue_lower or 'locked' in issue_lower):
            return cls._database_locked()
        
        elif 'bluetooth' in issue_lower and ('printer' in issue_lower or 'device' in issue_lower):
            return cls._bluetooth_printer()
        
        elif 'network' in issue_lower or 'wifi' in issue_lower:
            return cls._network_issue()
        
        elif 'scan' in issue_lower or 'barcode' in issue_lower:
            return cls._barcode_issue()
        
        elif 'cash drawer' in issue_lower or 'cash' in issue_lower:
            return cls._cash_drawer_issue()
        
        elif 'slow' in issue_lower or 'lag' in issue_lower:
            return cls._slow_performance()
        
        elif 'login' in issue_lower or 'password' in issue_lower:
            return cls._login_issue()
        
        else:
            return cls._general_help(issue)
    
    @classmethod
    def _printer_offline(cls) -> Dict:
        """Printer offline solutions"""
        solutions = [
            "🖨️ Printer Power Check",
            "🔌 USB/Network Cable",
            "🔄 Print Spooler Restart",
            "📄 Paper/Toner Check",
        ]
        
        steps = [
            "1. Check if printer is powered ON and connected",
            "2. Verify USB cable is properly connected",
            "3. Restart Print Spooler service:",
            "   - Press Win + R, type 'services.msc'",
            "   - Find 'Print Spooler', right-click → Restart",
            "4. Check printer status in Settings → Printers",
            "5. Ensure printer is set as default printer",
        ]
        
        return {
            'issue': 'Printer Offline/Not Working',
            'solutions': solutions,
            'steps': steps,
            'severity': 'critical',
            'quick_fix': "ℹ️ Restart Print Spooler manually only after confirming no print job is still being processed."
        }
    
    @classmethod
    def _database_locked(cls) -> Dict:
        """Database locked solutions"""
        steps = [
            "1. Close all other POS instances",
            "2. Check if other users are accessing the database",
            "3. Wait 30 seconds and retry",
            "4. If issue persists, restart the POS application",
            "5. Check database file permissions",
        ]
        
        return {
            'issue': 'Database Locked',
            'solutions': ['Close other POS instances', 'Restart application', 'Check file permissions'],
            'steps': steps,
            'severity': 'warning',
        }
    
    @classmethod
    def _bluetooth_printer(cls) -> Dict:
        """Bluetooth printer solutions"""
        steps = [
            "1. Turn on Bluetooth on your computer",
            "2. Ensure printer is in pairing mode",
            "3. Go to Settings → Bluetooth & devices → Add device",
            "4. Select your printer from the list",
            "5. Check if printer is paired and connected",
        ]
        
        return {
            'issue': 'Bluetooth Printer Not Connecting',
            'solutions': ['Enable Bluetooth', 'Pair printer', 'Check connection'],
            'steps': steps,
            'severity': 'warning',
        }
    
    @classmethod
    def _network_issue(cls) -> Dict:
        """Network issue solutions"""
        steps = [
            "1. Check WiFi/Ethernet connection",
            "2. Restart your router/modem",
            "3. Run Windows Network Troubleshooter",
            "4. Check if other devices can connect",
            "5. If using VPN, try disconnecting",
        ]
        
        return {
            'issue': 'Network Connection Issue',
            'solutions': ['Check connection', 'Restart router', 'Run troubleshooter'],
            'steps': steps,
            'severity': 'critical',
        }
    
    @classmethod
    def _barcode_issue(cls) -> Dict:
        """Barcode scanner issues"""
        steps = [
            "1. Check USB connection of barcode scanner",
            "2. Ensure scanner is in USB Keyboard mode",
            "3. Test scanning in Notepad - does it type numbers?",
            "4. Check if scanner has power (LED light)",
            "5. Clean the scanner lens",
        ]
        
        return {
            'issue': 'Barcode Scanner Not Working',
            'solutions': ['Check USB connection', 'Test in Notepad', 'Clean scanner'],
            'steps': steps,
            'severity': 'warning',
        }
    
    @classmethod
    def _cash_drawer_issue(cls) -> Dict:
        """Cash drawer issues"""
        steps = [
            "1. Check cash drawer cable connection to printer",
            "2. Ensure printer is powered ON",
            "3. Check if drawer is locked or jammed",
            "4. Test: Print a receipt to trigger drawer",
            "5. Check printer driver settings",
        ]
        
        return {
            'issue': 'Cash Drawer Not Opening',
            'solutions': ['Check cable', 'Test receipt print', 'Check driver settings'],
            'steps': steps,
            'severity': 'warning',
        }
    
    @classmethod
    def _slow_performance(cls) -> Dict:
        """Performance issues"""
        steps = [
            "1. Close unnecessary programs running in background",
            "2. Clear POS cache and temporary files",
            "3. Check disk space (at least 1GB free recommended)",
            "4. Consider upgrading RAM if using large database",
            "5. Defragment your hard drive (if using HDD)",
        ]
        
        return {
            'issue': 'Slow Performance',
            'solutions': ['Close background apps', 'Clear cache', 'Free up disk space'],
            'steps': steps,
            'severity': 'warning',
        }
    
    @classmethod
    def _login_issue(cls) -> Dict:
        """Login issues"""
        steps = [
            "1. Check your username and password carefully",
            "2. Ensure Caps Lock is OFF",
            "3. Try resetting your password (contact admin)",
            "4. Check if your account is active",
            "5. Try restarting the application",
        ]
        
        return {
            'issue': 'Login Issue',
            'solutions': ['Check credentials', 'Reset password', 'Check account status'],
            'steps': steps,
            'severity': 'info',
        }
    
    @classmethod
    def _general_help(cls, issue: str) -> Dict:
        """General help for unknown issues"""
        return {
            'issue': f'Issue: "{issue}"',
            'solutions': ['Restart application', 'Check for updates', 'Contact support'],
            'steps': [
                "1. Try restarting the application",
                "2. Check if your system meets requirements",
                "3. Check for software updates",
                "4. If issue persists, contact support with error details",
            ],
            'severity': 'info',
        }
    
    @staticmethod
    def _restart_print_spooler() -> str:
        """Return guidance without changing operating-system services."""
        return "ℹ️ Please restart Print Spooler manually if you are authorized to do so."
