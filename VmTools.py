import sys
import socket
import threading
import datetime
import struct
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QMessageBox, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt

class Signaller(QObject):
    log_signal = pyqtSignal(str)
    recv_signal = pyqtSignal(str)

class EnipServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VM EtherNet/IP 标签管理器 (支持层级路径)")
        self.resize(1000, 850)
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.session_handle = 0x00000001
        
        self.tags = {
            "Stn05CameraHKVision.Trigger": {"value": 2, "type": "INT16"},
            "TAG1": {"value": 2, "type": "INT16"}
        }

        self.signaller = Signaller()
        self.signaller.log_signal.connect(self._append_log)
        self.signaller.recv_signal.connect(self._append_recv)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 1. 连接与监听配置
        cfg_group = QGroupBox("连接配置")
        cfg_layout = QGridLayout(cfg_group)
        cfg_layout.addWidget(QLabel("监听 IP:"), 0, 0)
        self.ip_edit = QLineEdit("127.0.0.1")
        cfg_layout.addWidget(self.ip_edit, 0, 1)
        cfg_layout.addWidget(QLabel("端口:"), 0, 2)
        self.port_edit = QLineEdit("44818")
        cfg_layout.addWidget(self.port_edit, 0, 3)
        self.start_btn = QPushButton("启动监听")
        self.start_btn.clicked.connect(self._start)
        cfg_layout.addWidget(self.start_btn, 0, 4)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        cfg_layout.addWidget(self.stop_btn, 0, 5)
        main_layout.addWidget(cfg_group)

        # 2. 状态
        status_group = QGroupBox("状态")
        status_layout = QHBoxLayout(status_group)
        self.status_label = QLabel("未启动")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addWidget(status_group)

        # 3. 标签管理区
        tag_group = QGroupBox("标签管理 (带点的标签会自动按层级拆分路径)")
        tag_layout = QVBoxLayout(tag_group)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("新建标签名:"))
        self.new_tag_edit = QLineEdit("Stn06CameraHKVision.Trigger")
        input_layout.addWidget(self.new_tag_edit)
        
        input_layout.addWidget(QLabel("类型:"))
        self.new_type_combo = QComboBox()
        self.new_type_combo.addItems(["INT16", "DINT32", "REAL"])
        input_layout.addWidget(self.new_type_combo)
        
        input_layout.addWidget(QLabel("初始值:"))
        self.new_val_edit = QLineEdit("3")
        input_layout.addWidget(self.new_val_edit)
        
        self.add_btn = QPushButton("创建标签")
        self.add_btn.clicked.connect(self._create_tag)
        input_layout.addWidget(self.add_btn)
        tag_layout.addLayout(input_layout)

        self.tag_table = QTableWidget(0, 4)
        self.tag_table.setHorizontalHeaderLabels(["标签名", "数据类型", "当前值", "操作"])
        self.tag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tag_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tag_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tag_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.tag_table.itemChanged.connect(self._on_table_item_changed)
        tag_layout.addWidget(self.tag_table)
        
        main_layout.addWidget(tag_group)

        # 4. 接收区
        recv_group = QGroupBox("从 VM 接收的报文")
        recv_layout = QVBoxLayout(recv_group)
        self.recv_text = QTextEdit()
        self.recv_text.setReadOnly(True)
        recv_layout.addWidget(self.recv_text)
        clear_btn = QPushButton("清空接收区")
        clear_btn.clicked.connect(self.recv_text.clear)
        recv_layout.addWidget(clear_btn)
        main_layout.addWidget(recv_group, stretch=2)

        # 5. 日志
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group, stretch=1)

        self._refresh_table()

    # ---------------- UI 与 数据同步 ----------------
    def _log(self, msg):
        self.signaller.log_signal.emit(msg)

    def _append_log(self, msg):
        self.log_text.append(msg)

    def _append_recv(self, msg):
        if self.recv_text.document().blockCount() > 300:
            cursor = self.recv_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        self.recv_text.append(msg)

    def _refresh_table(self):
        self.tag_table.blockSignals(True)
        self.tag_table.setRowCount(0)
        for tag, info in self.tags.items():
            row = self.tag_table.rowCount()
            self.tag_table.insertRow(row)
            
            item_tag = QTableWidgetItem(tag)
            item_tag.setTextAlignment(Qt.AlignCenter)
            self.tag_table.setItem(row, 0, item_tag)
            
            combo_type = QComboBox()
            combo_type.addItems(["INT16", "DINT32", "REAL"])
            combo_type.setCurrentText(info["type"])
            combo_type.currentTextChanged.connect(lambda text, r=row: self._on_type_changed(r, text))
            self.tag_table.setCellWidget(row, 1, combo_type)
            
            item_val = QTableWidgetItem(str(info["value"]))
            item_val.setTextAlignment(Qt.AlignCenter)
            self.tag_table.setItem(row, 2, item_val)
            
            btn_del = QPushButton("删除")
            btn_del.setStyleSheet("color: red;")
            btn_del.clicked.connect(lambda checked, t=tag: self._delete_tag(t))
            self.tag_table.setCellWidget(row, 3, btn_del)
            
        self.tag_table.blockSignals(False)

    def _on_type_changed(self, row, new_type):
        tag_name = self.tag_table.item(row, 0).text()
        if tag_name in self.tags and self.tags[tag_name]["type"] != new_type:
            self.tags[tag_name]["type"] = new_type
            self._log(f"[*] 标签 {tag_name} 的数据类型已改为: {new_type}")
            if self.client_socket:
                self._send_write_tag(tag_name)

    def _create_tag(self):
        tag = self.new_tag_edit.text().strip()
        if not tag: return
        if tag in self.tags:
            QMessageBox.warning(self, "警告", f"标签 {tag} 已存在！")
            return
        try:
            dtype = self.new_type_combo.currentText()
            val_str = self.new_val_edit.text().strip()
            if dtype == "REAL":
                val = float(val_str)
            else:
                val = int(val_str)
        except ValueError:
            QMessageBox.warning(self, "错误", "值的格式与数据类型不匹配")
            return

        self.tags[tag] = {"value": val, "type": dtype}
        self._refresh_table()
        self._log(f"[*] 创建新标签: {tag} = {val} ({dtype})")

    def _delete_tag(self, tag_name):
        reply = QMessageBox.question(self, '确认删除', f'确定要删除标签 {tag_name} 吗？', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if tag_name in self.tags:
                del self.tags[tag_name]
                self._refresh_table()
                self._log(f"[*] 已删除标签: {tag_name}")

    def _on_table_item_changed(self, item):
        if item.column() != 2: return
        
        row = item.row()
        tag_name = self.tag_table.item(row, 0).text()
        dtype = self.tags[tag_name]["type"]
        
        try:
            val_str = item.text()
            if dtype == "REAL":
                new_val = float(val_str)
            else:
                new_val = int(val_str)
                
            if self.tags[tag_name]["value"] != new_val:
                self.tags[tag_name]["value"] = new_val
                self._log(f"[*] 标签 {tag_name} ({dtype}) 的值已更新为: {new_val}")
                
                if self.client_socket:
                    self._send_write_tag(tag_name)
        except ValueError:
            QMessageBox.warning(self, "错误", f"请输入有效的 {dtype} 格式")
            self.tag_table.blockSignals(True)
            item.setText(str(self.tags[tag_name]["value"]))
            self.tag_table.blockSignals(False)

    # ---------------- 核心：CIP 路径智能拆分 ----------------
    def _build_cip_path(self, tag_name):
        """将带点的标签名拆分为多段 0x91 符号段"""
        parts = tag_name.split('.')
        path_bytes = bytearray()
        
        for part in parts:
            part_bytes = part.encode('ascii')
            # CIP 要求 ANSI 字符串必须补齐到偶数长度
            if len(part_bytes) % 2 != 0:
                part_bytes += b'\x00'
            
            # 0x91: ANSI Extended Symbol Segment
            path_bytes += bytes([0x91, len(part)])
            path_bytes += part_bytes
            
        # 计算总路径字数（以 16-bit 字为单位，即字节数 / 2）
        # 每个段包含 1 字节 0x91, 1 字节 长度, 以及补齐后的字符串
        path_words = len(path_bytes) // 2
        
        return bytes([path_words]) + path_bytes

    # ---------------- 网络与数据打包逻辑 ----------------
    def _start(self):
        if self.is_running: return
        ip = self.ip_edit.text().strip()
        try: port = int(self.port_edit.text().strip())
        except ValueError:
            QMessageBox.critical(self, "错误", "端口必须是整数")
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((ip, port))
            self.server_socket.listen(1)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", str(e))
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("监听中，等待 VM 连接…")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self._log(f"[*] 监听 {ip}:{port}")
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.is_running:
            try:
                self.server_socket.settimeout(1.0)
                client, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            self.client_socket = client
            self._log(f"[+] VM 已连接: {addr}")
            self.status_label.setText(f"已连接: {addr}")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            threading.Thread(target=self._recv_loop, args=(client, addr), daemon=True).start()
            continue

    def _recv_loop(self, client, addr):
        buffer = b""
        while self.is_running:
            try:
                data = client.recv(4096)
                if not data: break
                buffer += data
                
                while len(buffer) >= 24:
                    length = int.from_bytes(buffer[2:4], "little")
                    total_len = 24 + length
                    if len(buffer) < total_len: break
                    packet = buffer[:total_len]
                    buffer = buffer[total_len:]
                    self._handle_packet(client, packet)
            except Exception:
                break

        self.status_label.setText("VM 已断开")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        if client: client.close()

    def _handle_packet(self, client, packet):
        command = int.from_bytes(packet[0:2], "little")
        session = packet[4:8]
        context = packet[12:20]

        if command == 0x0065:
            response = bytearray()
            response += (0x0065).to_bytes(2, "little")
            response += (4).to_bytes(2, "little")
            response += self.session_handle.to_bytes(4, "little")
            response += (0).to_bytes(4, "little")
            response += context
            response += (0).to_bytes(4, "little")
            response += (1).to_bytes(4, "little")
            client.sendall(bytes(response))
            self._log(f"[SEND] RegisterSession 成功")

        elif command == 0x006F:
            self._handle_vm_read_request(client, packet, session, context)

    def _handle_vm_read_request(self, client, packet, session, context):
        payload = packet[24:]
        if len(payload) < 16: return
        
        offset = 8
        addr_len = int.from_bytes(payload[offset+2:offset+4], "little")
        offset += 4 + addr_len
        data_len = int.from_bytes(payload[offset+2:offset+4], "little")
        offset += 4
        
        cip_data = payload[offset:offset+data_len]
        if len(cip_data) < 2: return

        # 尝试从报文里解析请求的标签路径
        target_tag = "Stn05CameraHKVision.Trigger"  # 默认值
        try:
            # 简单解析：提取所有 0x91 段拼起来
            path_parts = []
            i = 2 # 跳过 Service 和 Path Size
            while i < len(cip_data):
                if cip_data[i] == 0x91:
                    tag_len = cip_data[i+1]
                    tag_bytes = cip_data[i+2 : i+2+tag_len]
                    path_parts.append(tag_bytes.decode('ascii', errors='ignore'))
                    i += 2 + tag_len
                else:
                    i += 1
            if path_parts:
                target_tag = ".".join(path_parts)
        except Exception:
            pass

        # 获取对应的值和类型
        if target_tag in self.tags:
            info = self.tags[target_tag]
            val = info["value"]
            dtype = info["type"]
        else:
            val = 0
            dtype = "INT16"

        cip_response = bytearray()
        cip_response += bytes([cip_data[0] | 0x80, 0x00, 0x00, 0x00])
        
        if dtype == "INT16":
            cip_response += (0x00C3).to_bytes(2, "little")
            cip_response += (2).to_bytes(2, "little")
            cip_response += (1).to_bytes(2, "little")
            cip_response += int(val).to_bytes(2, "little", signed=True)
        elif dtype == "DINT32":
            cip_response += (0x00C4).to_bytes(2, "little")
            cip_response += (1).to_bytes(2, "little")
            cip_response += int(val).to_bytes(4, "little", signed=True)
        elif dtype == "REAL":
            cip_response += (0x00CA).to_bytes(2, "little")
            cip_response += (1).to_bytes(2, "little")
            cip_response += struct.pack("<f", float(val))
        
        self._send_cip_packet(client, session, context, cip_response)

    def _send_write_tag(self, tag_name):
        if not self.client_socket or tag_name not in self.tags: return
        info = self.tags[tag_name]
        val = info["value"]
        dtype = info["type"]
        
        cip_request = bytearray()
        cip_request += bytes([0x4D]) # Write Tag
        cip_request += self._build_cip_path(tag_name) # 使用智能路径打包
        
        if dtype == "INT16":
            cip_request += (0x00C3).to_bytes(2, "little")
            cip_request += (1).to_bytes(2, "little")
            cip_request += int(val).to_bytes(2, "little", signed=True)
        elif dtype == "DINT32":
            cip_request += (0x00C4).to_bytes(2, "little")
            cip_request += (1).to_bytes(2, "little")
            cip_request += int(val).to_bytes(4, "little", signed=True)
        elif dtype == "REAL":
            cip_request += (0x00CA).to_bytes(2, "little")
            cip_request += (1).to_bytes(2, "little")
            cip_request += struct.pack("<f", float(val))
            
        self._send_cip_packet(self.client_socket, self.session_handle.to_bytes(4, "little"), bytes(8), cip_request)
        self._log(f"[SEND] 主动推送 {tag_name} = {val} ({dtype})")

    def _send_cip_packet(self, client, session, context, cip_payload):
        payload = bytearray()
        payload += (0).to_bytes(4, "little")
        payload += (0).to_bytes(2, "little")
        payload += (2).to_bytes(2, "little")
        payload += (0).to_bytes(2, "little")
        payload += (0).to_bytes(2, "little")
        payload += (0x00B2).to_bytes(2, "little")
        payload += len(cip_payload).to_bytes(2, "little")
        payload += cip_payload

        packet = bytearray()
        packet += (0x006F).to_bytes(2, "little")
        packet += len(payload).to_bytes(2, "little")
        packet += session
        packet += (0).to_bytes(4, "little")
        packet += context
        packet += (0).to_bytes(4, "little")
        packet += payload

        try:
            client.sendall(bytes(packet))
        except Exception:
            pass

    def _stop(self):
        self.is_running = False
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
            self.client_socket = None
        if self.server_socket:
            try: self.server_socket.close()
            except: pass
            self.server_socket = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("已停止")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        self._log("[*] 已停止")

    def closeEvent(self, event):
        self._stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = EnipServerWindow()
    win.show()
    sys.exit(app.exec_())