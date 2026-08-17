# ui/ai_pages/ai_chat_room.py
"""
AI Chat Room - Database Query Assistant
ZAY POS Database ထဲက အချက်အလက်များကို မေးမြန်နိုင်သော AI Chat Room
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QScrollArea, QTextEdit, QSizePolicy,
    QApplication, QMessageBox, QFileDialog, QComboBox
)
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from ui.themes.theme_manager import get_theme_colors
from ui.ai_pages.ai_chat_widgets import CopyableMessageFrame
from ui.ai_pages.ai_enhanced_worker import EnhancedQueryWorker
from ui.ai_pages.ai_conversation_context import AIConversationContext
from ui.ai_pages.ai_navigation import AINavigationRequest
from ui.ai_pages.ai_burmese_normalizer import AIBurmeseNormalizer
from utils.permissions import PermissionManager
from ui.ai_pages.ai_analytics import AIAnalytics
from ui.ai_pages.ai_cache import get_cache_stats, clear_cache
from ui.widgets.modern_button import ModernButton
from loguru import logger
import os
import re
from datetime import datetime, timedelta


class ChatInputEdit(QTextEdit):
    """Multi-line chat input: Enter sends, Shift+Enter inserts a new line."""

    submit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFixedHeight(58)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class AIChatRoom(QWidget):
    """
    AI Chat Room - Database Query Assistant
    """
    
    MAX_PROMPT_LENGTH = 2000

    # Signal for analytics
    query_logged = pyqtSignal(dict)
    navigation_requested = pyqtSignal(dict)
    
    def __init__(self, parent=None, user_id=None):
        super().__init__(parent)
        self._user_id = str(user_id or "anonymous")
        self._worker = None
        self._is_processing = False
        self._analytics = AIAnalytics()
        self._message_history = []
        self._recent_prompts = []
        self._cancel_requested = False
        self._last_status = "Ready"
        self._last_prompt = ""
        self._conversation_context = AIConversationContext()
        self._active_raw_query = ""
        self._active_resolved_query = ""
        self._pending_navigation = None
        self._last_result = None
        self._setup_ui()
        self._load_recent_prompts()
        
        # Welcome message
        self._add_welcome_message()
    
    def _setup_ui(self):
        colors = get_theme_colors()
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ============================================================
        # CHAT AREA
        # ============================================================
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        self.chat_content = QWidget()
        self.chat_content.setStyleSheet("background-color: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()
        
        self.chat_area.setWidget(self.chat_content)
        main_layout.addWidget(self.chat_area, stretch=1)
        
        # ============================================================
        # INPUT AREA
        # ============================================================
        input_frame = QFrame()
        self.input_frame = input_frame
        input_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_frame.setMinimumHeight(184)
        input_frame.setMaximumHeight(198)
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('card_bg', '#ffffff')};
                border-top: 1px solid {colors.get('border', '#e0e0e0')};
            }}
        """)
        input_frame_layout = QVBoxLayout(input_frame)
        input_frame_layout.setContentsMargins(32, 8, 32, 8)
        input_frame_layout.setSpacing(5)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        quick_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.recent_combo = QComboBox()
        self.recent_combo.addItem("Recent prompts")
        self.recent_combo.setFixedHeight(30)
        self.recent_combo.setMinimumWidth(180)
        self.recent_combo.setMaximumWidth(260)
        self.recent_combo.activated.connect(self._on_recent_prompt_selected)
        self.recent_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {colors.get('input_bg', '#f8f9fa')};
                color: {colors.get('text', '#2d3436')};
                border: 1px solid {colors.get('border', '#e0e0e0')};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }}
        """)
        quick_layout.addWidget(self.recent_combo)
        quick_layout.addStretch()

        self.clear_btn = ModernButton("Clear", ModernButton.DANGER)
        self.clear_btn.set_icon("delete", size=(15, 15))
        self.clear_btn.setCheckable(False)
        self.clear_btn.setAutoExclusive(False)
        self.clear_btn.setFixedSize(92, 30)
        self.clear_btn.clicked.connect(self._clear_chat)
        quick_layout.addWidget(self.clear_btn)

        self.retry_btn = ModernButton("Retry", ModernButton.SECONDARY)
        self.retry_btn.set_icon("refresh", size=(15, 15))
        self.retry_btn.setFixedSize(92, 30)
        self.retry_btn.setEnabled(False)
        self.retry_btn.setToolTip("Run the last prompt again")
        self.retry_btn.clicked.connect(self._retry_last_prompt)
        quick_layout.addWidget(self.retry_btn)

        self.analytics_btn = ModernButton("Stats", ModernButton.SECONDARY)
        self.analytics_btn.set_icon("bar_chart", size=(15, 15))
        self.analytics_btn.setCheckable(False)
        self.analytics_btn.setAutoExclusive(False)
        self.analytics_btn.setFixedSize(92, 30)
        self.analytics_btn.setToolTip("View AI Statistics")
        self.analytics_btn.clicked.connect(self._show_analytics)
        quick_layout.addWidget(self.analytics_btn)

        self.export_chat_btn = ModernButton("Export", ModernButton.SECONDARY)
        self.export_chat_btn.set_icon("file_export", size=(15, 15))
        self.export_chat_btn.setCheckable(False)
        self.export_chat_btn.setAutoExclusive(False)
        self.export_chat_btn.setFixedSize(92, 30)
        self.export_chat_btn.clicked.connect(self._export_chat_history)
        quick_layout.addWidget(self.export_chat_btn)
        input_frame_layout.addLayout(quick_layout)

        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setFixedHeight(46)
        chips_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        chips_widget = QWidget()
        chips_widget.setStyleSheet("background: transparent;")
        chips_widget.setMinimumHeight(40)
        chips_layout = QHBoxLayout(chips_widget)
        chips_layout.setContentsMargins(0, 3, 0, 3)
        chips_layout.setSpacing(8)
        self._add_quick_action(chips_layout, "Today Sales", "today sales", "trending_up")
        self._add_quick_action(chips_layout, "Low Stock", "low stock", "warning")
        self._add_quick_action(chips_layout, "Top Products", "top products", "trophy")
        self._add_quick_action(chips_layout, "Debt Summary", "debt summary", "credit_card")
        self._add_quick_action(chips_layout, "Expenses", "recent expenses", "payments")
        self._add_quick_action(chips_layout, "Commands", "/help", "info")
        chips_layout.addStretch()
        chips_scroll.setWidget(chips_widget)
        input_frame_layout.addWidget(chips_scroll)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        input_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Input field
        self.input_field = ChatInputEdit()
        self.input_field.setPlaceholderText("Ask me about your business data... (e.g., 'today sales' or 'ယနေ့ရောင်းအား')")
        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px 14px;
                border: 1px solid {colors.get('border', '#e0e0e0')};
                border-radius: 8px;
                font-size: 10.5pt;
                background-color: {colors.get('input_bg', '#f8f9fa')};
                color: {colors.get('text', '#2d3436')};
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
        """)
        self.input_field.submit_requested.connect(self._send_message)
        input_layout.addWidget(self.input_field, stretch=1)

        button_width = 112
        button_height = 36
        
        # Send button
        self.send_btn = ModernButton("Send", ModernButton.PRIMARY)
        self.send_btn.set_icon("send", size=(16, 16))
        self.send_btn.setCheckable(False)
        self.send_btn.setAutoExclusive(False)
        self.send_btn.setFixedSize(button_width, button_height)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.stop_btn = ModernButton("Stop", ModernButton.DANGER)
        self.stop_btn.set_icon("cancel", size=(16, 16))
        self.stop_btn.setCheckable(False)
        self.stop_btn.setAutoExclusive(False)
        self.stop_btn.setFixedSize(92, button_height)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_response)
        input_layout.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        input_frame_layout.addLayout(input_layout)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(2, 0, 2, 0)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {colors.get('text_secondary', '#636e72')}; font-size: 8.5pt;")
        self.char_count_label = QLabel(f"0 / {self.MAX_PROMPT_LENGTH}")
        self.char_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.char_count_label.setStyleSheet(f"color: {colors.get('text_secondary', '#636e72')}; font-size: 8.5pt;")
        meta_layout.addWidget(self.status_label)
        meta_layout.addStretch()
        meta_layout.addWidget(self.char_count_label)
        input_frame_layout.addLayout(meta_layout)
        self.input_field.textChanged.connect(self._update_input_meta)
        self._update_input_meta()
        
        main_layout.addWidget(input_frame, stretch=0)

    def _add_quick_action(self, layout, text, prompt, icon_name, callback=None):
        button = ModernButton(text, ModernButton.SECONDARY)
        button.set_icon(icon_name, size=(14, 14))
        button.setCheckable(False)
        button.setAutoExclusive(False)
        button.setFixedHeight(34)
        button.setMinimumWidth(118)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if callback:
            button.clicked.connect(callback)
        else:
            button.clicked.connect(lambda _checked=False, value=prompt: self._run_quick_prompt(value))
        layout.addWidget(button)
        return button

    def _run_quick_prompt(self, prompt):
        if not prompt or self._is_processing:
            return
        self.input_field.setPlainText(prompt)
        self._send_message()

    def _set_chat_status(self, text):
        self._last_status = text
        if hasattr(self, "status_label"):
            self.status_label.setText(text)

    def _message_timestamp(self):
        return datetime.now().strftime("%H:%M")

    def _on_recent_prompt_selected(self, index):
        if index <= 0:
            return
        prompt = self.recent_combo.itemText(index)
        self.input_field.setPlainText(prompt)
        self.input_field.setFocus()

    def _remember_prompt(self, text):
        text = text.strip()
        if not text:
            return
        if text in self._recent_prompts:
            self._recent_prompts.remove(text)
        self._recent_prompts.insert(0, text)
        self._recent_prompts = self._recent_prompts[:10]
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()
        self.recent_combo.addItem("Recent prompts")
        self.recent_combo.addItems(self._recent_prompts)
        self.recent_combo.setCurrentIndex(0)
        self.recent_combo.blockSignals(False)
        QSettings("ZAY POS", "AI Chat").setValue(f"recent_prompts/{self._user_id}", self._recent_prompts)

    def _load_recent_prompts(self):
        prompts = QSettings("ZAY POS", "AI Chat").value(f"recent_prompts/{self._user_id}", [])
        if isinstance(prompts, str):
            prompts = [prompts]
        for prompt in reversed(list(prompts or [])[:10]):
            self._remember_prompt(str(prompt))

    def _update_input_meta(self):
        length = len(self.input_field.toPlainText())
        over_limit = length > self.MAX_PROMPT_LENGTH
        self.char_count_label.setText(f"{length:,} / {self.MAX_PROMPT_LENGTH:,}")
        color = "#e74c3c" if over_limit else get_theme_colors().get("text_secondary", "#636e72")
        self.char_count_label.setStyleSheet(f"color: {color}; font-size: 8.5pt;")
        if not self._is_processing:
            self.send_btn.setEnabled(bool(length) and not over_limit)

    def _retry_last_prompt(self):
        if not self._last_prompt or self._is_processing:
            return
        self.input_field.setPlainText(self._last_prompt)
        self._send_message()
    
    def _add_welcome_message(self):
        """Add welcome message to chat"""
        message = """
👋 **Welcome to ZAY POS AI Assistant!**

I can help you with:
• 📊 **Sales** - Today, weekly, monthly, total
• 📦 **Products** - Stock, low stock, search
• 👥 **Customers** - Search, profile, top customers, statistics
• 💰 **Expenses** - Today, monthly, total, recent, category
• 📈 **Profit** - Profit summary
• 💳 **Credit/Debt** - Debt summary, customer debt
• 👤 **Employees** - Attendance, shifts, leave, payroll, performance
• 🛠️ **Diagnostics** - Paste an error message for safe, structured troubleshooting
• 🧠 **Read-only Insights** - Attendance health, late ranking, business health and cross-checks

**Try asking:**
• "today sales" | "ယနေ့ရောင်းအား"
• "low stock" | "စတော့နည်းသောပစ္စည်းများ"
• "top products" | "ထိပ်ဆုံးပစ္စည်းများ"
• "sales summary" | "sales by category"
• "search customer John" | "customer John"
• "today expenses" | "recent expenses"
• "ယနေ့" | "မနေ့က" | "1.8.2027"
• "profit" | "အမြတ်"
• "debt summary" | "အကြွေးစာရင်း"
• "today employee attendance" | "ဒီနေ့ ဝန်ထမ်း attendance"
• "EMP-0008 shift" | "pending employee leave"
• "ဒီလ ဝန်ထမ်းတွေ အလုပ်တက်တာ အခြေအနေကောင်းလား"
• "အလုပ်နောက်ကျဆုံးဝန်ထမ်း သုံးယောက်ပြ"
• "ဒီလ business အခြေအနေကို အကျဉ်းချုပ်ပေး"

💡 **Tip:** You can ask in English or Myanmar. Common spellings such as `ph`, `ဖုန်းနံပတ်`, `attendence`, `checkin`, and Myanmar digits such as `EMP-၀၀၀၈` are normalized automatically.
💬 **Follow-up:** After selecting an employee and period, ask “နောက်ကျတဲ့ရက်တွေပဲပြ” or “သူ့ shift ကရော”. Clear Chat resets this context.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **Special Commands:**
• `/analytics` - Show sales dashboard
• `/inventory` - Show reorder recommendations  
• `/customers` - Show customer insights
• `/export` - Export the latest authorized result (Excel/CSV/PDF)
• `/help` - Show all commands
"""
        
        bubble = CopyableMessageFrame(message, is_user=False, parent=self, timestamp=self._message_timestamp())
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._message_history.append(("AI", message.strip()))
        self._scroll_to_bottom()
    
    def _send_message(self):
        """Send user message"""
        text = self.input_field.toPlainText().strip()
        if not text or self._is_processing:
            return
        if len(text) > self.MAX_PROMPT_LENGTH:
            QMessageBox.warning(self, "Prompt Too Long", f"Please shorten the prompt to {self.MAX_PROMPT_LENGTH:,} characters or fewer.")
            return
        
        self.input_field.clear()
        self._last_prompt = text
        self.retry_btn.setEnabled(False)
        self._remember_prompt(text)
        self._add_user_message(text)
        
        # 🆕 Check for special commands
        cmd = text.lower().strip()
        
        if cmd == '/analytics':
            self._show_analytics_dashboard()
            return
        elif cmd == '/inventory':
            self._show_inventory_recommendations()
            return
        elif cmd == '/customers':
            self._show_customer_insights()
            return
        elif cmd == '/export':
            self._export_report()
            return
        elif cmd == '/help':
            self._show_command_help()
            return
        
        self._process_query(text)
    
    def _add_user_message(self, text):
        """Add user message to chat"""
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addStretch()
        
        bubble = CopyableMessageFrame(text, is_user=True, parent=self, timestamp=self._message_timestamp())
        container_layout.addWidget(bubble)
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._message_history.append(("You", text.strip()))
        self._scroll_to_bottom()
    
    def _add_bot_message(self, text, is_loading=False, enhanced_message=None, action_text=None, action_callback=None, actions=None, visual_spec=None, utility_actions=None):
        """Add bot message to chat"""
        colors = get_theme_colors()
        
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        if is_loading:
            bubble = QFrame()
            bubble.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#f0f0f0')};
                    border-radius: 12px;
                    padding: 10px 14px;
                }}
            """)
            layout = QVBoxLayout(bubble)
            layout.setContentsMargins(8, 6, 8, 6)
            
            # Loading animation with dots
            label = QLabel("⏳ Thinking")
            label.setStyleSheet(f"""
                color: {colors.get('text_secondary', '#636e72')};
                font-size: 10.5pt;
                background: transparent;
            """)
            layout.addWidget(label)
            
            # Store label reference for animation
            self._loading_label = label
            self._loading_dots = 0
            self._loading_timer = QTimer()
            self._loading_timer.timeout.connect(lambda: self._update_loading_animation(label))
            self._loading_timer.start(500)
            
            container_layout.addWidget(bubble)
        else:
            display_text = enhanced_message if enhanced_message else text
            bubble = CopyableMessageFrame(
                display_text,
                is_user=False,
                parent=self,
                timestamp=self._message_timestamp(),
                action_text=action_text,
                action_callback=action_callback,
                actions=actions,
                visual_spec=visual_spec,
                utility_actions=utility_actions,
            )
            container_layout.addWidget(bubble)
            if display_text:
                self._message_history.append(("AI", str(display_text).strip()))
        
        container_layout.addStretch()
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, container)
        self._scroll_to_bottom()
        
        return bubble

    def _format_product_results_page(self, results, search_term, start=0, limit=10):
        """Format one page of product search results."""
        total = len(results)
        end = min(start + limit, total)
        if start == 0:
            message = f"🔍 **Found {total} products for '{search_term}':**\n\n"
        else:
            message = f"📦 **More products for '{search_term}' ({start + 1}-{end} of {total}):**\n\n"

        for index, product in enumerate(results[start:end], start + 1):
            stock = product.get('stock', 0) or 0
            stock_emoji = "🟢" if stock > 10 else "🟡" if stock > 0 else "🔴"
            price = self._format_product_price(product.get('price', 0))
            message += f"{index}. {product.get('name', 'Unknown')} - {price} Ks {stock_emoji} (Stock: {stock})\n"

        remaining = total - end
        if remaining > 0:
            next_count = min(5, remaining)
            message += f"\n... and {remaining} more results"
            action_text = f"Show {next_count} more results"
        else:
            action_text = None

        return message, end, action_text

    def _add_product_search_message(self, result):
        """Add product search results with a clickable 'show more' action."""
        results = result.get('data') or []
        search_term = result.get('search_term') or self._extract_product_search_term(result.get('message', '')) or "search"
        if len(results) <= 10:
            self._add_bot_message(result.get('message', ''))
            return

        message, next_offset, action_text = self._format_product_results_page(results, search_term, start=0, limit=10)

        def show_more(_checked=False):
            nonlocal next_offset
            sender = self.sender()
            if sender:
                sender.setEnabled(False)
                sender.setText("Shown")
            next_message, next_offset, next_action_text = self._format_product_results_page(
                results,
                search_term,
                start=next_offset,
                limit=5
            )
            self._add_bot_message(next_message, action_text=next_action_text, action_callback=show_more if next_action_text else None)

        self._add_bot_message(message, action_text=action_text, action_callback=show_more if action_text else None)

    def _extract_product_search_term(self, message):
        match = re.search(r"products for '([^']+)'", message or "")
        return match.group(1) if match else ""

    def _format_product_price(self, value):
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError):
            return str(value or 0)
    
    def _update_loading_animation(self, label):
        """Update loading animation dots"""
        self._loading_dots = (self._loading_dots % 3) + 1
        dots = "." * self._loading_dots
        label.setText(f"⏳ Thinking{dots}")
    
    def _process_query(self, text):
        """Process user query"""
        if self._is_processing:
            return
        
        self._is_processing = True
        self._cancel_requested = False
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.input_field.setEnabled(False)
        self._set_chat_status("Thinking...")
        self._active_raw_query = text
        normalized_query = AIBurmeseNormalizer.normalize(text)
        self._active_resolved_query = self._conversation_context.resolve(normalized_query)
        self._pending_navigation = AINavigationRequest.parse(normalized_query)
        
        # Add loading message
        loading_bubble = self._add_bot_message("", is_loading=True)
        
        # Create and start enhanced worker
        self._worker = EnhancedQueryWorker(self._active_resolved_query, user_id=self._user_id)
        self._worker.progress.connect(lambda p: self._update_progress(loading_bubble, p))
        self._worker.finished.connect(lambda r: self._on_query_finished(r, loading_bubble))
        self._worker.error.connect(lambda e: self._on_query_error(e, loading_bubble))
        self._worker.start()
    
    def _update_progress(self, loading_bubble, progress):
        """Update progress in loading message"""
        self._set_chat_status(f"Thinking... {progress}%")
        if hasattr(self, '_loading_label'):
            self._loading_label.setText(f"⏳ Thinking... {progress}%")

    def _stop_response(self):
        if not self._is_processing:
            return
        self._cancel_requested = True
        self.stop_btn.setEnabled(False)
        self._set_chat_status("Stopping...")
        if self._worker and hasattr(self._worker, "stop"):
            self._worker.stop()
    
    def _on_query_finished(self, result, loading_bubble):
        """Handle query completion"""
        # Stop loading animation
        if hasattr(self, '_loading_timer'):
            self._loading_timer.stop()
        
        # Remove loading bubble
        self.chat_layout.removeWidget(loading_bubble)
        loading_bubble.deleteLater()

        if not self._cancel_requested:
            self._conversation_context.update(self._active_raw_query,self._active_resolved_query,result)
            if result.get("type")=="employee_query":result["_ai_module"]=self._conversation_context.module
            self._last_result=result
            if self._pending_navigation and result.get("type")!="error" and "permission" not in str(result.get("message") or "").lower():
                self.navigation_requested.emit(AINavigationRequest.enrich(self._pending_navigation,self._conversation_context))
        self._pending_navigation = None
        
        if self._cancel_requested:
            self._add_bot_message("Request stopped.")
        elif result.get('type') == 'error':
            self._add_bot_message(result.get('message', 'Unknown error occurred'))
        elif result.get('type') == 'product_search':
            self._add_product_search_message(result)
        else:
            actions=self._build_follow_up_actions(result)
            visual_spec=self._build_result_visual(result)
            utilities=self._build_result_utilities(result)
            enhanced = result.get('enhanced_message')
            if enhanced:
                self._add_bot_message(enhanced, enhanced_message=None, actions=actions, visual_spec=visual_spec, utility_actions=utilities)
            else:
                self._add_bot_message(result.get('message', ''), actions=actions, visual_spec=visual_spec, utility_actions=utilities)
        
        self._reset_ui()
        self._scroll_to_bottom()

    def _build_follow_up_actions(self,result):
        """Build up to three safe suggestions for the current answer."""
        if not result or result.get("type") in ("error","usage_guide","diagnostic"):
            return []
        permissions=self._current_permissions();module=self._conversation_context.module
        specs=[]
        if result.get("type")=="employee_query":
            by_module={
                "employees":[("Attendance","သူ့ attendance ကရော","attendance"),("View Shift","သူ့ shift ကရော","shifts"),("Leave History","သူ့ leave history ကရော","leave")],
                "attendance":[("Late Records","late records only","attendance"),("Missing Check-out","missing check-out only","attendance"),("View Shift","သူ့ shift ကရော","shifts")],
                "shifts":[("Attendance","သူ့ attendance ကရော","attendance"),("Employee Profile","သူ့ profile ကရော","employees")],
                "leave":[("Attendance","သူ့ attendance ကရော","attendance"),("Payroll","သူ့ payroll ကရော","payroll")],
                "payroll":[("Attendance","သူ့ attendance ကရော","attendance"),("Advances","သူ့ outstanding advance","employee_finance")],
                "finance":[("Payroll","သူ့ payroll ကရော","payroll"),("Performance","သူ့ performance ကရော","employee_performance")],
                "performance":[("Attendance","သူ့ attendance ကရော","attendance"),("Commission","သူ့ commission ကရော","employee_finance")],
                "cash_sessions":[("Attendance","သူ့ attendance ကရော","attendance")],
            }
            specs=by_module.get(module,[])
        elif result.get("type")=="insight":
            kind=result.get("insight_kind")
            specs={
                "attendance_health":[("Late Ranking","အလုပ်နောက်ကျဆုံးဝန်ထမ်း သုံးယောက်ပြ","attendance")],
                "late_ranking":[("Attendance Health","ဒီလ ဝန်ထမ်း attendance အခြေအနေကောင်းလား","attendance")],
                "sales_attendance_correlation":[("Attendance Health","ဒီလ ဝန်ထမ်း attendance အခြေအနေကောင်းလား","attendance")],
                "business_health":[("Today's Sales","today sales",None),("Monthly Expenses","monthly expenses","expense")],
            }.get(kind,[])
        else:
            result_type=str(result.get("type") or "").lower()
            message=str(result.get("message") or "").lower()
            if "stock" in result_type or "stock" in message:
                specs=[("Low Stock","low stock",None),("Stock Summary","stock summary",None)]
            elif "debt" in result_type or "debt" in message or "credit" in message:
                specs=[("Overdue Debts","overdue debts",None),("Recent Debts","recent debts",None)]
            elif "sale" in result_type or "sales" in message:
                specs=[("Today's Sales","today sales",None),("Top Products","top 5 products",None)]
        actions=[]
        for label,prompt,required in specs:
            if required and required not in permissions:
                continue
            if prompt.startswith("သူ့") and not self._conversation_context.employee_no:
                prompt="employee"+prompt[len("သူ့"):]
            actions.append((label,self._suggestion_callback(prompt)))
            if len(actions)==2:break
        navigation=self._navigation_for_result(result,module)
        if navigation:
            actions.append((navigation[0],self._navigation_callback(navigation[1])))
        return actions

    def _navigation_for_result(self,result,module):
        if result.get("type")=="employee_query" and module:
            permission={"employees":"employees","attendance":"attendance","shifts":"shifts","payroll":"payroll","leave":"leave","documents":"employee_documents","finance":"employee_finance","performance":"employee_performance","cash_sessions":"cash_sessions"}.get(module)
            if permission and permission in self._current_permissions():
                label={"employees":"Open Employees","attendance":"Open Attendance","shifts":"Open Shifts","payroll":"Open Payroll","leave":"Open Leave","documents":"Open Documents","finance":"Open Finance","performance":"Open Performance","cash_sessions":"Open Sessions"}.get(module,"Open Page")
                return label,AINavigationRequest.for_employee_module(module)
        if result.get("type")=="insight":
            kind=result.get("insight_kind")
            if kind in ("attendance_health","late_ranking") and "attendance" in self._current_permissions():return "Open Attendance",AINavigationRequest.for_employee_module("attendance")
            if kind=="sales_attendance_correlation" and "employee_performance" in self._current_permissions():return "Open Performance",AINavigationRequest.for_employee_module("performance")
            if kind=="business_health" and ({"sales_summary","reports"}&self._current_permissions()):return "Open Sales Summary",{"page":"sales_summary","filters":{}}
        page_by_type={"sales":"sales_summary","daily_summary":"sales_summary","sales_summary":"sales_summary","top_products":"products","low_stock":"inventory","expenses":"expense","expense_categories":"expense","receipts":"receipts","customer_search":"customers","customer_profile":"customers"}
        page=page_by_type.get(str(result.get("type") or "").lower())
        return (f"Open {page.replace('_',' ').title()}",{"page":page,"filters":{}}) if page else None

    def _navigation_callback(self,request):
        def navigate(_checked=False):
            enriched=AINavigationRequest.enrich(request,self._conversation_context)
            self.navigation_requested.emit(enriched)
        return navigate

    def _build_result_utilities(self,result):
        rows=self._exportable_rows(result)
        if not rows or not self._can_export_result(result):return []
        return [("Export",lambda _checked=False,r=result:self._export_ai_result(r)),("Print",lambda _checked=False,r=result:self._print_ai_result(r))]

    def _can_export_result(self,result):
        permissions=self._current_permissions();result_type=str(result.get("type") or "").lower()
        if result_type=="employee_query":
            module=result.get("_ai_module") or self._conversation_context.module
            required={"employees":"employees","attendance":"attendance","shifts":"shifts","payroll":"payroll","leave":"leave","documents":"employee_documents","finance":"employee_finance","performance":"employee_performance","cash_sessions":"cash_sessions"}.get(module,"employees")
            return required in permissions
        if result_type=="insight":
            required=set(result.get("_required_permissions") or [])
            if "sales_summary" in required and ({"sales_summary","reports"}&permissions):required.remove("sales_summary")
            return required.issubset(permissions)
        alternatives={
            "sales":{"sales","sales_summary","reports"},"daily_summary":{"sales_summary","reports"},"sales_summary":{"sales_summary","reports"},
            "top_products":{"products","reports"},"low_stock":{"inventory"},"expenses":{"expense","reports"},"expense_categories":{"expense","reports"},
            "debt_summary":{"credit"},"customer_debt":{"credit"},"overdue_debts":{"credit"},"recent_debts":{"credit"},
            "receipts":{"receipts"},"receipt_detail":{"receipts"},"customer_search":{"customers"},"customer_profile":{"customers"},"top_customers":{"customers","reports"},
        }.get(result_type,set())
        return bool(permissions.intersection(alternatives))

    def _exportable_rows(self,result):
        rows=result.get("data") or []
        if not rows or not all(isinstance(row,dict) for row in rows):return []
        if result.get("type")!="employee_query":
            blocked={"id","photo_data","photo_path","user_id","created_by","corrected_by","opened_by","closed_by"}
            return [{key:value for key,value in row.items() if key not in blocked and not isinstance(value,(bytes,bytearray,memoryview))} for row in rows]
        module=result.get("_ai_module") or self._conversation_context.module
        fields={
            "employees":("employee_no","full_name","phone","address","position","department","branch","hire_date","employment_status","zkteco_user_id"),
            "attendance":("attendance_date","employee_no","full_name","check_in","check_out","status","late_minutes","shift_start","notes","correction_reason"),
            "shifts":("employee_no","full_name","shift_name","start_time","end_time","effective_from","effective_to","weekly_off_days"),
            "payroll":("payroll_no","employee_no","full_name","period_month","basic_salary","allowance","overtime_amount","bonus","late_deduction","absence_deduction","advance_deduction","other_deduction","net_salary","status","paid_date","payment_method"),
            "leave":("employee_no","full_name","leave_type","start_date","end_date","days","reason","status","review_notes"),
            "finance":("employee_no","full_name","advance_date","amount","repaid_amount","balance","status","commission_rate","target_amount","commission_amount"),
            "performance":("employee_no","full_name","branch","sale_count","sales_total","refund_count","discount_total","target_amount","commission_rate","commission_amount"),
            "cash_sessions":("employee_no","full_name","opened_at","opening_cash","closed_at","expected_cash","actual_cash","difference","status","notes"),
        }.get(module,())
        return [{key:row.get(key) for key in fields if key in row} for row in rows]

    def _export_ai_result(self,result):
        rows=self._exportable_rows(result)
        if not rows or not self._can_export_result(result):
            QMessageBox.warning(self,"Export Result","This result is empty or you no longer have permission to export it.");return
        path,selected=QFileDialog.getSaveFileName(self,"Export AI Result",f"ai_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx","Excel Files (*.xlsx);;CSV Files (*.csv);;PDF Files (*.pdf)")
        if not path:return
        if not path.lower().endswith((".xlsx",".csv",".pdf")):
            path+= ".csv" if "CSV" in selected else ".pdf" if "PDF" in selected else ".xlsx"
        suffix=path.rsplit(".",1)[-1].upper();answer=QMessageBox.question(self,"Confirm Export",f"Export {len(rows):,} authorized record(s) as {suffix}?\n\nLocation: {path}",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        try:
            from ui.ai_pages.ai_result_exporter import AIResultExporter
            AIResultExporter.export(rows,path,self._result_title(result));QMessageBox.information(self,"Export Complete",f"Exported {len(rows):,} record(s) to:\n{path}")
        except Exception as exc:
            logger.error(f"AI result export failed: {exc}");QMessageBox.warning(self,"Export Failed",str(exc))

    def _print_ai_result(self,result):
        rows=self._exportable_rows(result)
        if not rows or not self._can_export_result(result):
            QMessageBox.warning(self,"Print Result","This result is empty or you no longer have permission to print it.");return
        answer=QMessageBox.question(self,"Confirm Print",f"Print {len(rows):,} authorized record(s)?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        try:
            from ui.ai_pages.ai_result_exporter import AIResultExporter
            AIResultExporter.print_rows(rows,self,self._result_title(result))
        except Exception as exc:
            logger.error(f"AI result print failed: {exc}");QMessageBox.warning(self,"Print Failed",str(exc))

    def _result_title(self,result):
        module=result.get("_ai_module") or self._conversation_context.module or str(result.get("type") or "AI Result")
        period=self._conversation_context.description()
        return f"ZAY POS — {module.replace('_',' ').title()}"+(f" — {period}" if period else "")

    def _build_result_visual(self,result):
        """Create a visualization spec only from already-authorized rows."""
        if not result:return None
        if result.get("type")!="employee_query":return self._build_business_visual(result)
        rows=result.get("data") or [];module=self._conversation_context.module
        if module=="attendance":
            statuses=("Present","Late","Incomplete","Absent","Half-day","Leave")
            counts={status:sum(str(row.get("status") or "").lower()==status.lower() for row in rows) for status in statuses}
            return {"title":"Attendance overview","cards":[
                {"label":"Records","value":str(len(rows))},{"label":"Present","value":str(counts["Present"])},
                {"label":"Late","value":str(counts["Late"])},{"label":"Issues","value":str(counts["Incomplete"]+counts["Absent"]+counts["Half-day"])},
            ],"bars":[{"label":status,"value":count,"display":str(count)} for status,count in counts.items() if count]}
        if module=="payroll":
            net=sum(float(row.get("net_salary") or 0) for row in rows);paid=sum(str(row.get("status"))=="Paid" for row in rows)
            return {"title":"Payroll overview","cards":[
                {"label":"Records","value":str(len(rows))},{"label":"Net total","value":self._compact_number(net)},
                {"label":"Paid","value":str(paid)},{"label":"Draft","value":str(len(rows)-paid)},
            ],"bars":[{"label":row.get("full_name") or row.get("employee_no"),"value":row.get("net_salary") or 0,"display":f"{self._compact_number(row.get('net_salary'))} Ks"} for row in rows[:8]]}
        if module=="performance":
            revenue=sum(float(row.get("sales_total") or 0) for row in rows);sales=sum(int(row.get("sale_count") or 0) for row in rows);commission=sum(float(row.get("commission_amount") or 0) for row in rows)
            return {"title":"Performance overview","cards":[
                {"label":"Employees","value":str(len(rows))},{"label":"Sales","value":str(sales)},
                {"label":"Revenue","value":self._compact_number(revenue)},{"label":"Commission","value":self._compact_number(commission)},
            ],"bars":[{"label":row.get("full_name") or row.get("employee_no"),"value":row.get("sales_total") or 0,"display":f"{self._compact_number(row.get('sales_total'))} Ks"} for row in rows[:8]]}
        if module=="finance":
            is_commission="commission" in self._active_resolved_query.lower() or "ကော်မရှင်" in self._active_resolved_query
            field="commission_amount" if is_commission else "balance";total=sum(float(row.get(field) or 0) for row in rows)
            label="Commission" if is_commission else "Outstanding"
            return {"title":f"{label} overview","cards":[
                {"label":"Records","value":str(len(rows))},{"label":f"{label} total","value":self._compact_number(total)},
            ],"bars":[{"label":row.get("full_name") or row.get("employee_no"),"value":row.get(field) or 0,"display":f"{self._compact_number(row.get(field))} Ks"} for row in rows[:8]]}
        if module=="leave":
            approved=sum(float(row.get("days") or 0) for row in rows if row.get("status")=="Approved");pending=sum(float(row.get("days") or 0) for row in rows if row.get("status")=="Pending")
            return {"title":"Leave overview","cards":[{"label":"Requests","value":str(len(rows))},{"label":"Approved days","value":self._compact_number(approved)},{"label":"Pending days","value":self._compact_number(pending)}]}
        return None

    def _build_business_visual(self,result):
        rows=result.get("data") or [];result_type=str(result.get("type") or "").lower()
        if result_type=="insight" and rows:
            kind=result.get("insight_kind")
            if kind=="attendance_health":
                metrics={str(row.get("Metric")):row.get("Value") for row in rows}
                return {"title":"Attendance health","cards":[{"label":"Records","value":str(metrics.get("Records",0))},{"label":"Present","value":str(metrics.get("Present",0))},{"label":"Late","value":str(metrics.get("Late",0))},{"label":"Issue rate","value":f"{metrics.get('Issue Rate %',0)}%"}],"bars":[{"label":name,"value":metrics.get(name,0)} for name in ("Present","Late","Incomplete","Absent","Half-day","Leave") if metrics.get(name,0)]}
            if kind=="late_ranking":
                return {"title":"Late ranking","cards":[{"label":"Employees","value":str(len(rows))},{"label":"Late minutes","value":self._compact_number(sum(float(row.get('late_minutes') or 0) for row in rows))}],"bars":[{"label":row.get("full_name") or row.get("employee_no"),"value":row.get("late_minutes") or 0,"display":f"{row.get('late_minutes') or 0} min"} for row in rows]}
            if kind=="sales_attendance_correlation":
                return {"title":"Sales + attendance review","cards":[{"label":"Employees flagged","value":str(len(rows))},{"label":"Sales","value":self._compact_number(sum(float(row.get('sales_total') or 0) for row in rows))},{"label":"Attendance issues","value":str(sum(int(row.get('attendance_issues') or 0) for row in rows))}],"bars":[{"label":row.get("full_name") or row.get("employee_no"),"value":row.get("sales_total") or 0,"display":f"{self._compact_number(row.get('sales_total'))} Ks"} for row in rows[:8]]}
            if kind=="business_health":
                current=rows[0]
                return {"title":"Business health","cards":[{"label":"Transactions","value":str(current.get('transactions',0))},{"label":"Sales","value":self._compact_number(current.get('sales'))},{"label":"Expenses","value":self._compact_number(current.get('expenses'))},{"label":"Net","value":self._compact_number(current.get('net'))}],"bars":[{"label":row.get("Period"),"value":row.get("sales") or 0,"display":f"{self._compact_number(row.get('sales'))} Ks"} for row in rows]}
        if result_type=="sales" and rows:
            row=rows[0]
            return {"title":"Sales overview","cards":[
                {"label":"Transactions","value":str(row.get("Transactions",0))},
                {"label":"Total sales","value":self._compact_number(self._as_number(row.get("Total Sales")))},
                {"label":"Average","value":self._compact_number(self._as_number(row.get("Average")))},
                {"label":"Profit","value":self._compact_number(self._as_number(row.get("Profit")))},
            ]}
        if result_type=="daily_summary" and rows:
            row=rows[0]
            return {"title":"Daily business overview","cards":[
                {"label":"Sales","value":self._compact_number(self._as_number(row.get("Total Sales")))},
                {"label":"Gross profit","value":self._compact_number(self._as_number(row.get("Gross Profit")))},
                {"label":"Expenses","value":self._compact_number(self._as_number(row.get("Total Expenses")))},
                {"label":"Net","value":self._compact_number(self._as_number(row.get("Net After Expenses")))},
            ],"bars":[
                {"label":"Sales","value":self._as_number(row.get("Total Sales"))},
                {"label":"Profit","value":self._as_number(row.get("Gross Profit"))},
                {"label":"Expenses","value":self._as_number(row.get("Total Expenses"))},
            ]}
        if result_type=="top_products" and rows:
            revenue=sum(self._as_number(row.get("Revenue")) for row in rows)
            quantity=sum(self._as_number(row.get("Total Quantity")) for row in rows)
            return {"title":"Top products","cards":[{"label":"Products","value":str(len(rows))},{"label":"Quantity","value":self._compact_number(quantity)},{"label":"Revenue","value":self._compact_number(revenue)}],
                    "bars":[{"label":row.get("Product"),"value":self._as_number(row.get("Revenue")),"display":f"{self._compact_number(self._as_number(row.get('Revenue')))} Ks"} for row in rows[:8]]}
        if result_type=="low_stock" and rows:
            stock=sum(self._as_number(row.get("Stock")) for row in rows)
            return {"title":"Low-stock overview","cards":[{"label":"Products","value":str(len(rows))},{"label":"Units left","value":self._compact_number(stock)}],
                    "bars":[{"label":row.get("Product"),"value":self._as_number(row.get("Stock")),"display":str(row.get("Stock") or 0)} for row in rows[:8]]}
        if result_type in ("expenses","expense_categories") and rows:
            amount_key="Amount" if any("Amount" in row for row in rows) else "Total"
            total=sum(self._as_number(row.get(amount_key)) for row in rows)
            return {"title":"Expense overview","cards":[{"label":"Categories","value":str(len(rows))},{"label":"Total","value":self._compact_number(total)}],
                    "bars":[{"label":row.get("Category") or "Expense","value":self._as_number(row.get(amount_key)),"display":f"{self._compact_number(self._as_number(row.get(amount_key)))} Ks"} for row in rows[:8]]}
        if result_type=="sales_summary" and rows:
            label_key=next((key for key in ("Product","Category","Parent Category","Category Group","Payment Type","Date") if key in rows[0]),None)
            value_key=next((key for key in ("Amount","Revenue","Total Sales","Sales") if key in rows[0]),None)
            if label_key and value_key:
                total=sum(self._as_number(row.get(value_key)) for row in rows)
                return {"title":"Sales breakdown","cards":[{"label":"Groups","value":str(len(rows))},{"label":"Total","value":self._compact_number(total)}],
                        "bars":[{"label":row.get(label_key),"value":self._as_number(row.get(value_key)),"display":f"{self._compact_number(self._as_number(row.get(value_key)))} Ks"} for row in rows[:8]]}
        return None

    @staticmethod
    def _compact_number(value):
        try:
            number=float(value or 0)
            if abs(number)>=1_000_000:return f"{number/1_000_000:.1f}M"
            if abs(number)>=1_000:return f"{number/1_000:.1f}K"
            return f"{number:,.0f}"
        except (TypeError,ValueError):return str(value or 0)

    @staticmethod
    def _as_number(value):
        try:return float(str(value or 0).replace(",","").replace(" Ks","").strip())
        except (TypeError,ValueError):return 0.0

    def _suggestion_callback(self,prompt):
        def submit(_checked=False):
            if self._is_processing:return
            sender=self.sender()
            if sender:sender.setEnabled(False)
            self.input_field.setPlainText(prompt)
            self._send_message()
        return submit

    def _current_permissions(self):
        try:return PermissionManager.get_user_permissions(int(self._user_id))
        except (TypeError,ValueError):return set()
    
    def _on_query_error(self, error, loading_bubble):
        """Handle query error"""
        # Stop loading animation
        if hasattr(self, '_loading_timer'):
            self._loading_timer.stop()
        
        # Remove loading bubble
        self.chat_layout.removeWidget(loading_bubble)
        loading_bubble.deleteLater()
        
        self._add_bot_message(f"❌ {error}")
        self._reset_ui()
        self._scroll_to_bottom()
    
    def _reset_ui(self):
        """Reset UI state"""
        self._is_processing = False
        self._worker = None
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.retry_btn.setEnabled(bool(self._last_prompt))
        self._cancel_requested = False
        context=self._conversation_context.description()
        self._set_chat_status(f"Ready · {context}" if context else "Ready")
        self._update_input_meta()
    
    def _scroll_to_bottom(self):
        """Scroll chat to bottom"""
        QTimer.singleShot(50, lambda: self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        ))
    
    def _clear_chat(self):
        """Clear chat history"""
        reply = QMessageBox.question(
            self,
            "Clear Chat",
            "Are you sure you want to clear all messages and conversation context?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        while self.chat_layout.count() > 1:
            item = self.chat_layout.itemAt(0)
            if item.widget():
                item.widget().deleteLater()
            self.chat_layout.removeItem(item)
        
        self._message_history.clear()
        self._conversation_context.clear()
        self._active_raw_query = ""
        self._active_resolved_query = ""
        self._pending_navigation = None
        self._last_result = None
        self._add_welcome_message()
        self._set_chat_status("Chat cleared")

    def _export_chat_history(self):
        if not self._message_history:
            QMessageBox.information(self, "Export Chat", "No chat messages to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Chat",
            f"ai_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write("ZAY POS AI Chat Transcript\n")
                file.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                file.write("=" * 60 + "\n\n")
                for speaker, message in self._message_history:
                    file.write(f"{speaker}:\n{message}\n\n")
            self._set_chat_status("Chat exported")
            QMessageBox.information(self, "Export Chat", f"Chat exported to:\n{file_path}")
        except Exception as e:
            logger.error(f"Failed to export AI chat: {e}")
            QMessageBox.warning(self, "Export Chat", f"Failed to export chat:\n{e}")
    
    def _show_analytics(self):
        """Show analytics dialog"""
        stats = self._analytics.get_statistics()
        suggestions = self._analytics.get_suggestions()
        cache_stats = get_cache_stats()
        
        message = "📊 **AI Chat Statistics**\n\n"
        message += f"📝 Total Queries: {stats['total_queries']}\n"
        message += f"👥 Unique Users: {stats['unique_users']}\n"
        message += f"⚠️ Error Rate: {stats['error_rate']}\n"
        message += f"⏱️ Avg Response Time: {stats['avg_response_time']}\n"
        message += f"📈 Daily Avg: {stats['daily_avg']:.1f} queries/day\n\n"
        
        message += "🔥 **Popular Intents:**\n"
        for intent, count in stats['popular_intents']:
            emoji = {
                'sales_today': '📊',
                'sales_weekly': '📈',
                'profit': '💰',
                'low_stock': '⚠️',
                'top_products': '🏆'
            }.get(intent, '•')
            message += f"  {emoji} {intent}: {count} queries\n"
        
        if cache_stats:
            message += f"\n💾 **Cache:**\n"
            message += f"  • Size: {cache_stats.get('size', 0)}/{cache_stats.get('max_size', 20)}\n"
            message += f"  • Hit Rate: {cache_stats.get('hit_rate', '0%')}\n"
        
        if suggestions:
            message += "\n💡 **Suggestions:**\n"
            for suggestion in suggestions:
                message += f"  • {suggestion}\n"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("AI Analytics")
        msg.setText(message)
        msg.setIcon(QMessageBox.Icon.Information)
        
        clear_cache_btn = msg.addButton("Clear Cache", QMessageBox.ButtonRole.ActionRole)
        clear_stats_btn = msg.addButton("Clear Stats", QMessageBox.ButtonRole.ActionRole)
        close_btn = msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == clear_cache_btn:
            clear_cache()
            QMessageBox.information(self, "Cache Cleared", "Cache has been cleared successfully!")
        elif msg.clickedButton() == clear_stats_btn:
            self._analytics.clear()
            QMessageBox.information(self, "Stats Cleared", "Analytics statistics have been cleared!")
    
    # ================================================================
    # 🆕 SPECIAL COMMANDS - Phase 2
    # ================================================================
    
    def _show_analytics_dashboard(self):
        """Show analytics dashboard in chat"""
        try:
            from ui.ai_pages.ai_dashboard import get_dashboard_data_sync
            
            data = get_dashboard_data_sync()
            
            if data:
                message = f"""
