!EtherNet-IP for VM
<img width="1079" height="538" alt="reame" src="https://github.com/lister2000/EtherNet-IP-/blob/master/%E7%95%8C%E9%9D%A2.png" />

📦 VM EtherNet/IP Tag Simulator (PLC 模拟与标签管理工具)
这是一个基于 Python + PyQt5 开发的轻量级 EtherNet/IP (CIP) 服务端（从站）模拟器。

由于海康 VM（VisionMaster）在作为 EtherNet/IP 客户端（TcpClient）时，无法直接接收外部发来的写入（Write Tag），只能通过轮询读取（Read Tag）获取数据。本工具专门用于解决这一痛点，它可以模拟一个真实 PLC，让 VM 能够成功读取到指定标签的数据。同时，本工具也支持主动向 VM 发送写入请求。

✨ 核心特性

🔄 动态标签管理：支持在界面上实时创建、修改和删除标签（CRUD）。

🏷️ 层级路径支持：完美支持带点号（.）的层级标签（如 Stn05CameraHKVision.Trigger），程序会自动将其解析为 CIP 协议中的多段符号路径。

🔢 多数据类型：每个标签均可独立配置数据类型，支持 INT16、DINT32、REAL（浮点数）。

⚡ 双工通信：

自动应答：当 VM 发起轮询读取时，程序自动解析目标标签并返回最新值。

主动推送：支持在界面上手动修改标签值，并主动向 VM 发送 Write Tag 报文。

📝 实时报文日志：带十六进制（HEX）报文打印，方便开发调试时排查协议问题。

🛠️ 环境准备
确保你的电脑上安装了 Python 3.8 或更高版本。

bash
# 1. 克隆或下载本项目代码
# 2. 安装依赖库
pip install PyQt5
🚀 快速开始
启动程序：

bash
python main.py
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

🧠 技术实现原理（CIP 协议解析）
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

