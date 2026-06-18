from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from backend.common.mysql import Base


class FetchQuotaConfig(Base):
    """数据源抓取配额配置模型"""

    __tablename__ = "fetch_quota_config"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    twitter = Column(Integer, nullable=False, default=8, comment="Twitter 配额")
    youtube = Column(Integer, nullable=False, default=8, comment="YouTube 配额")
    bilibili = Column(Integer, nullable=False, default=3, comment="Bilibili 配额")
    twitterEnabled = Column("twitter_enabled", Boolean, nullable=False, default=True, comment="Twitter 是否启用")
    youtubeEnabled = Column("youtube_enabled", Boolean, nullable=False, default=True, comment="YouTube 是否启用")
    bilibiliEnabled = Column("bilibili_enabled", Boolean, nullable=False, default=True, comment="Bilibili 是否启用")
    douyin = Column(Integer, nullable=False, default=3, comment="抖音 配额")
    douyinEnabled = Column("douyin_enabled", Boolean, nullable=False, default=True, comment="抖音 是否启用")
    bing = Column(Integer, nullable=False, default=2, comment="Bing 配额")
    bingEnabled = Column("bing_enabled", Boolean, nullable=False, default=True, comment="Bing 是否启用")
    sogou = Column(Integer, nullable=False, default=1, comment="搜狗 配额")
    sogouEnabled = Column("sogou_enabled", Boolean, nullable=False, default=True, comment="搜狗 是否启用")
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return (f"<FetchQuotaConfig(twitter={self.twitter}/{self.twitterEnabled}, "
                f"youtube={self.youtube}/{self.youtubeEnabled}, "
                f"bilibili={self.bilibili}/{self.bilibiliEnabled}, "
                f"douyin={self.douyin}/{self.douyinEnabled}, "
                f"bing={self.bing}/{self.bingEnabled}, "
                f"sogou={self.sogou}/{self.sogouEnabled})>")