📊 **AI Analytics Dashboard**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **Today's Sales:** {data.get('today_sales', 0):,.0f} Ks
📋 **Transactions:** {data.get('today_transactions', 0)}
🎯 **Today's Profit:** {data.get('today_profit', 0):,.0f} Ks

📦 **Low Stock Items:** {data.get('low_stock_count', 0)}
👥 **Total Customers:** {data.get('total_customers', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **Commands:**
• `/analytics` - Show this dashboard
• `/inventory` - Show reorder recommendations
• `/customers` - Show customer insights
• `/export` - Export the latest authorized result (Excel/CSV/PDF)
• `/help` - Show all commands
"""
                self._add_bot_message(message)
            else:
                self._add_bot_message("❌ Failed to load analytics data. Make sure you have sales data in the database.")
                
        except Exception as e:
            logger.error(f"Failed to show analytics: {e}")
            self._add_bot_message(f"❌ Error loading analytics: {str(e)}")
    
    def _show_inventory_recommendations(self):
        """Show inventory recommendations in chat"""
        try:
            from ui.ai_pages.ai_inventory_recommendation import AIInventoryRecommendation
            
            recommendations = AIInventoryRecommendation.get_reorder_recommendations()
            
            if recommendations:
                message = "📦 **Reorder Recommendations**\n\n"
                
                for rec in recommendations[:10]:
                    emoji = {
                        'critical': '🚨',
                        'high': '🔴',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(rec['priority'], '📦')
                    
                    message += f"{emoji} **{rec['name']}**\n"
                    message += f"   • Stock: {rec['stock']} (Min: {rec['low_stock']})\n"
                    message += f"   • Days left: {rec['days_remaining']:.0f}\n"
                    message += f"   • Order: {rec['recommended_qty']} units\n"
                    message += f"   • Supplier: {rec['supplier_name']}\n\n"
                
                if len(recommendations) > 10:
                    message += f"... and {len(recommendations) - 10} more items"
                
                self._add_bot_message(message)
            else:
                self._add_bot_message("✅ No reorder recommendations. All stock is sufficient!")
                
        except Exception as e:
            logger.error(f"Failed to show inventory: {e}")
            self._add_bot_message(f"❌ Error loading inventory: {str(e)}")
    
    def _show_customer_insights(self):
        """Show customer insights in chat"""
        try:
            from ui.ai_pages.ai_customer_insights import AICustomerInsights
            
            segments = AICustomerInsights.get_customer_segments()
            
            if segments:
                message = "👥 **Customer Insights**\n\n"
                
                for seg in segments:
                    emoji = {
                        'VIP': '👑',
                        'Regular': '⭐',
                        'Occasional': '📋',
                        'New': '🆕'
                    }.get(seg['name'], '•')
                    
                    message += f"{emoji} **{seg['label']}**: {seg['count']} customers\n"
                    
                    if seg['customers']:
                        names = [c['name'][:20] for c in seg['customers'][:3]]
                        if names:
                            message += f"   └─ {', '.join(names)}\n"
                    message += "\n"
                
                self._add_bot_message(message)
            else:
                self._add_bot_message("📋 No customer data available yet.\nStart making sales to see customer insights!")
                
        except Exception as e:
            logger.error(f"Failed to show customers: {e}")
            self._add_bot_message(f"❌ Error loading customers: {str(e)}")
    
    def _export_report(self):
        """Export report from chat"""
        if self._last_result and self._exportable_rows(self._last_result):
            self._export_ai_result(self._last_result)
            return
        try:
            from ui.ai_pages.ai_report_generator import AIReportGenerator
            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Report",
                f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
                "CSV Files (*.csv);;JSON Files (*.json)"
            )
            
            if not file_path:
                return
            
            today = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            report = AIReportGenerator.generate_sales_report(start_date, today)
            
            if not report:
                self._add_bot_message("❌ No data available to export.")
                return
            
            if file_path.endswith('.csv'):
                if report.get('daily'):
                    success = AIReportGenerator.export_to_csv(
                        report['daily'],
                        file_path,
                        ['date', 'transactions', 'total_sales']
                    )
                    if success:
                        self._add_bot_message(f"✅ Report exported to:\n{file_path}")
                    else:
                        self._add_bot_message("❌ Failed to export CSV.")
                        
            elif file_path.endswith('.json'):
                success = AIReportGenerator.export_to_json(report, file_path)
                if success:
                    self._add_bot_message(f"✅ Report exported to:\n{file_path}")
                else:
                    self._add_bot_message("❌ Failed to export JSON.")
            
            else:
                self._add_bot_message("❌ Unsupported file format. Use .csv or .json")
                
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            self._add_bot_message(f"❌ Error exporting: {str(e)}")
    
    def _show_command_help(self):
        """Show command help"""
        message = """
📋 **AI Chat Commands**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Analytics:**
• `/analytics` - Show sales dashboard
• `/inventory` - Show reorder recommendations
• `/customers` - Show customer insights
• `/export` - Export the latest authorized result (Excel/CSV/PDF)

📝 **Quick Queries:**
• "today sales" - Today's sales
• "low stock" - Low stock products
• "top products" - Best selling products
• "profit" - Profit summary
• "debt summary" - Credit debt summary
• "today expenses" - Today's expenses
• "recent expenses" - Recent expenses

📦 **Product Queries:**
• "search [product]" - Search for a product
• "[barcode/SKU]" - Product details
• "stock summary" - Overall stock

👥 **Customer Queries:**
• "search customer [name/phone]" - Search customers
• "customer [name]" - Customer profile
• "customer balance [name]" - Customer credit balance
• "top customers" - Best customers
• "customer stats" - Customer statistics
• "customer debt [name]" - Customer debt

💰 **Expense Queries:**
• "today expenses" - Today's expenses
• "monthly expenses" - Last 30 days expenses
• "total expenses" - Total expense summary
• "recent expenses" - Latest expense entries
• "expense categories" - List available categories
• "expense category [name]" - Category expense summary
• "[category name]" - Direct category summary, e.g. ဈေးဖိုး

📅 **Date Queries:**
• "ယနေ့" / "ဒီနေ့" - Today daily summary
• "မနေ့က" - Yesterday daily summary
• "မနေ့တစ်နေ့က" - Day before yesterday
• "1.8.2027" - Daily summary for a date
• "ဈေးဖိုး ဒီနေ့" - Category expenses on a date

📊 **Sales Summary Queries:**
• "sales summary" - Sales Summary page overview
• "sales summary this month" - Monthly overview
• "top sales items" - Top products by net sales
• "sales by category" - Category sales
• "sales by payment" - Payment type sales
• "sales by category group" - Category group sales

🧾 **Receipts Queries:**
• "receipts summary" - Receipts Page overview
• "receipts 31.7.2026" - Receipts overview for a date
• "recent receipts" - Latest receipt list
• "receipt [invoice no]" - Receipt detail
• "refunded receipts" - Refunded receipts
• "discounted receipts" - Discounted receipts
• "credit receipts" - Credit receipts

👤 **Employee Queries (permission required):**
• "employee summary" - Active/on-leave/resigned employee counts
• "today employee attendance" - Today's attendance
• "missing check-in today" - Missing check-ins
• "late employees today" - Late/after-shift employees
• "EMP-0008 attendance" - One employee's attendance
• "employee shifts" / "EMP-0008 shift" - Shift assignments
• "pending employee leave" - Pending leave requests
• "payroll 2026-08" - Monthly payroll
• "outstanding salary advances" - Advance balances
• "employee performance" - 30-day performance
• "open cash sessions" - Open cash sessions

💬 **Help:**
• `/help` - Show this help
• "help" - General help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        self._add_bot_message(message)
    
    def update_theme(self):
        """Update theme"""
        colors = get_theme_colors()
        self.setStyleSheet(f"background-color: {colors.get('bg', '#f5f6fa')};")
        if hasattr(self, "input_frame"):
            self.input_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.get('card_bg', '#ffffff')};
                    border-top: 1px solid {colors.get('border', '#e0e0e0')};
                }}
            """)
        if hasattr(self, "input_field"):
            self.input_field.setStyleSheet(f"""
                QTextEdit {{
                    padding: 8px 14px;
                    border: 1px solid {colors.get('border', '#e0e0e0')};
                    border-radius: 8px;
                    font-size: 10.5pt;
                    background-color: {colors.get('input_bg', '#f8f9fa')};
                    color: {colors.get('text', '#2d3436')};
                }}
                QTextEdit:focus {{
                    border-color: #5865f2;
                }}
            """)
        if hasattr(self, "recent_combo"):
            self.recent_combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {colors.get('input_bg', '#f8f9fa')};
                    color: {colors.get('text', '#2d3436')};
                    border: 1px solid {colors.get('border', '#e0e0e0')};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 9pt;
                }}
            """)
        if hasattr(self, "status_label"):
            secondary = colors.get('text_secondary', '#636e72')
            self.status_label.setStyleSheet(f"color: {secondary}; font-size: 8.5pt;")
            self._update_input_meta()
        
        for button in self.findChildren(ModernButton):
            button.update_theme()

        for message in self.findChildren(CopyableMessageFrame):
            message.update_theme()
    
    def refresh(self):
        """Refresh page"""
        logger.info("AI Chat Room refreshed")
        stats = self._analytics.get_statistics()
        logger.debug(f"AI Analytics: {stats}")
