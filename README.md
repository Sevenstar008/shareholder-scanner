# 🗄️ A 股股东检索系统

> 本地化 A 股十大流通股东数据检索工具，支持多股东匹配、智能排序、Excel 导出

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特点

- 🔍 **多股东检索**：支持同时搜索多个股东名字，逗号分隔
- 🏆 **智能排序**：匹配多个股东的股票自动排在前面
- 💾 **本地数据库**：SQLite 存储，毫秒级检索响应
- 📊 **Excel 导出**：一键导出搜索结果或全量数据
- 🔄 **定期更新**：财报季后可更新最新股东数据
- 🌐 **网页界面**：无需命令行，浏览器即可操作
- 🔐 **完全免费**：基于公开数据，无任何费用

---

## 📦 快速开始

### 环境要求

- Python 3.8 或更高版本
- Windows / Mac / Linux

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/shareholder-scanner.git
cd shareholder-scanner
