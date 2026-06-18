-- AI Hotspot Monitor 数据库初始化脚本
-- 字符集配置
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `ai_hotspot_monitor`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `ai_hotspot_monitor`;

-- 设置时区
SET GLOBAL time_zone = '+8:00';
