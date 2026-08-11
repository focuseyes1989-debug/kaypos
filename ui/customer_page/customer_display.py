# ui/customer_page/customer_display.py
import os
import re
from html import escape
from urllib.parse import parse_qs, quote, urlparse
from loguru import logger

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from models.database import connect_db
from utils.performance import get_performance_settings
from utils.paths import get_images_dir
from .customer_display_cart import CartDisplayWidget
from .customer_display_theme import get_display_palette, get_launcher_style
from .customer_display_utils import set_default_geometry, show_on_customer_monitor_fullscreen


try:
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtWebEngineCore import QWebEngineHttpRequest, QWebEngineSettings, QWebEngineUrlRequestInterceptor
except Exception:
    QByteArray = None
    QWebEngineHttpRequest = None
    QWebEngineSettings = None
    QWebEngineUrlRequestInterceptor = None


if QWebEngineUrlRequestInterceptor:
    class YouTubeRequestInterceptor(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            try:
                host = info.requestUrl().host().lower()
                if "youtube.com" in host or "youtube-nocookie.com" in host or "googlevideo.com" in host:
                    info.setHttpHeader(QByteArray(b"Referer"), QByteArray(b"https://www.youtube.com/"))
                    info.setHttpHeader(QByteArray(b"Origin"), QByteArray(b"https://www.youtube.com"))
            except Exception:
                pass
else:
    YouTubeRequestInterceptor = None


class CustomerDisplayWindow(QWidget):
    """Simple customer display: shop header, YouTube player, cart cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_maximized = False
        self.youtube_view = None
        self.youtube_placeholder = None
        self.youtube_interceptor = None
        self.youtube_fallback_pixmap = QPixmap()
        self.performance_settings = get_performance_settings()

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumSize(640, 420)
        self.setup_ui()
        self.apply_theme_style()
        set_default_geometry(self)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(500)

        self.load_shop_info()
        self.load_youtube_player()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        self.header_frame = QFrame()
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(64, 46)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.logo_label)

        shop_text_layout = QVBoxLayout()
        shop_text_layout.setContentsMargins(0, 0, 0, 0)
        shop_text_layout.setSpacing(2)
        self.shop_name_label = QLabel("ZAY POS")
        self.shop_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.shop_detail_label = QLabel("")
        self.shop_detail_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.shop_detail_label.setWordWrap(True)
        shop_text_layout.addWidget(self.shop_name_label)
        shop_text_layout.addWidget(self.shop_detail_label)
        header_layout.addLayout(shop_text_layout, 1)
        root.addWidget(self.header_frame)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        self.youtube_frame = QFrame()
        self.youtube_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        youtube_layout = QVBoxLayout(self.youtube_frame)
        youtube_layout.setContentsMargins(8, 8, 8, 8)
        youtube_layout.setSpacing(0)
        web_view_class = self._web_view_class() if self.performance_settings.customer_display_youtube_enabled else None
        if web_view_class:
            self.youtube_view = web_view_class()
            self._configure_youtube_view()
            youtube_layout.addWidget(self.youtube_view)
        else:
            self.youtube_placeholder = QLabel()
            self.youtube_placeholder.setObjectName("youtubeFallbackImage")
            self.youtube_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.youtube_placeholder.setWordWrap(True)
            self.youtube_placeholder.setScaledContents(False)
            self.youtube_placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            youtube_layout.addWidget(self.youtube_placeholder)
            if not self.performance_settings.customer_display_youtube_enabled:
                self._show_youtube_disabled_placeholder()
            else:
                self.youtube_placeholder.setText(
                    "YouTube player is unavailable.\nInstall PyQt6-WebEngine to enable playback."
                )
        youtube_stretch = 3 if not self.performance_settings.customer_display_youtube_enabled else 4
        columns.addWidget(self.youtube_frame, youtube_stretch)

        self.cart_frame = QFrame()
        self.cart_frame.setMinimumWidth(300)
        self.cart_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cart_layout = QVBoxLayout(self.cart_frame)
        cart_layout.setContentsMargins(10, 10, 10, 10)
        cart_layout.setSpacing(0)
        self.cart_display = CartDisplayWidget(self)
        cart_layout.addWidget(self.cart_display)
        columns.addWidget(self.cart_frame, 3)

        root.addLayout(columns, 1)

    def _web_view_class(self):
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            return QWebEngineView
        except Exception as exc:
            logger.warning(f"Customer display WebEngine unavailable: {exc}")
            return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (
            self.youtube_placeholder
            and not self.youtube_fallback_pixmap.isNull()
            and not self.performance_settings.customer_display_youtube_enabled
        ):
            scaled = self.youtube_fallback_pixmap.scaled(
                self.youtube_placeholder.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.youtube_placeholder.setPixmap(scaled)

    def _configure_youtube_view(self):
        try:
            page = self.youtube_view.page()
            profile = page.profile()
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
            settings = page.settings()
            if QWebEngineSettings and settings:
                settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
                settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
            if YouTubeRequestInterceptor:
                self.youtube_interceptor = YouTubeRequestInterceptor(profile)
                profile.setUrlRequestInterceptor(self.youtube_interceptor)
        except Exception as exc:
            logger.warning(f"Failed to configure customer display WebEngine: {exc}")

    def apply_theme_style(self):
        colors = get_display_palette()
        self.setStyleSheet(get_launcher_style())
        self.header_frame.setStyleSheet(f"""
            QFrame {{
                background: {colors['panel']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
        """)
        self.logo_label.setStyleSheet(f"""
            background: transparent;
            color: {colors['muted']};
            border: none;
            border-radius: 4px;
            font-size: 9pt;
            font-weight: 800;
        """)
        self.shop_name_label.setStyleSheet(f"""
            color: {colors['title_text']};
            font-size: 15pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        self.shop_detail_label.setStyleSheet(f"""
            color: {colors['muted']};
            font-size: 10.5pt;
            font-weight: 650;
            background: transparent;
            border: none;
        """)
        panel_style = f"""
            QFrame {{
                background: {colors['panel_alt']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
        """
        self.youtube_frame.setStyleSheet(panel_style)
        self.cart_frame.setStyleSheet(panel_style)
        if self.youtube_placeholder:
            self.youtube_placeholder.setStyleSheet(f"""
                color: {colors['muted']};
                font-size: 16pt;
                font-weight: 800;
                background: transparent;
                border: none;
            """)
        if self.cart_display:
            self.cart_display.apply_theme_style()

    def _settings(self):
        values = {}
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value
                FROM settings
                WHERE key IN (
                    'shop_name', 'shop_address', 'shop_phone', 'shop_logo',
                    'customer_display_youtube_url', 'youtube_url', 'shop_youtube_url'
                )
            """)
            values = dict(cursor.fetchall())
            conn.close()
        except Exception:
            pass
        return values

    def _market_image_path(self):
        return os.path.join(get_images_dir(), "market.png")

    def _show_youtube_disabled_placeholder(self):
        image_path = self._market_image_path()
        if self.youtube_view:
            from PyQt6.QtCore import QUrl
            image_url = QUrl.fromLocalFile(image_path).toString()
            colors = get_display_palette()
            self.youtube_view.setHtml(f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: {colors['panel_alt']};
    }}
    body {{
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      display: block;
    }}
  </style>
</head>
<body>
  <img src="{image_url}" alt="Market">
</body>
</html>""")
            return

        if not self.youtube_placeholder:
            return
        if os.path.exists(image_path):
            self.youtube_fallback_pixmap = QPixmap(image_path)
            scaled = self.youtube_fallback_pixmap.scaled(
                self.youtube_frame.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.youtube_placeholder.setPixmap(scaled)
            self.youtube_placeholder.setText("")
        else:
            self.youtube_placeholder.setPixmap(QPixmap())
            self.youtube_placeholder.setText("YouTube is disabled in Performance settings.")

    def load_shop_info(self):
        settings = self._settings()
        shop_name = settings.get("shop_name") or "ZAY POS"
        address = settings.get("shop_address") or ""
        phone = settings.get("shop_phone") or ""
        details = " | ".join([part for part in (address, phone) if part])
        self.shop_name_label.setText(shop_name)
        self.shop_detail_label.setText(details)

        logo_path = settings.get("shop_logo") or ""
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaled(
                    60,
                    42,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                self.logo_label.setText("")
                return
        self.logo_label.setPixmap(QPixmap())
        self.logo_label.setText("Logo")

    def _youtube_embed_url(self, raw_url):
        raw_url = (raw_url or "").strip()
        if not raw_url:
            return "https://www.youtube.com/embed/videoseries?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI&autoplay=1&mute=1&loop=1"
        if "youtube.com/embed/" in raw_url or "youtube-nocookie.com/embed/" in raw_url:
            return self._with_youtube_params(raw_url)
        video_match = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})", raw_url)
        if video_match:
            video_id = video_match.group(1)
            start = self._youtube_start_seconds(raw_url)
            start_param = f"&start={start}" if start else ""
            return f"https://www.youtube.com/embed/{video_id}?autoplay=1&mute=1&loop=1&playlist={video_id}&rel=0&origin={quote('https://www.youtube.com', safe='')}{start_param}"
        list_match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", raw_url)
        if list_match:
            return f"https://www.youtube.com/embed/videoseries?list={list_match.group(1)}&autoplay=1&mute=1&loop=1&rel=0&origin={quote('https://www.youtube.com', safe='')}"
        return None

    def _youtube_watch_url(self, raw_url):
        raw_url = (raw_url or "").strip()
        if not raw_url:
            return "https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI&autoplay=1&mute=1"

        video_match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{6,})", raw_url)
        if video_match:
            video_id = video_match.group(1)
            start = self._youtube_start_seconds(raw_url)
            start_param = f"&t={start}s" if start else ""
            return f"https://www.youtube.com/watch?v={video_id}&autoplay=1&mute=1{start_param}"

        list_match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", raw_url)
        if list_match:
            return f"https://www.youtube.com/playlist?list={list_match.group(1)}&autoplay=1&mute=1"

        return None

    def _with_youtube_params(self, url):
        separator = "&" if "?" in url else "?"
        params = []
        for key, value in (
            ("autoplay", "1"),
            ("mute", "1"),
            ("rel", "0"),
            ("origin", quote("https://www.youtube.com", safe="")),
        ):
            if f"{key}=" not in url:
                params.append(f"{key}={value}")
        return url if not params else f"{url}{separator}{'&'.join(params)}"

    def _youtube_start_seconds(self, raw_url):
        try:
            query = parse_qs(urlparse(raw_url).query)
            value = (query.get("t") or query.get("start") or [""])[0]
            match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", value)
            if match and value:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                return hours * 3600 + minutes * 60 + seconds
            return int(value) if value else 0
        except Exception:
            return 0

    def _youtube_html(self, embed_url):
        safe_url = escape(embed_url, quote=True)
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <style>
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: #000;
    }}
    iframe {{
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
    }}
  </style>
