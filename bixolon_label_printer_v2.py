"""
BIXOLON XD5-40d 라벨 프린터 - 한글 폰트 지원 버전
"""

import socket
import json
import threading
import time
import sys
import io
import os
import logging
from datetime import datetime

# QR 코드 생성
import qrcode
from PIL import Image, ImageDraw, ImageFont

# 시스템 트레이
import pystray
from pystray import MenuItem as item

# GUI
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QCursor

# Windows 프린터
try:
    import win32print
    import win32ui
    from PIL import ImageWin
except ImportError:
    print("Windows 환경이 아닙니다. pywin32가 필요합니다.")


class PrintSignals(QObject):
    """인쇄 상태 시그널"""
    start_printing = pyqtSignal()
    finish_printing = pyqtSignal()
    update_status = pyqtSignal(str)


class PrintingDialog(QDialog):
    """인쇄 중 애니메이션 다이얼로그 - 글래스모피즘 디자인"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("국립소방병원 TAG 발급 프린터 실행중 ... ")
        self.setFixedSize(400, 250)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)  # 투명 배경
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 글래스 컨테이너
        self.glass_container = QLabel()
        self.glass_container.setFixedSize(400, 250)
        self.glass_container.setStyleSheet("""
            QLabel {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 0.25),
                    stop:1 rgba(255, 255, 255, 0.15)
                );
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 25px;
            }
        """)
        
        # 컨테이너 내부 레이아웃
        container_layout = QVBoxLayout(self.glass_container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.setSpacing(20)
        
        # 상단 여백
        container_layout.addStretch()
        
        # 아이콘 레이블
        self.icon_label = QLabel("🖨️")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                background: transparent;
                border: none;
            }
        """)
        container_layout.addWidget(self.icon_label)
        
        # 상태 레이블
        self.status_label = QLabel("인쇄 준비 중...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 1);
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            }
        """)
        container_layout.addWidget(self.status_label)
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 무한 애니메이션
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(100, 200, 255, 0.8),
                    stop:0.5 rgba(150, 220, 255, 1),
                    stop:1 rgba(100, 200, 255, 0.8)
                );
                border-radius: 4px;
            }
        """)
        container_layout.addWidget(self.progress_bar)
        
        # 세부 정보 레이블
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.8);
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)
        container_layout.addWidget(self.detail_label)
        
        # 하단 여백
        container_layout.addStretch()
        
        main_layout.addWidget(self.glass_container)
        self.setLayout(main_layout)
        
        # 화면 중앙에 배치
        self.center_on_screen()
        
        # 자동 닫기 타이머
        self.close_timer = QTimer()
        self.close_timer.timeout.connect(self.close)
        
        # 애니메이션 타이머
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_icon)
        self.animation_step = 0
        self.animation_timer.start(300)  # 300ms마다 아이콘 변경
    
    def center_on_screen(self):
        """화면 중앙에 다이얼로그 배치"""
        screen = QApplication.desktop().screenGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def animate_icon(self):
        """아이콘 애니메이션"""
        icons = ["🖨️", "📄", "✨", "🖨️"]
        self.icon_label.setText(icons[self.animation_step % len(icons)])
        self.animation_step += 1
    
    def update_status(self, status_text):
        """상태 업데이트"""
        self.status_label.setText(status_text)
    
    def update_detail(self, detail_text):
        """세부 정보 업데이트"""
        self.detail_label.setText(detail_text)
    
    def finish_and_close(self, delay=2000):
        """인쇄 완료 후 자동 닫기"""
        self.animation_timer.stop()
        self.icon_label.setText("✅")
        self.status_label.setText("인쇄 완료!")
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(100, 255, 150, 1);
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
                text-shadow: 0 2px 8px rgba(100, 255, 150, 0.5);
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(100, 255, 150, 0.8),
                    stop:0.5 rgba(150, 255, 180, 1),
                    stop:1 rgba(100, 255, 150, 0.8)
                );
                border-radius: 4px;
            }
        """)
        self.close_timer.start(delay)


class BixolonLabelPrinter:
    """BIXOLON 라벨 프린터 제어 클래스"""
    
    def __init__(self, printer_name="BIXOLON XD5-40d - BPL-Z", config=None):
        self.printer_name = printer_name
        self.config = config or {}
        self.signals = PrintSignals()
        self.font = self.load_font()
        self.setup_logger()
        
    def setup_logger(self):
        """로거 설정"""
        # logs 폴더 생성
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # 오늘 날짜로 로그 파일명 생성
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = f'logs/{today}.log'
        
        # 로거 설정
        self.logger = logging.getLogger('BixolonPrinter')
        self.logger.setLevel(logging.INFO)
        
        # 기존 핸들러 제거 (중복 방지)
        self.logger.handlers.clear()
        
        # 파일 핸들러 추가
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 포맷 설정
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
    def load_font(self):
        """한글 폰트 로드"""
        # Windows 기본 한글 폰트 경로들
        font_paths = [
            "C:\\Windows\\Fonts\\malgun.ttf",      # 맑은 고딕
            "C:\\Windows\\Fonts\\gulim.ttc",       # 굴림
            "C:\\Windows\\Fonts\\batang.ttc",      # 바탕
            "C:\\Windows\\Fonts\\arial.ttf",       # Arial (영문)
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, 18)
                except:
                    continue
        
        # 기본 폰트 사용
        return ImageFont.load_default()
    
    def create_qr_code(self, data, size=200):
        """QR 코드 이미지 생성"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        return img
    
    def create_label_image(self, data):
        """라벨 이미지 생성 (QR 코드 + 텍스트 정보)"""
        # 용지 크기: 55mm x 32mm
        # 203 DPI 기준: 55mm = 439 픽셀, 32mm = 255 픽셀
        label_width = 800   # 55mm (203 DPI 기준)
        label_height = 240  # 32mm (203 DPI 기준)
        qr_size = 132       # QR 코드 크기 (라벨 높이보다 작게!)
        
        # 배경 이미지 생성
        label = Image.new('RGB', (label_width, label_height), 'white')
        draw = ImageDraw.Draw(label)
        
        # QR 코드 생성 및 배치 (왼쪽, 위아래 여백 5픽셀)
        qr_data = data.get('qr_data', 'NO DATA')
        qr_img = self.create_qr_code(qr_data, size=qr_size)
        qr_x = 220  # 왼쪽 여백
        qr_y = (label_height - qr_size) // 2  # 세로 중앙
        label.paste(qr_img, (qr_x, qr_y))
        
        # 텍스트 정보 추가 (QR 오른쪽)
        text_start_x = qr_x + qr_size + 30  # QR 코드 오른쪽
        
        # 폰트 생성
        try:
            small_font = ImageFont.truetype("C:\\Windows\\Fonts\\malgun.ttf", 24)
        except:
            try:
                small_font = ImageFont.truetype("C:\\Windows\\Fonts\\gulim.ttc", 24)
            except:
                small_font = self.font
        
        text_items = [
            f"이름: {data.get('name', '')}",
            f"사번: {data.get('employee_id', '')}",
            f"소속: {data.get('department', '')}",
            f"발급: {data.get('issue_date', datetime.now().strftime('%Y-%m-%d'))}",
        ]
        
        # 텍스트 전체 높이 계산
        line_height = 55
        total_text_height = len(text_items) * line_height - line_height//2  # 마지막 줄 간격 제외
        text_start_y = (label_height - total_text_height) // 2  # 세로 중앙 정렬
        
        y_position = text_start_y
        for text in text_items:
            draw.text((text_start_x, y_position), text, fill='black', font=small_font)
            y_position += line_height
        
        return label
    
    def print_label(self, data):
        """라벨 인쇄"""
        try:
            
            self.logger.info(f"인쇄 시작 - 데이터: {data}")  # ← 추가
            
            self.signals.update_status.emit("🎨 라벨 이미지 생성 중...")
            time.sleep(0.5)  # UI 업데이트를 위한 짧은 대기
            
            # 라벨 이미지 생성
            label_img = self.create_label_image(data)
            
            self.signals.update_status.emit("🔌 프린터 연결 중...")
            time.sleep(0.3)
            
            # Windows 프린터로 인쇄
            hprinter = win32print.OpenPrinter(self.printer_name)
            try:
                hdc = win32ui.CreateDC()
                hdc.CreatePrinterDC(self.printer_name)
                
                self.signals.update_status.emit("🖨️ 인쇄 시작...")
                
                hdc.StartDoc("Label Print")
                hdc.StartPage()
                
                # 이미지를 프린터로 전송
                dib = ImageWin.Dib(label_img)
                dib.draw(hdc.GetHandleOutput(), (0, 0, label_img.width, label_img.height))
                
                hdc.EndPage()
                hdc.EndDoc()
                hdc.DeleteDC()
                
                self.signals.update_status.emit("✓ 인쇄 완료!")
                self.logger.info("인쇄 성공")  # ← 추가
                return True
                
            finally:
                win32print.ClosePrinter(hprinter)
                
        except Exception as e:
            self.signals.update_status.emit(f"❌ 인쇄 오류: {str(e)}")
            print(f"인쇄 오류: {e}")
            self.logger.error(f"인쇄 오류: {str(e)}")  # ← 추가
            return False


