# ui/ai_pages/ai_settings_assistant.py
"""
AI Settings Assistant - Control settings with natural language
"""

import re
from typing import Dict, Optional, List
from loguru import logger


class AISettingsAssistant:
    """Control POS settings with natural language"""
    
    @classmethod
    def parse_command(cls, command: str) -> Dict:
        """
        Parse natural language settings command
        
        Returns:
            {
                'action': 'toggle' | 'set' | 'open' | 'get',
                'setting': 'dark_mode' | 'language' | 'receipt_logo' | ...,
                'value': Optional[str],
                'response': str
            }
        """
        command_lower = command.lower().strip()
        
        # Check for toggle commands
        toggle_patterns = {
            'dark_mode': [
                r'(dark|night|ည)\s*(mode|theme|ပုံစံ|မုဒ်)',
                r'(turn|switch|change|ဖွင့်|ပိတ်)\s*(dark|night|ည)',
                r'^(dark|night|ည)$'
            ],
            'sound': [
                r'(sound|audio|အသံ)\s*(on|off|ဖွင့်|ပိတ်)',
                r'(turn|switch|change|ဖွင့်|ပိတ်)\s*(sound|audio|အသံ)',
            ],
            'auto_print': [
                r'(auto|အလိုအလျောက်)\s*(print|receipt|ပရင့်|ထွက်)',
                r'(print|receipt|ပရင့်)\s*(auto|အလိုအလျောက်)',
            ],
        }
        
        for setting, patterns in toggle_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    # Determine if turning on or off
                    if any(word in command_lower for word in ['off', 'ပိတ်', 'disable', 'deactivate']):
                        return cls._toggle_response(setting, False)
                    else:
                        return cls._toggle_response(setting, True)
        
        # Check for open commands
        if any(word in command_lower for word in ['open', 'ဖွင့်', 'show', 'ပြ']):
            if 'receipt' in command_lower and ('logo' in command_lower or 'ပုံ' in command_lower):
                return cls._open_setting('Receipt Logo Settings')
            elif 'language' in command_lower or 'ဘာသာ' in command_lower:
                return cls._open_setting('Language Settings')
            elif 'user' in command_lower or 'အသုံးပြုသူ' in command_lower:
                return cls._open_setting('User Settings')
            elif 'database' in command_lower or 'ဒေတာ' in command_lower:
                return cls._open_setting('Database Settings')
            else:
                return cls._open_setting('Settings')
        
        # Check for get/info commands
        if any(word in command_lower for word in ['what', 'show', 'get', 'ဘယ်လို', 'ပြပေး']):
            if 'version' in command_lower or 'ဗားရှင်း' in command_lower:
                return cls._get_info('version')
            elif 'language' in command_lower or 'ဘာသာ' in command_lower:
                return cls._get_info('language')
        
        # Unknown command - FIXED: Don't use bullet points in f-string
        return {
            'action': 'unknown',
            'setting': 'unknown',
            'value': None,
            'response': (
                "I don't understand that command.\n\n"
                "Try:\n"
                "- Dark mode on / ညမုဒ်ဖွင့်\n"
                "- Turn off sound / အသံပိတ်\n"
                "- Open receipt settings\n"
                "- What language is this?"
            )
        }
    
    @classmethod
    def _toggle_response(cls, setting: str, status: bool) -> Dict:
        """Generate toggle response"""
        setting_names = {
            'dark_mode': ('Dark Mode', 'ညမုဒ်'),
            'sound': ('Sound', 'အသံ'),
            'auto_print': ('Auto Print', 'အလိုအလျောက်ပရင့်'),
        }
        
        name_en, name_my = setting_names.get(setting, (setting, setting))
        status_text = "ON" if status else "OFF"
        status_emoji = "✅" if status else "❌"
        
        return {
            'action': 'toggle',
            'setting': setting,
            'value': status,
            'response': f"{status_emoji} {name_en} turned {status_text}",
            'response_my': f"{status_emoji} {name_my} {status_text}",
        }
    
    @classmethod
    def _open_setting(cls, setting: str) -> Dict:
        """Generate open setting response"""
        return {
            'action': 'open',
            'setting': setting,
            'value': None,
            'response': f"Opening {setting}...",
        }
    
    @classmethod
    def _get_info(cls, info_type: str) -> Dict:
        """Get system information"""
        if info_type == 'version':
            return {
                'action': 'get',
                'setting': 'version',
                'value': None,
                'response': "ZAY POS Version 2.0.0\nBuilt with Python, PyQt6"
            }
        elif info_type == 'language':
            return {
                'action': 'get',
                'setting': 'language',
                'value': None,
                'response': "Current language: English/Myanmar\nလက်ရှိဘာသာစကား: အင်္ဂလိပ်/မြန်မာ"
            }
        
        return {
            'action': 'unknown',
            'setting': info_type,
            'value': None,
            'response': "Information not found."
        }