</head>
<body>
  <iframe
    src="{safe_url}"
    title="Customer display YouTube player"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    referrerpolicy="strict-origin-when-cross-origin"
    allowfullscreen>
  </iframe>
</body>
</html>"""

    def _message_html(self, title, message):
        colors = get_display_palette()
        return f"""<!doctype html>
<html>
<body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:{colors['panel_alt']};font-family:Arial,sans-serif;">
  <div style="text-align:center;color:{colors['muted']};padding:32px;">
    <div style="font-size:22px;font-weight:800;color:{colors['title_text']};margin-bottom:10px;">{escape(title)}</div>
    <div style="font-size:15px;font-weight:650;line-height:1.5;">{escape(message)}</div>
  </div>
</body>
</html>"""

    def load_youtube_player(self):
        self.performance_settings = get_performance_settings(refresh=True)
        if not self.performance_settings.customer_display_youtube_enabled:
            self._show_youtube_disabled_placeholder()
            return
        if not self.youtube_view:
            return
        from PyQt6.QtCore import QUrl
        settings = self._settings()
        raw_url = (
            settings.get("customer_display_youtube_url")
            or settings.get("youtube_url")
            or settings.get("shop_youtube_url")
            or ""
        )
        watch_url = self._youtube_watch_url(raw_url)
        if not watch_url:
            self.youtube_view.setHtml(
                self._message_html(
                    "YouTube link is not a video",
                    "Please paste a YouTube video, Shorts, playlist, or embed link in Settings.",
                ),
                QUrl("https://www.youtube.com/"),
            )
            logger.warning(f"Invalid customer display YouTube URL: {raw_url}")
            return
        if QWebEngineHttpRequest and QByteArray:
            request = QWebEngineHttpRequest(QUrl(watch_url))
            request.setHeader(QByteArray(b"Referer"), QByteArray(b"https://www.youtube.com/"))
            request.setHeader(QByteArray(b"Origin"), QByteArray(b"https://www.youtube.com"))
            self.youtube_view.load(request)
            return
        self.youtube_view.setUrl(QUrl(watch_url))

    def refresh_display(self):
        if not self.parent_window or not hasattr(self.parent_window, "cart_widget"):
            return
        self.cart_display.update_display(self.parent_window.cart_widget.get_cart())

    def toggle_maximize(self):
        self.is_maximized = not self.is_maximized
        if self.is_maximized:
            show_on_customer_monitor_fullscreen(self)
        else:
            self.showNormal()
            set_default_geometry(self)

    def close_display(self):
        self.refresh_timer.stop()
        self.close()
        if self.parent_window and hasattr(self.parent_window, "customer_display_closed"):
            self.parent_window.customer_display_closed()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.isFullScreen():
            show_on_customer_monitor_fullscreen(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_display()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_maximize()
        super().keyPressEvent(event)

    def retranslateUi(self):
        if hasattr(self, "cart_display"):
            self.cart_display.retranslate_ui()
