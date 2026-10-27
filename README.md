# 工业通信实战经验：VM EtherNet/IP & CIP 协议对接避坑指南📘 

[![GitHub stars](https://img.shields.io/github/stars/lister2000/EtherNet-IP-?style=social)](https://github.com/lister2000/EtherNet-IP-/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/lister2000/EtherNet-IP-?style=social)](https://github.com/lister2000/EtherNet-IP-/network/members)
[![GitHub last commit](https://img.shields.io/github/last-commit/lister2000/EtherNet-IP-)](https://github.com/lister2000/EtherNet-IP-/commits/master)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-green)](https://pypi.org/project/PyQt5/)
[![EtherNet/IP](https://img.shields.io/badge/Protocol-EtherNet%2FIP-orange)](https://github.com/lister2000/EtherNet-IP-)

> 🚀 回顾这次从“连不上”到“彻底掌控”的完整历程，中间踩过了非常多工业通信和 Python 编程的坑。把这些经验总结下来，对做类似的工控对接会非常有帮助。
由于海康 VM（VisionMaster）在作为 EtherNet/IP 客户端（TcpClient）时，无法直接接收外部发来的写入（Write Tag），只能通过轮询读取（Read Tag）获取数据。本工具专门用于解决这一痛点，它可以模拟一个真实 PLC，让 VM 能够成功读取到指定标签的数据。同时，本工具也支持主动向 VM 发送写入请求。
VM EtherNet/IP Tag Simulator (PLC 模拟与标签管理工具)这是一个基于 Python + PyQt5 开发的轻量级 EtherNet/IP (CIP) 服务端（从站）模拟器。
这套代码和其中的逻辑，不仅能用来模拟这个相机标签，以后如果遇到任何上位机（SCADA、MES）或者 PLC 的 EtherNet/IP 对接，都能直接复用！

## 📖 目录导航

- [📖项目经验](#-一、项目经验)
- [📖快速安装](#-二、快速安装)
- [📖技术原理](#-三、技术原理)
---


## 🧩 一、项目经验
本文档总结了在使用海康 VisionMaster作为 EtherNet/IP 客户端（TcpClient），并使用 Python 模拟 PLC 服务端（Adapter）进行双向通信时，所积累的底层协议原理、调试技巧与开发经验。

### 🧩 1.1、协议层经验（EtherNet/IP & CIP）
TCP 连通 ≠ 协议连通:
即使 TCP 三次握手成功，VM 发来 RegisterSession，也不代表真正建立通信。这只是“敲门”，如果不回 RegisterSession 的成功响应，VM 会一直重试并最终断开。
角色反转是核心:
VM 的 TcpClient 模式意味着 VM 是主动方。所以你的 Python 程序不能去连它，必须作为 TCP 服务端（Server） 监听端口（默认 44818），等 VM 来连。
读懂底层服务码（Service Code）:
0x0065：RegisterSession（注册会话）
0x006F：SendRRData（封装显式报文，读写都在这里）
0x4D：Write Tag（写标签）
0x52 / 0x4C：Read Tag（读标签）。你之前遇到的“未处理 0x52”，就是因为 VM 实际发的读请求带了路由信息，服务码表现成了 0x52，直接“抓包就回”是最稳妥的。
数据类型必须与报文严格匹配:
INT16 对应类型码 0x00C3，长度 2 字节。
DINT32 对应类型码 0x00C4，长度 4 字节。
REAL 对应类型码 0x00CA，长度 4 字节（IEEE 754 浮点数）。
类型码或字节数对不上，VM 会报错或解析成乱码。
层级分隔符“. 点号”:
这是最容易踩的坑。Stn05CameraHKVision.Trigger 在 CIP 里不是一个长字符串，而是两个独立的 0x91 符号段。打包和解析时，必须按 . 拆分，并把每个段补齐到偶数长度（\x00 补位）。
1.1.6、解析响应必须“随波逐流”:
最初想主动发 Write Tag 让 VM 更新，但 VM 的配置是“轮询读取”，它根本不看写入报文。它只看回复读请求时的数据是什么。 所以，“改了不生效”的根本原因是只改了下发报文，没改内存字典里用于回复读取请求的值。

### 🧩1.2、软件与 UI 层经验（PyQt5）
表格数据的“提交”时机:
在 PyQt5 的 QTableWidget 里，用户双击单元格输入内容后，必须按回车或点击其他单元格，数据才会提交并触发 itemChanged 信号。如果不提醒用户，他们改完直接去点发送，程序拿到的还是旧值。
精准刷新，避免连带反应
修改一个标签的值时，如果用 setRowCount(0) 全表刷新，会打断用户正在进行的其他操作，甚至导致信号死循环。应该只更新对应的那一格，或者用 blockSignals(True) 临时屏蔽信号后再刷新。
 线程与 UI 的安全交互
网络接收是在子线程中进行的。所有的界面更新（追加文本、弹窗）都必须通过 pyqtSignal 发回主线程，否则程序会崩溃或报 QTextCursor 之类的警告。

### 🧩1.3、调试排查

端口冲突：如果 44818 被 RSLinx 等软件占用，需要修改监听端口，同时 VM 里的目标端口也要同步改。
调试排查的终极手段
抓包（Wireshark / pktmon）
当“猜不出”对方发了什么时，唯一的真理就是抓包。看 VM 发来的十六进制数据，能瞬间定位服务码、长度、路径解析是否正确。
保留错误日志
像 [!] 收到未处理的 CIP 服务码: 0x52 这种日志，是排查问题的金矿。程序不要因为不认识就崩溃或静默，一定要打印出来。
“3721”回包法
在协议解析还不完美时（比如搞不清路径解析细节），最有效的测试手段就是：只要收到请求，直接构造一个可能对的响应发回去。只要能通一次，再顺藤摸瓜修补细节。

## ✨ 二、软件核心特性

🔄 动态标签管理：支持在界面上实时创建、修改和删除标签（CRUD）。

🏷️ 层级路径支持：完美支持带点号（.）的层级标签（如 Stn05CameraHKVision.Trigger），程序会自动将其解析为 CIP 协议中的多段符号路径。

🔢 多数据类型：每个标签均可独立配置数据类型，支持 INT16、DINT32、REAL（浮点数）。

⚡ 双工通信：

自动应答：当 VM 发起轮询读取时，程序自动解析目标标签并返回最新值。

主动推送：支持在界面上手动修改标签值，并主动向 VM 发送 Write Tag 报文。

📝 实时报文日志：带十六进制（HEX）报文打印，方便开发调试时排查协议问题。

## 🚀 二、快速安装
📦环境准备：确保你的电脑上安装了 Python 3.8 或更高版本。
bash
1. 克隆或下载本项目代码
2. 安装依赖库
pip install PyQt5
启动程序：
bash
python VmTools.py
配置连接：

默认监听 IP 为 127.0.0.1，端口为 44818（如果被占用可修改）。

点击界面上的 “▶ 启动监听”。

连接 VM：

打开海康 VM 软件。

在通信管理中新建 EtherNet/IP CIP 设备。

通信方式选择 TcpClient，目标 IP 填 127.0.0.1，端口填 44818。

配置你需要读取的标签（如 CameraHKVision.Trigger）。

标签配置：

在工具的表格中，点击 “+ 创建标签” 输入标签名和类型。

双击表格中的“当前值”即可直接修改数据，按回车生效。

VM 端即可立刻读取到最新数据。

## 📦 三、技术原理
本项目在底层直接使用 Python socket 实现了 CIP 协议的核心部分：
RegisterSession (0x65)：应答 VM 的握手请求，建立会话。
SendRRData (0x6F)：封装显式报文的载体。
Read Tag (0x4C / 0x52)：解析 VM 发来的路径段，提取标签名并打包对应数据类型的响应。
Write Tag (0x4D)：支持主动下发。
CIP 路径解析：对于 A.B 形式的标签，代码会将其自动拆分为两个 0x91 符号段（ANSI Extended Symbol Segment），并自动补齐偶数长度（\x00）。


⚠️ 常见问题
VM 端显示数据不对，出现 [01][00][02][00] 等多余前缀：
这是因为 VM 端在配置设备管理时，预留了槽号（Slot）或字节长度导致的。建议将 VM 设备管理中的“字节长度”改为与实际数据长度一致（如 INT16 填 2），或者在工具里调整返回的字节组装顺序。

端口 44818 被占用：
可能电脑上运行了 RSLinx、FactoryTalk 等罗克韦尔软件，请关闭它们或更改本程序的监听端口。

📄 开源协议
本项目基于 MIT License 开源，可自由用于个人学习或商业测试环境。