class SocketServer:
    """소켓 서버 클래스"""
    
    def __init__(self, host='127.0.0.1', port=9999, printer=None):
        self.host = host
        self.port = port
        self.printer = printer
        self.running = False
        self.server_socket = None
        
    def start(self):
        """서버 시작"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.printer.logger.info(f"✓ 소켓 서버 시작: {self.host}:{self.port}")  # ← 추가
        except Exception as e:
            print(f"✗ 서버 시작 실패: {e}")
            self.printer.logger.info(f"✗ 서버 시작 실패: {e}")  # ← 추가
            return
        
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()
                self.printer.logger.info(f"📡 클라이언트 연결: {address}")  # ← 추가
                # 별도 스레드에서 처리
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"서버 오류: {e}")
    
    def handle_client(self, client_socket):
        """클라이언트 요청 처리"""
        try:
            # 데이터 수신
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(chunk) < 4096:
                    break
            
            if data:
                # JSON 파싱
                json_data = json.loads(data.decode('utf-8'))
                self.printer.logger.info(f"데이터 수신: {json_data}")  # ← 추가
                
                # 인쇄 시작 시그널
                self.printer.signals.start_printing.emit()
                
                # 라벨 인쇄
                success = self.printer.print_label(json_data)
                
                # 응답 전송
                if success:
                    response = "001"
                else:
                    response = "999"
                client_socket.sendall(response.encode('utf-8'))
                self.printer.logger.info(f"응답 전송: {response}")  # ← 추가
                
                # 인쇄 완료 시그널 (약간의 지연)
                time.sleep(0.5)
                self.printer.signals.finish_printing.emit()
                
        except Exception as e:
            self.printer.logger.error(f"클라이언트 처리 오류: {e}")  # ← 추가
            error_response = {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
            try:
                client_socket.sendall(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
    
    def stop(self):
        """서버 종료"""
        self.printer.logger.error(f"🛑 서버 종료 중...")  # ← 추가
        self.running = False
        if self.server_socket:
            self.server_socket.close()


class TrayIcon:
    """시스템 트레이 아이콘"""
    
    def __init__(self, server, app):
        self.server = server
        self.app = app
        self.icon = None
        
    def create_image(self):
        """트레이 아이콘 이미지 생성"""
        try:
            # img/logo.ico 파일 사용
            if os.path.exists('img/logo.ico'):
                image = Image.open('img/logo.ico')
                # ICO 파일은 여러 크기를 포함할 수 있으므로 적절한 크기로 조정
                if image.size != (64, 64):
                    image = image.resize((64, 64), Image.Resampling.LANCZOS)
                return image
            else:
                # 파일이 없으면 기본 아이콘 생성
                print("⚠️ img/logo.ico 파일을 찾을 수 없습니다. 기본 아이콘을 사용합니다.")
                return self.create_default_icon()
        except Exception as e:
            print(f"⚠️ 아이콘 로드 오류: {e}. 기본 아이콘을 사용합니다.")
            return self.create_default_icon()

    def create_default_icon(self):
        """기본 아이콘 생성 (로고 파일이 없을 때)"""
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), 'white')
        dc = ImageDraw.Draw(image)
        
        # 간단한 프린터 아이콘
        dc.rectangle([10, 15, 54, 40], fill='#0078D4', outline='black', width=2)
        dc.rectangle([15, 20, 49, 35], fill='white', outline='black')
        dc.rectangle([20, 40, 44, 50], fill='white', outline='black', width=1)
        dc.line([25, 43, 39, 43], fill='green', width=2)
        dc.line([25, 46, 39, 46], fill='green', width=2)
        
        return image
    
    def on_quit(self, icon, item):
        """종료 메뉴"""
        print("👋 프로그램 종료 중...")
        self.server.stop()
        icon.stop()
        QApplication.quit()
    
    def on_status(self, icon, item):
        """상태 확인"""
        print("✓ 프린터 상태: 실행 중")
        print(f"   서버: {self.server.host}:{self.server.port}")
        print(f"   프린터: {self.server.printer.printer_name}")
        
        # 시그널 발생
        self.app.status_signal.emit()
    
    def run(self):
        """트레이 아이콘 실행"""
        menu = (
            item('상태 확인', self.on_status),
            item('종료', self.on_quit)
        )
        
        self.icon = pystray.Icon(
            "bixolon_printer",
            self.create_image(),
            "국립소방병원 TAG 발급 프린터\n실행 중...",
            menu
        )
        
        print("📌 시스템 트레이 아이콘 생성됨")
        self.icon.run()

class StatusDialog(QDialog):
    """상태 확인 다이얼로그 - 글래스모피즘 디자인"""
    
    def __init__(self, server_info):
        super().__init__()
        self.setWindowTitle("프린터 상태")
        self.setFixedSize(450, 350)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 글래스 컨테이너
        self.glass_container = QLabel()
        self.glass_container.setFixedSize(450, 350)
        self.glass_container.setStyleSheet("""
            QLabel {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 0, 0, 0.75),
                    stop:1 rgba(0, 0, 0, 0.85)
                );
                border: 2px solid rgba(242, 98, 29, 0.75);
                border-radius: 25px;
            }
        """)
        
        # 컨테이너 내부 레이아웃
        container_layout = QVBoxLayout(self.glass_container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.setSpacing(20)
        
        # 제목
        title_label = QLabel("🖨️ 프린터 상태")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 1);
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        container_layout.addWidget(title_label)
        
        # 구분선
        line = QLabel()
        line.setFixedHeight(2)
        line.setStyleSheet("""
            QLabel {
                background: rgba(242, 98, 29, 0.5);
                border: none;
            }
        """)
        container_layout.addWidget(line)
        
        # 상태 정보 부분을 이렇게 수정
        status_text = f"""
        <div style='color: rgba(255, 255, 255, 0.98); line-height: 1.3;'>
            <p style='font-size: 16px; margin: 5px 0;'>
                <b>🟢 상태:</b> 실행 중
            </p>
            <p style='font-size: 16px; margin: 5px 0;'>
                <b>🌐 서버:</b> {server_info['host']}:{server_info['port']}
            </p>
            <p style='font-size: 16px; margin: 5px 0;'>
                <b>🖨️ 프린터:</b> {server_info['printer']}
            </p>
            <p style='font-size: 16px; margin: 5px 0;'>
                <b>📂 로그:</b> logs/ 폴더
            </p>
        </div>
        """
        
        info_label = QLabel(status_text)
        info_label.setWordWrap(True)  # 자동 줄바꿈
        info_label.setTextFormat(Qt.RichText)  # ← 이거 추가!
        info_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                padding: 10px;
            }
        """)
        container_layout.addWidget(info_label)
        
        container_layout.addStretch()
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.setFixedHeight(45)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(242, 98, 29, 0.2);
                color: white;
                border: 2px solid rgba(242, 98, 29, 0.3);
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(242, 98, 29, 0.6);
                border: 2px solid rgba(242, 98, 29, 0.5);
            }
            QPushButton:pressed {
                background: rgba(242, 98, 29, 0.7);
            }
        """)
        close_btn.clicked.connect(self.hide)
        container_layout.addWidget(close_btn)
        
        main_layout.addWidget(self.glass_container)
        self.setLayout(main_layout)
        
        # 화면 중앙에 배치
        self.center_on_screen()
        
    def close_dialog(self):
        """다이얼로그 닫기"""
        self.hide()
        self.deleteLater()
    
    def center_on_screen(self):
        """화면 중앙에 다이얼로그 배치"""
        screen = QApplication.desktop().screenGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

class Application(QObject):  # ← QObject 추가!
    """메인 애플리케이션"""
    
    status_signal = pyqtSignal()  # ← 클래스 변수로!
    
    def __init__(self):
        super().__init__()  # ← 추가!
        
        # 설정 파일 로드
        self.config = self.load_config()
        
        # Qt 애플리케이션
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # 컴포넌트 초기화
        printer_name = self.config.get('printer', {}).get('name', 'BIXOLON XD5-40d - BPL-Z')
        self.printer = BixolonLabelPrinter(printer_name, self.config)
        
        server_config = self.config.get('server', {})
        self.server = SocketServer(
            host=server_config.get('host', '127.0.0.1'),
            port=server_config.get('port', 9999),
            printer=self.printer
        )
        
        self.tray = TrayIcon(self.server, self)
        self.dialog = None
        
        # 시그널 연결
        self.printer.signals.start_printing.connect(self.show_printing_dialog)
        self.printer.signals.finish_printing.connect(self.hide_printing_dialog)
        self.printer.signals.update_status.connect(self.update_dialog_status)
        self.status_signal.connect(self._show_status_dialog)  # ← 상태 시그널
    
    def _show_status_dialog(self):
        """실제 다이얼로그 표시 (메인 스레드)"""
        server_info = {
            'host': self.server.host,
            'port': self.server.port,
            'printer': self.server.printer.printer_name
        }
        dialog = StatusDialog(server_info)
        dialog.exec_()
        
    def load_config(self):
        """설정 파일 로드"""
        try:
            with open('conf/config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def show_printing_dialog(self):
        """인쇄 다이얼로그 표시"""
        if self.dialog is None:
            self.dialog = PrintingDialog()
        self.dialog.show()
        self.dialog.update_status("🖨️ 인쇄 중...")
    
    def hide_printing_dialog(self):
        """인쇄 다이얼로그 숨김"""
        if self.dialog:
            delay = self.config.get('dialog', {}).get('auto_close_delay', 2000)
            self.dialog.finish_and_close(delay=delay)
    
    def update_dialog_status(self, status):
        """다이얼로그 상태 업데이트"""
        if self.dialog:
            self.dialog.update_status(status)
    
    def run(self):
        """애플리케이션 실행"""
        print("=" * 60)
        print("🖨️  BIXOLON 라벨 프린터 프로그램")
        print("=" * 60)
        
        # 서버 스레드 시작
        server_thread = threading.Thread(target=self.server.start)
        server_thread.daemon = True
        server_thread.start()
        
        # 트레이 아이콘 스레드 시작
        tray_thread = threading.Thread(target=self.tray.run)
        tray_thread.daemon = True
        tray_thread.start()
        
        print("✓ 프로그램이 시작되었습니다.")
        print("✓ 시스템 트레이에서 확인할 수 있습니다.")
        print("✓ 종료하려면 트레이 아이콘을 우클릭하세요.")
        print("=" * 60)
        
        # Qt 이벤트 루프 실행
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    app = Application()
    app.run()