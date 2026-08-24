"""Lightweight, dependency-free chart widgets for the Car dashboard."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class HorizontalBarChart(QWidget):
    def __init__(self, color="#27c992", parent=None):
        super().__init__(parent);self.color=QColor(color);self.data=[];self.setMinimumHeight(190)

    def set_data(self, data):
        self.data=[(str(label),int(value)) for label,value in data if int(value)>=0];self.update()

    def paintEvent(self,event):
        super().paintEvent(event);p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        rect=self.rect().adjusted(12,10,-12,-10)
        if not self.data:
            p.setPen(QColor("#99a8bd"));p.drawText(rect,Qt.AlignmentFlag.AlignCenter,"No data for this date range");return
        maximum=max(1,max(value for _label,value in self.data));row_height=max(24,rect.height()//len(self.data));label_width=min(145,max(80,rect.width()//3));bar_left=rect.left()+label_width;bar_width=max(30,rect.right()-bar_left-40)
        font=QFont(self.font());font.setPointSize(9);p.setFont(font)
        for index,(label,value) in enumerate(self.data):
            y=rect.top()+index*row_height;label_rect=QRectF(rect.left(),y,label_width-8,row_height);p.setPen(QColor("#d7e2f1"));p.drawText(label_rect,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,p.fontMetrics().elidedText(label,Qt.TextElideMode.ElideRight,int(label_rect.width())))
            track=QRectF(bar_left,y+row_height*.24,bar_width,row_height*.52);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor("#253243"));p.drawRoundedRect(track,4,4)
            fill=QRectF(track.x(),track.y(),max(3,track.width()*value/maximum),track.height());p.setBrush(self.color);p.drawRoundedRect(fill,4,4);p.setPen(QColor("#edf2ff"));p.drawText(QRectF(track.right()+6,y,34,row_height),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,str(value))


class CompletenessChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.complete=0;self.incomplete=0;self.setMinimumHeight(190)

    def set_data(self,complete,incomplete):
        self.complete=int(complete);self.incomplete=int(incomplete);self.update()

    def paintEvent(self,event):
        super().paintEvent(event);p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing,True);total=self.complete+self.incomplete
        if not total:
            p.setPen(QColor("#99a8bd"));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"No data for this date range");return
        size=min(self.width()//2,self.height()-34);donut=QRectF(24,(self.height()-size)/2,size,size);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor("#27c992"));p.drawPie(donut,90*16,-round(360*16*self.complete/total));p.setBrush(QColor("#ff858d"));p.drawPie(donut,(90-round(360*self.complete/total))*16,-round(360*16*self.incomplete/total));inner=donut.adjusted(size*.25,size*.25,-size*.25,-size*.25);p.setBrush(QColor("#151c2a"));p.drawEllipse(inner);p.setPen(QColor("#ffffff"));font=QFont(self.font());font.setBold(True);font.setPointSize(13);p.setFont(font);p.drawText(inner,Qt.AlignmentFlag.AlignCenter,f"{total:,}")
        x=donut.right()+28;y=self.height()/2-28
        for label,value,color in (("Complete",self.complete,"#27c992"),("Incomplete",self.incomplete,"#ff858d")):
            p.setBrush(QColor(color));p.setPen(Qt.PenStyle.NoPen);p.drawRoundedRect(QRectF(x,y,12,12),3,3);p.setPen(QColor("#d7e2f1"));p.drawText(QRectF(x+20,y-5,self.width()-x-24,24),Qt.AlignmentFlag.AlignVCenter,f"{label}: {value:,}");y+=36
