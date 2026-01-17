# 阿里云 ESA DDNS 自动更新服务

一个基于 **Python + 阿里云 ESA API** 的 DDNS 自动更新服务，支持 **整点定时更新、手动触发、彩色终端输出、日志记录与优雅退出**，适合长期后台运行。

## ✨ 功能特性

* 🌐 **自动获取本机公网 IP**
* 🔁 **对比并自动更新阿里云 ESA 域名记录**
* ⏰ **每小时整点自动执行 DDNS 更新**
* ▶ **启动时立即执行一次**
* 🖥 **交互式命令行控制**
* 🎨 **彩色终端输出（状态清晰）**
* 📄 **完整日志记录（ddns_updater.log）**
* 🛑 **支持 Ctrl+C / SIGTERM 优雅退出**
* 🔒 **配置文件方式管理 AccessKey**

---

## 📦 运行环境

* Python **3.9+**（推荐 3.10 / 3.11）
* 操作系统：

  * Windows
  * Linux（服务器 / Docker 均可）

---

## 📥 安装依赖

```bash
pip install -r requirements.txt
```
---

## ⚙ 配置文件

程序默认读取当前目录下的 `config.yml`。

### 示例 `config.yml`

```yaml
aliyun:
  access_key_id: YOUR_ACCESS_KEY_ID
  access_key_secret: YOUR_ACCESS_KEY_SECRET
  region: cn-hangzhou
  record_id: 域名ID（需要自己获取）
```

字段说明：

| 字段                | 说明                        |
| ----------------- | ------------------------- |
| access_key_id     | 阿里云 AccessKey ID          |
| access_key_secret | 阿里云 AccessKey Secret      |
| region            | ESA 所在区域（一般为 cn-hangzhou） |
| record_id         | ESA 域名记录 ID               |

---

## 🚀 启动方式

```bash
python main.py
```

启动后将会：

1. 初始化日志与信号处理
2. 启动交互式命令行线程
3. **立即执行一次 DDNS 更新**
4. 等待到下一个整点执行下一次

---

## 🧭 命令行交互

启动后可在终端中输入以下命令：

| 命令          | 作用                |
| ----------- | ----------------- |
| start       | 立即执行一次 DDNS 扫描与更新 |
| status      | 查看当前运行状态与下次执行时间   |
| help        | 显示帮助信息            |
| clear       | 清空终端              |
| exit / quit | 退出程序              |

示例：

```
DDNS> start
DDNS> status
DDNS> exit
```

---

## 📝 日志说明

* 日志文件：`ddns_updater.log`
* 记录内容包括：

  * IP 获取结果
  * 记录查询与更新结果
  * 错误与异常信息
  * 定时执行时间点

日志为 **无颜色纯文本**，适合长期留存与分析。

---

## 🔄 工作流程

```text
启动程序
  ├─ 立即执行一次 DDNS 更新
  ├─ 等待至下一个整点
  ├─ 每小时整点自动执行
  ├─ 支持随时手动触发
  └─ 接收退出信号后优雅停止
```

---

## ⚠ 注意事项

* AccessKey 请妥善保管，**不要提交到公开仓库**
* record_id 需要提前在阿里云 ESA 控制台获取
* 若用于长期运行，建议：

  * Linux：`systemd`
  * Docker：`restart: always`
  * Windows：任务计划程序（需启用控制台）

