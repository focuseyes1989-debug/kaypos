"""Compact, read-only result visualizations embedded in AI Chat messages."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

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


class AITrendChart(QWidget):
    """Small theme-aware multi-series line chart for dated Dashboard points."""

    def __init__(self,series,parent=None):
        super().__init__(parent);self.series=list(series or [])[:4];self.setMinimumHeight(190)

    def paintEvent(self,event):
        super().paintEvent(event)
        available=[float(point.get("value") or 0) for series in self.series for point in series.get("points",[])]
        if not available:return
        colors=get_theme_colors();painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        muted=QColor(colors.get("text_secondary","#636e72"));grid=QColor(colors.get("border","#dfe6e9"))
        left,top,right,bottom=48,28,self.width()-12,self.height()-28;width=max(10,right-left);height=max(10,bottom-top)
        minimum=min(0,min(available));maximum=max(0,max(available));span=maximum-minimum or 1
        painter.setPen(QPen(grid,1))
        for index in range(5):
            y=top+height*index/4;painter.drawLine(left,int(y),right,int(y))
            value=maximum-span*index/4;painter.setPen(QPen(muted));painter.drawText(0,int(y)-8,left-5,16,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,_short(value));painter.setPen(QPen(grid,1))
        max_points=max((len(series.get("points",[])) for series in self.series),default=1)
        for series_index,series in enumerate(self.series):
            points=series.get("points",[]);color=QColor(series.get("color") or colors.get("primary","#5865f2"));path=QPainterPath()
            for index,point in enumerate(points):
                x=left+(width*index/max(1,max_points-1));y=top+height*(maximum-float(point.get("value") or 0))/span
                if index==0:path.moveTo(x,y)
                else:path.lineTo(x,y)
            painter.setPen(QPen(color,2));painter.drawPath(path)
            painter.setBrush(color)
            for index,point in enumerate(points):
                x=left+(width*index/max(1,max_points-1));y=top+height*(maximum-float(point.get("value") or 0))/span;painter.drawEllipse(int(x)-3,int(y)-3,6,6)
            painter.setPen(QPen(color));painter.drawText(left+series_index*120,2,116,20,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,str(series.get("label") or "")[:18])
        labels=next((series.get("points",[]) for series in self.series if series.get("points")),[])
        if labels:
            painter.setPen(QPen(muted));painter.drawText(left,bottom+5,width//2,18,Qt.AlignmentFlag.AlignLeft,str(labels[0].get("label") or ""));painter.drawText(left+width//2,bottom+5,width//2,18,Qt.AlignmentFlag.AlignRight,str(labels[-1].get("label") or ""))
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
            grid=QGridLayout();grid.setHorizontalSpacing(7);grid.setVerticalSpacing(7)
            columns=min(4,max(1,len(cards)))
            for index,card in enumerate(cards[:12]):
                frame=QFrame();box=QVBoxLayout(frame);box.setContentsMargins(9,6,9,6);box.setSpacing(1)
                label=QLabel(str(card.get("label") or ""));value=QLabel(str(card.get("value") or "0"))
                value.setObjectName("visualValue");label.setObjectName("visualLabel")
                value.setWordWrap(True);label.setWordWrap(True)
                frame.setProperty("accentColor",str(card.get("color") or ""))
                box.addWidget(value);box.addWidget(label)
                grid.addWidget(frame,index//columns,index%columns);self.card_frames.append(frame)
            layout.addLayout(grid)
        bars=self.spec.get("bars") or []
        if bars:
            self.chart=AIBarChart(bars);layout.addWidget(self.chart)
        series=self.spec.get("series") or []
        if series:
            self.trend_chart=AITrendChart(series);layout.addWidget(self.trend_chart)
        self.update_theme()

    def update_theme(self):
        colors=get_theme_colors();self.setStyleSheet("background: transparent; border: none;")
        if hasattr(self,"title_label"):
            self.title_label.setStyleSheet(f"color:{colors.get('text','#2d3436')};font-weight:600;background:transparent;")
        for frame in self.card_frames:
            accent=frame.property("accentColor") or colors.get('primary','#5865f2')
            frame.setStyleSheet(f"QFrame{{background:{colors.get('background','#f7f8fa')};border:1px solid {accent};border-radius:9px;}}")
            for label in frame.findChildren(QLabel):
                if label.objectName()=="visualValue":label.setStyleSheet(f"color:{accent};font-size:13pt;font-weight:700;background:transparent;border:none;")
                else:label.setStyleSheet(f"color:{colors.get('text_secondary','#636e72')};font-size:8.5pt;background:transparent;border:none;")
        if hasattr(self,"chart"):self.chart.update()
        if hasattr(self,"trend_chart"):self.trend_chart.update()


def _number(value):
    value=float(value or 0)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def _short(value):
    value=float(value or 0)
    if abs(value)>=1_000_000:return f"{value/1_000_000:.1f}M"
    if abs(value)>=1_000:return f"{value/1_000:.0f}K"
    return f"{value:.0f}"
