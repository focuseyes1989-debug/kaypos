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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from ui.themes.theme_manager import get_theme_colors
from ui.ai_pages.ai_chat_widgets import CopyableMessageFrame
from ui.ai_pages.ai_enhanced_worker import EnhancedQueryWorker
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
    
    # Signal for analytics
    query_logged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._is_processing = False
        self._analytics = AIAnalytics()
        self._message_history = []
        self._recent_prompts = []
        self._cancel_requested = False
        self._last_status = "Ready"
        self._setup_ui()
        
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
        input_frame.setMinimumHeight(160)
        input_frame.setMaximumHeight(172)
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

💡 **Tip:** You can ask in English or Myanmar!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **Special Commands:**
• `/analytics` - Show sales dashboard
• `/inventory` - Show reorder recommendations  
• `/customers` - Show customer insights
• `/export` - Export report (CSV/JSON)
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
        
        self.input_field.clear()
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
    
    def _add_bot_message(self, text, is_loading=False, enhanced_message=None, action_text=None, action_callback=None):
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
                action_callback=action_callback
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
        
        # Add loading message
        loading_bubble = self._add_bot_message("", is_loading=True)
        
        # Create and start enhanced worker
        self._worker = EnhancedQueryWorker(text, user_id="user_001")
        self._worker.progress.connect(lambda p: self._update_progress(loading_bubble, p))
        self._worker.finished.connect(lambda r: self._on_query_finished(r, loading_bubble))
        self._worker.error.connect(lambda e: self._on_query_error(e, loading_bubble))
        self._worker.start()
    
    def _update_progress(self, loading_bubble, progress):
        """Update progress in loading message"""
        pass

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
        
        if self._cancel_requested:
            self._add_bot_message("Request stopped.")
        elif result.get('type') == 'error':
            self._add_bot_message(result.get('message', 'Unknown error occurred'))
        elif result.get('type') == 'product_search':
            self._add_product_search_message(result)
        else:
            enhanced = result.get('enhanced_message')
            if enhanced:
                self._add_bot_message(enhanced, enhanced_message=None)
            else:
                self._add_bot_message(result.get('message', ''))
        
        self._reset_ui()
        self._scroll_to_bottom()
    
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
        self._cancel_requested = False
        self._set_chat_status("Ready")
    
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
            "Are you sure you want to clear all messages?",
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
• `/export` - Export report (CSV/JSON)
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
• `/export` - Export report (CSV/JSON)

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
        
        for button in self.findChildren(ModernButton):
            button.update_theme()

        for message in self.findChildren(CopyableMessageFrame):
            message.update_theme()
    
    def refresh(self):
        """Refresh page"""
        logger.info("AI Chat Room refreshed")
        stats = self._analytics.get_statistics()
        logger.debug(f"AI Analytics: {stats}")
