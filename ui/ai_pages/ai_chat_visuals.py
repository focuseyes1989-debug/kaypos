"""Compact, read-only result visualizations embedded in AI Chat messages."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.themes.theme_manager import get_theme_colors


class AIBarChart(QWidget):
    def __init__(self,bars,parent=None):
        super().__init__(parent);self.bars=list(bars or [])[:8]
        self.setMinimumHeight(max(70,len(self.bars)*30+12))

    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.bars:return
        colors=get_theme_colors();painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text_color=QColor(colors.get("text","#2d3436"));muted=QColor(colors.get("text_secondary","#636e72"))
        track=QColor(colors.get("border","#dfe6e9"));bar_color=QColor(colors.get("primary","#5865f2"))
        maximum=max((float(item.get("value") or 0) for item in self.bars),default=0) or 1
        label_width=min(150,max(80,int(self.width()*0.28)));value_width=82;available=max(30,self.width()-label_width-value_width-18)
        row_height=max(26,int((self.height()-8)/max(1,len(self.bars))))
        for index,item in enumerate(self.bars):
            top=5+index*row_height;value=max(0,float(item.get("value") or 0));width=int(available*value/maximum)
            painter.setPen(QPen(text_color));painter.drawText(2,top,label_width-6,row_height-4,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,str(item.get("label") or "")[:22])
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(track);painter.drawRoundedRect(label_width,top+6,available,12,6,6)
            painter.setBrush(QColor(item.get("color") or bar_color));painter.drawRoundedRect(label_width,top+6,width,12,6,6)
            painter.setPen(QPen(muted));painter.drawText(label_width+available+7,top,value_width,row_height-4,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,str(item.get("display") or _number(value)))
        painter.end()


class AIResultVisual(QFrame):
    def __init__(self,spec,parent=None):
        super().__init__(parent);self.spec=spec or {};self.card_frames=[];self._setup()

    def _setup(self):
        layout=QVBoxLayout(self);layout.setContentsMargins(0,4,0,2);layout.setSpacing(8)
        title=self.spec.get("title")
        if title:
            self.title_label=QLabel(str(title));layout.addWidget(self.title_label)
        cards=self.spec.get("cards") or []
        if cards:
            row=QHBoxLayout();row.setSpacing(7)
            for card in cards[:4]:
                frame=QFrame();box=QVBoxLayout(frame);box.setContentsMargins(9,6,9,6);box.setSpacing(1)
                label=QLabel(str(card.get("label") or ""));value=QLabel(str(card.get("value") or "0"))
                value.setObjectName("visualValue");label.setObjectName("visualLabel");box.addWidget(value);box.addWidget(label)
                row.addWidget(frame,1);self.card_frames.append(frame)
            layout.addLayout(row)
        bars=self.spec.get("bars") or []
        if bars:
            self.chart=AIBarChart(bars);layout.addWidget(self.chart)
        self.update_theme()

    def update_theme(self):
        colors=get_theme_colors();self.setStyleSheet("background: transparent; border: none;")
        if hasattr(self,"title_label"):
            self.title_label.setStyleSheet(f"color:{colors.get('text','#2d3436')};font-weight:600;background:transparent;")
        for frame in self.card_frames:
            frame.setStyleSheet(f"QFrame{{background:{colors.get('background','#f7f8fa')};border:1px solid {colors.get('border','#dfe6e9')};border-radius:8px;}}")
            for label in frame.findChildren(QLabel):
                if label.objectName()=="visualValue":label.setStyleSheet(f"color:{colors.get('primary','#5865f2')};font-size:13pt;font-weight:700;background:transparent;border:none;")
                else:label.setStyleSheet(f"color:{colors.get('text_secondary','#636e72')};font-size:8.5pt;background:transparent;border:none;")
        if hasattr(self,"chart"):self.chart.update()


def _number(value):
    value=float(value or 0)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"
