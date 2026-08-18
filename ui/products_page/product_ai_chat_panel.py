"""Products-page shell for the shared AI chat assistant."""

import re
import time

from PyQt6.QtCore import QEvent, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from ui.ai_pages.ai_chat_room import AIChatRoom
from ui.themes.theme_manager import get_theme_colors
from ui.widgets.modern_button import ModernButton
from ui.products_page.product_ai_insights import ProductAIInsights


class ProductInsightsWorker(QThread):
    completed = pyqtSignal(dict, str)

    def __init__(self, focus="all", include_sensitive=True, parent=None):
        super().__init__(parent)
        self.focus = focus
        self.include_sensitive = include_sensitive

    def run(self):
        self.completed.emit(ProductAIInsights.analyze(self.include_sensitive), self.focus)


class ProductAIChatPanel(QFrame):
    """Collapsible, product-focused entry point to the existing AI chat."""

    close_requested = pyqtSignal()
    product_action_requested = pyqtSignal(str, dict)
    audit_event = pyqtSignal(str, dict)

    QUICK_ACTIONS = (
        ("Add Product", "add product ", "add", False),
        ("Export", "/product-export", "file_export", True),
        ("Actions Help", "/product-actions", "info", True),
        ("Smart Insights", "/product-insights", "emoji_objects", True),
        ("Reorder Plan", "/product-reorder", "local_shipping", True),
        ("Slow Movers", "/product-slow", "trending_down", True),
        ("Low Stock", "low stock", "warning", True),
        ("Out of Stock", "out of stock products", "inventory_2", True),
        ("Search Product", "search product ", "search", False),
        ("Stock Summary", "stock summary", "bar_chart", True),
        ("Top Products", "top products", "trophy", True),
    )

    PRIMARY_ACTIONS = (
        ("Insights", "/product-insights", "analytics", True),
        ("Reorder", "/product-reorder", "local_shipping", True),
        ("Search", "search product ", "search", False),
    )

    def __init__(self, parent=None, user_id=None, can_view_sensitive=True):
        super().__init__(parent)
        self.setObjectName("productAIChatPanel")
        self.setMinimumWidth(440)
        self.setMaximumWidth(620)
        self._can_view_sensitive = bool(can_view_sensitive)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("productAIHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 9, 8, 9)

        self.title_label = QLabel("Product AI Assistant")
        self.title_label.setStyleSheet("font-size: 11pt; font-weight: 700;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        close_button = ModernButton("Close", ModernButton.TERTIARY)
        close_button.set_icon("close", size=(14, 14))
        close_button.setText("")
        close_button.setToolTip("Close assistant")
        close_button.set_chatgpt_style(True)
        close_button.setCheckable(False)
        close_button.setAutoExclusive(False)
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(close_button)
        layout.addWidget(self.header)

        self.context_label = QLabel("Context: All products", self)
        self.context_label.setWordWrap(True)
        self.context_label.setContentsMargins(12, 5, 12, 5)
        layout.addWidget(self.context_label)

        self.quick_scroll = QScrollArea(self)
        self.quick_scroll.setWidgetResizable(True)
        self.quick_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.quick_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.quick_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.quick_scroll.setFixedHeight(52)
        self.quick_frame = QWidget()
        quick_layout = QHBoxLayout(self.quick_frame)
        quick_layout.setContentsMargins(10, 7, 10, 7)
        quick_layout.setSpacing(3)
        quick_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for label, prompt, icon, submit in self.PRIMARY_ACTIONS:
            button = ModernButton(label, ModernButton.SECONDARY)
            button.set_icon(icon, size=(14, 14))
            button.setText("")
            button.setToolTip(label)
            button.set_compact(True)
            button.set_chatgpt_style(True)
            button.setCheckable(False)
            button.setAutoExclusive(False)
            button.setFixedSize(34, 30)
            button.clicked.connect(
                lambda _checked=False, text=prompt, send=submit: self.run_prompt(text, send)
            )
            quick_layout.addWidget(button)

        self.more_actions_button = QToolButton(self.quick_frame)
        self.more_actions_button.setText("More")
        self.more_actions_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_actions_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.more_actions_button.setFixedSize(64, 30)
        self.more_actions_menu = QMenu(self.more_actions_button)
        primary_prompts = {item[1] for item in self.PRIMARY_ACTIONS}
        for label, prompt, _icon, submit in self.QUICK_ACTIONS:
            if prompt in primary_prompts:
                continue
            action = self.more_actions_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, text=prompt, send=submit: self.run_prompt(text, send)
            )
        self.more_actions_button.setMenu(self.more_actions_menu)
        quick_layout.addWidget(self.more_actions_button)
        self.quick_scroll.setWidget(self.quick_frame)
        layout.addWidget(self.quick_scroll)

        self._context = {}
        self._insight_worker = None
        self._insight_started_at = None
        self.chat = AIChatRoom(
            self,
            user_id=user_id,
            query_transform=self._contextualize_query,
            result_renderer=self._render_product_results,
            command_handler=self._handle_product_command,
        )
        self.chat.input_field.setPlaceholderText(
            "Ask about products or stock... / ပစ္စည်းနှင့် stock အကြောင်း မေးပါ"
        )
        self.chat.set_compact_mode()
        self.chat.replace_welcome_message(
            "Product Assistant\n\n"
            "Search products, check stock, review reorder suggestions, or ask about the selected item.\n\n"
            "Examples: “Coca Cola stock”, “reorder plan”, “ဒီပစ္စည်းအကြောင်းပြပါ”"
        )
        layout.addWidget(self.chat, 1)
        self.update_theme()

    def set_product_context(self, *, product=None, search_text="", category="", active_filter=None):
        """Receive the Products page state used to resolve contextual questions."""
        self._context = {
            "product": product or {},
            "search_text": (search_text or "").strip(),
            "category": (category or "").strip(),
            "active_filter": active_filter or "",
        }
        parts = []
        if product and product.get("name"):
            parts.append(f"Selected: {product['name']}")
        if search_text:
            parts.append(f"Search: {search_text}")
        if category:
            parts.append(f"Category: {category}")
        if active_filter:
            parts.append(f"Filter: {active_filter.replace('_', ' ').title()}")
        self.context_label.setText("Context: " + (" • ".join(parts) if parts else "All products"))

    def _contextualize_query(self, query):
        """Resolve Products-page pronouns into terms understood by the AI worker."""
        text = (query or "").strip()
        lowered = text.lower()
        product = self._context.get("product") or {}
        product_name = str(product.get("name") or "").strip()

        selected_references = (
            "this product", "selected product", "current product",
            "ဒီပစ္စည်း", "ရွေးထားတဲ့ပစ္စည်း", "ရွေးထားသောပစ္စည်း",
        )
        if product_name and any(term in lowered for term in selected_references):
            stock_terms = ("stock", "လက်ကျန်", "ကျန်", "ရှိလဲ", "ရှိလား", "ဘယ်လောက်")
            if any(term in lowered for term in stock_terms):
                return f"{product_name} stock"
            return f"product {product_name} details"

        table_references = (
            "these products", "current results", "filtered products",
            "ဒီစာရင်း", "အခုစာရင်း", "စစ်ထားတဲ့ပစ္စည်း",
        )
        has_table_reference = any(term in lowered for term in table_references)
        search_text = self._context.get("search_text") or ""
        category = self._context.get("category") or ""
        active_filter = self._context.get("active_filter") or ""

        if has_table_reference:
            if search_text:
                return f"search product {search_text}"
            if category:
                return f"search product {category}"
            filter_prompts = {
                "low_stock": "low stock",
                "out_stock": "out of stock products",
                "expiring_soon": "expiring soon products",
                "expired": "expired products",
            }
            if active_filter in filter_prompts:
                return filter_prompts[active_filter]
        return text

    def run_prompt(self, prompt, submit=True):
        """Fill the shared chat input and optionally submit the prompt."""
        insight_commands = {
            "/product-insights": "all",
            "/product-reorder": "reorder",
            "/product-slow": "slow",
        }
        if prompt in insight_commands:
            self._run_inventory_insights(insight_commands[prompt], prompt)
            return
        self.chat.input_field.setPlainText(prompt)
        self.chat.input_field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        cursor = self.chat.input_field.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat.input_field.setTextCursor(cursor)
        if submit:
            self.chat._send_message()

    def _run_inventory_insights(self, focus, prompt):
        if self._insight_worker and self._insight_worker.isRunning():
            return
        self.chat._add_user_message(prompt)
        self.chat._set_chat_status("Analyzing inventory...")
        self.chat.send_btn.setEnabled(False)
        loading = self.chat._add_bot_message("", is_loading=True)
        self._insight_started_at = time.monotonic()
        self.audit_event.emit("query", {"command": prompt, "focus": focus})
        self._insight_worker = ProductInsightsWorker(focus, self._can_view_sensitive, self)
        self._insight_worker.completed.connect(
            lambda result, result_focus: self._on_insights_ready(result, result_focus, loading)
        )
        self._insight_worker.start()

    def _handle_product_command(self, text):
        lowered = str(text or "").strip().lower()
        if lowered == "/product-actions":
            self.chat._add_user_message(str(text))
            self.chat._add_bot_message(
                "Safe Product Actions\n\n"
                "• add product PRODUCT NAME — opens a prefilled form; you still review and save it\n"
                "• assign current results to category CATEGORY — previews a bulk update\n"
                "• export filtered products — confirms before opening the export dialog\n"
                "• Set Alert on a reorder card — previews the suggested low-stock alert\n\n"
                "All data-changing actions check permissions, show impact, require confirmation, and are logged."
            )
            return True
        commands = {
            "/product-insights": "all",
            "smart inventory insights": "all",
            "inventory insights": "all",
            "ပစ္စည်း insights": "all",
            "/product-reorder": "reorder",
            "reorder plan": "reorder",
            "reorder recommendations": "reorder",
            "ပြန်မှာရန် အကြံပြုချက်": "reorder",
            "/product-slow": "slow",
            "slow movers": "slow",
            "dead stock": "slow",
            "အရောင်းနှေးပစ္စည်း": "slow",
        }
        focus = commands.get(lowered)
        if focus:
            self._run_inventory_insights(focus, str(text))
            return True

        add_match = re.match(r"^(?:add|create)\s+product\s+(.+)$", str(text).strip(), re.IGNORECASE)
        if add_match:
            self.chat._add_user_message(str(text))
            self.product_action_requested.emit(
                "prefill_add", {"name": add_match.group(1).strip(),
                                "category": self._context.get("category") or ""}
            )
            return True

        category_match = re.match(
            r"^(?:assign|move)\s+(?:current results|filtered products|these products)\s+to\s+category\s+(.+)$",
            str(text).strip(), re.IGNORECASE,
        )
        if category_match:
            self.chat._add_user_message(str(text))
            self.product_action_requested.emit(
                "bulk_category", {"category": category_match.group(1).strip()}
            )
            return True

        if lowered in {"export current products", "export filtered products", "/product-export"}:
            self.chat._add_user_message(str(text))
            self.product_action_requested.emit("export_filtered", {})
            return True
        return False

    def _on_insights_ready(self, result, focus, loading):
        if hasattr(self.chat, "_loading_timer"):
            self.chat._loading_timer.stop()
        self.chat.chat_layout.removeWidget(loading)
        loading.deleteLater()
        self.chat.send_btn.setEnabled(True)
        self.chat._set_chat_status("Ready")
        elapsed = time.monotonic() - self._insight_started_at if self._insight_started_at else 0
        self.audit_event.emit(
            "query_result",
            {"focus": focus, "success": result.get("type") != "error", "elapsed_ms": round(elapsed * 1000)},
        )
        if result.get("type") == "error":
            self.chat._add_bot_message(result.get("message", "Inventory analysis failed."))
        else:
            self._render_inventory_insights(result, focus)
        self._insight_worker = None

    def _render_inventory_insights(self, result, focus="all"):
        container = QFrame(self.chat.chat_content)
        container.setObjectName("productInsightContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        summary = result.get("summary") or {}
        title = QLabel("Smart Inventory Insights")
        title.setStyleSheet("font-size: 11pt; font-weight: 700; border: none;")
        layout.addWidget(title)
        summary_label = QLabel(
            f"Reorder {summary.get('reorder', 0)}  •  Fast {summary.get('fast', 0)}  •  "
            f"Slow {summary.get('slow', 0)}  •  Dead {summary.get('dead', 0)}  •  "
            f"Expiry {summary.get('expiry', 0)}  •  "
            + (f"Margin {summary.get('margin', 0)}  •  " if summary.get('margin') is not None else "") +
            f"Duplicates {summary.get('duplicates', 0)}"
        )
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-size: 8.5pt; border: none;")
        layout.addWidget(summary_label)

        section_map = {
            "reorder": "Reorder Priorities",
            "fast": "Fast-moving Products (30 days)",
            "slow": "Slow-moving Products (90 days)",
            "dead": "Dead Stock (no sales in 90 days)",
            "expiry": "Expiry Risks",
            "margin": "Margin Warnings",
        }
        if focus == "reorder":
            section_keys = ("reorder",)
        elif focus == "slow":
            section_keys = ("slow", "dead")
        else:
            section_keys = tuple(key for key in section_map if key != "margin" or not result.get("sensitive_hidden"))

        if result.get("sensitive_hidden"):
            notice = QLabel("Cost, stock-value, and margin insights are hidden by your role permissions.")
            notice.setWordWrap(True)
            notice.setStyleSheet("color: #f39c12; font-size: 8.5pt; border: none;")
            layout.addWidget(notice)

        for key in section_keys:
            items = result.get(key) or []
            if not items:
                continue
            heading = QLabel(f"{section_map[key]} ({len(items)})")
            heading.setStyleSheet("font-weight: 700; margin-top: 5px; border: none;")
            layout.addWidget(heading)
            for item in items[:5]:
                layout.addWidget(self._create_product_card(item, self._insight_detail(key, item)))

        duplicates = result.get("duplicates") or []
        if focus == "all" and duplicates:
            heading = QLabel(f"Potential Duplicates ({len(duplicates)})")
            heading.setStyleSheet("font-weight: 700; margin-top: 5px; border: none;")
            layout.addWidget(heading)
            for group in duplicates[:3]:
                for item in group.get("products", [])[:3]:
                    detail = f"Same {group.get('reason')}: {group.get('value')}"
                    layout.addWidget(self._create_product_card(item, detail))

        self.chat.chat_layout.insertWidget(self.chat.chat_layout.count() - 1, container)
        feedback = QHBoxLayout()
        feedback.addStretch()
        for label, rating in (("Helpful", "helpful"), ("Needs review", "needs_review")):
            button = ModernButton(label, ModernButton.TERTIARY)
            button.setCheckable(False)
            button.setAutoExclusive(False)
            button.setFixedHeight(26)
            button.clicked.connect(
                lambda _checked=False, value=rating: self.audit_event.emit(
                    "feedback", {"feature": "product_insights", "rating": value}
                )
            )
            feedback.addWidget(button)
        layout.addLayout(feedback)
        self.chat._message_history.append(("AI", "Smart inventory insights generated"))
        self.chat._scroll_to_bottom()

    @staticmethod
    def _insight_detail(kind, item):
        if kind == "reorder":
            days = item.get("days_left")
            days_text = "No recent velocity" if days is None else f"~{days} days left"
            return (f"{item.get('priority', '').upper()} • Order {item.get('recommended_qty', 0)} • "
                    f"{days_text} • Sold 30d: {item.get('sold_30', 0):g}")
        if kind == "fast":
            return f"Sold 30d: {item.get('sold_30', 0):g} • Daily velocity: {item.get('daily_velocity', 0):g}"
        if kind == "slow":
            return f"Only {item.get('sold_90', 0):g} sold in 90 days • Current stock: {item.get('stock', 0):g}"
        if kind == "dead":
            if "stock_value" in item:
                return f"No sales in 90 days • Stock value: {item.get('stock_value', 0):,.0f} Ks"
            return f"No sales in 90 days • Current stock: {item.get('stock', 0):g}"
        if kind == "expiry":
            days = item.get("days_to_expiry", 0)
            timing = f"Expired {abs(days)} day(s) ago" if days < 0 else f"Expires in {days} day(s)"
            return f"{timing} • {item.get('expire_date', '')}"
        if kind == "margin":
            return (f"Margin: {item.get('margin_pct', 0):g}% • Cost: {item.get('cost', 0):,.0f} Ks • "
                    f"Price: {item.get('price', 0):,.0f} Ks")
        return ""

    def _render_product_results(self, result):
        """Render product searches as interactive cards inside the chat stream."""
        products = result.get("data") or []
        if not products:
            return False

        container = QFrame(self.chat.chat_content)
        container.setObjectName("productResultContainer")
        result_layout = QVBoxLayout(container)
        result_layout.setContentsMargins(8, 8, 8, 8)
        result_layout.setSpacing(7)

        search_term = result.get("search_term") or "products"
        heading = QLabel(f"Found {len(products)} result(s) for “{search_term}”")
        heading.setStyleSheet("font-weight: 700; border: none;")
        result_layout.addWidget(heading)

        visible_count = min(10, len(products))
        for product in products[:visible_count]:
            result_layout.addWidget(self._create_product_card(product))

        if len(products) > visible_count:
            more = ModernButton(f"Show {len(products) - visible_count} more", ModernButton.SECONDARY)
            more.setCheckable(False)
            more.setAutoExclusive(False)

            def show_more(_checked=False):
                insert_at = result_layout.indexOf(more)
                for extra_product in products[visible_count:]:
                    result_layout.insertWidget(insert_at, self._create_product_card(extra_product))
                    insert_at += 1
                more.setText("All results shown")
                more.setEnabled(False)
                self.chat._scroll_to_bottom()

            more.clicked.connect(show_more)
            result_layout.addWidget(more)

        self.chat.chat_layout.insertWidget(self.chat.chat_layout.count() - 1, container)
        self.chat._message_history.append(("AI", f"Found {len(products)} products for {search_term}"))
        self.chat._scroll_to_bottom()
        return True

    def _create_product_card(self, product, insight_text=""):
        card = QFrame(self.chat.chat_content)
        card.setObjectName("aiProductCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        stock = product.get("stock", 0) or 0
        low_stock = product.get("low_stock", 0) or 0
        status = "Out of Stock" if stock <= 0 else "Low Stock" if stock <= low_stock else "In Stock"
        status_color = "#ed4245" if stock <= 0 else "#f39c12" if stock <= low_stock else "#2ecc71"
        name = QLabel(str(product.get("name") or "Unknown product"))
        name.setWordWrap(True)
        name.setStyleSheet("font-weight: 700; font-size: 10pt; border: none;")
        layout.addWidget(name)

        details = QLabel(
            f"{product.get('category') or 'Uncategorized'}  •  "
            f"{self.chat._format_product_price(product.get('price', 0))} Ks  •  "
            f"Stock: {stock}  •  {status}"
        )
        details.setWordWrap(True)
        details.setStyleSheet(f"color: {status_color}; font-size: 8.5pt; border: none;")
        layout.addWidget(details)

        if insight_text:
            insight = QLabel(insight_text)
            insight.setWordWrap(True)
            insight.setStyleSheet("color: #5865f2; font-weight: 600; font-size: 8.5pt; border: none;")
            layout.addWidget(insight)

        identifiers = []
        if product.get("sku"):
            identifiers.append(f"SKU: {product['sku']}")
        if product.get("barcode"):
            identifiers.append(f"Barcode: {product['barcode']}")
        if identifiers:
            meta = QLabel("  •  ".join(identifiers))
            meta.setWordWrap(True)
            meta.setStyleSheet("font-size: 8pt; border: none;")
            layout.addWidget(meta)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addStretch()
        for label, action, icon in (
            ("View", "view", "visibility"),
            ("Edit", "edit", "edit"),
            ("Filter", "filter", "search"),
            ("Barcode", "barcode", "barcode"),
        ):
            button = ModernButton(label, ModernButton.SECONDARY)
            button.set_icon(icon, size=(13, 13))
            button.setText("")
            button.setToolTip(label)
            button.set_compact(True)
            button.set_chatgpt_style(True)
            button.setCheckable(False)
            button.setAutoExclusive(False)
            button.setFixedSize(32, 30)
            button.clicked.connect(
                lambda _checked=False, kind=action, data=dict(product):
                self.product_action_requested.emit(kind, data)
            )
            actions.addWidget(button)
        if product.get("recommended_low_stock") is not None:
            button = ModernButton("Set Alert", ModernButton.PRIMARY)
            button.set_icon("notifications_active", size=(13, 13))
            button.setText("")
            button.setToolTip("Apply suggested low-stock alert")
            button.set_compact(True)
            button.set_chatgpt_style(True)
            button.setCheckable(False)
            button.setAutoExclusive(False)
            button.setFixedSize(32, 30)
            button.clicked.connect(
                lambda _checked=False, data=dict(product):
                self.product_action_requested.emit("apply_reorder", data)
            )
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self._style_product_card(card)
        return card

    def _style_product_card(self, card):
        colors = get_theme_colors()
        card.setStyleSheet(
            f"QFrame#aiProductCard {{ background: {colors.get('card_bg', '#ffffff')}; "
            f"border: 1px solid {colors.get('border', '#e0e0e0')}; border-radius: 7px; }}"
        )

    def update_theme(self):
        colors = get_theme_colors()
        border = colors.get("border", "#e0e0e0")
        card = colors.get("card_bg", "#ffffff")
        muted = colors.get("input_bg", "#f8f9fa")
        text = colors.get("text", "#212529")
        self.setStyleSheet(
            f"QFrame#productAIChatPanel {{ background: {card}; border-left: 1px solid {border}; }}"
        )
        self.header.setStyleSheet(
            f"QFrame#productAIHeader {{ background: {card}; border-bottom: 1px solid {border}; }}"
        )
        quick_style = f"background: {muted}; border-bottom: 1px solid {border};"
        self.quick_scroll.setStyleSheet(quick_style)
        self.quick_frame.setStyleSheet(quick_style)
        self.title_label.setStyleSheet(
            f"color: {text}; font-size: 11pt; font-weight: 700; border: none;"
        )
        self.context_label.setStyleSheet(
            f"color: {colors.get('text_secondary', '#636e72')}; background: {muted}; "
            f"border-bottom: 1px solid {border}; font-size: 8.5pt;"
        )
        self.more_actions_button.setStyleSheet(f"""
            QToolButton {{
                background: {card}; color: {text}; border: 1px solid {border};
                border-radius: 5px; padding: 4px 12px; font-weight: 600;
            }}
            QToolButton:hover {{ background: {muted}; border-color: #5865f2; }}
        """)
        self.more_actions_menu.setStyleSheet(f"""
            QMenu {{ background: {card}; color: {text}; border: 1px solid {border}; padding: 4px; }}
            QMenu::item {{ padding: 7px 22px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {muted}; }}
        """)
        self.chat.update_theme()
        for card in self.findChildren(QFrame, "aiProductCard"):
            self._style_product_card(card)
        for button in self.findChildren(ModernButton):
            button.update_theme()

    def shutdown(self):
        """Give the read-only insight worker time to finish before widget teardown."""
        worker = self._insight_worker
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.wait(1500)


class ProductAIChatDialog(QDialog):
    """Non-modal floating shell that keeps the Products page fully usable."""

    visibility_changed = pyqtSignal(bool)

    def __init__(self, parent=None, user_id=None, can_view_sensitive=True):
        super().__init__(parent)
        self.setObjectName("productAIChatDialog")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(500, 680)
        self.setMinimumSize(450, 540)
        self.setMaximumSize(620, 900)
        self._drag_offset = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        self.panel = ProductAIChatPanel(
            self,
            user_id=user_id,
            can_view_sensitive=can_view_sensitive,
        )
        self.panel.setMinimumWidth(0)
        self.panel.setMaximumWidth(16777215)
        self.panel.close_requested.connect(self.close)
        layout.addWidget(self.panel)

        self.panel.header.installEventFilter(self)
        self.panel.title_label.installEventFilter(self)
        self.update_theme()

    def eventFilter(self, watched, event):
        if watched in (self.panel.header, self.panel.title_label):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                return True
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        """Keep the Products toolbar state correct for every hide/close path."""
        self.visibility_changed.emit(False)
        super().hideEvent(event)

    def update_theme(self):
        colors = get_theme_colors()
        self.setStyleSheet(
            f"QDialog#productAIChatDialog {{ background: {colors.get('border', '#dfe3e8')}; "
            "border: 1px solid #5865f2; border-radius: 9px; }"
        )
        self.panel.update_theme()

    def shutdown(self):
        self.panel.shutdown()
