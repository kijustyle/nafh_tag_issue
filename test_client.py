"""
BIXOLON 라벨 프린터 테스트 클라이언트
서버로 인쇄 데이터를 전송합니다.
"""

import socket
import json
from datetime import datetime


def send_print_request(host='127.0.0.1', port=9999):
    """인쇄 요청 전송"""
    
    # 테스트 데이터
    print_data = {
        'qr_data': 'T000000001087',
        'name': '홍길동',
        'employee_id': 'T00000000108',
        'department': '싸이버원',
        'issue_date': '20205-01-01'
    }
    
    try:
        # 소켓 연결
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        
        print(f"서버에 연결됨: {host}:{port}")
        print(f"전송 데이터: {print_data}")
        
        # JSON 데이터 전송
        json_data = json.dumps(print_data, ensure_ascii=False)
        client_socket.sendall(json_data.encode('utf-8'))
        
        # 응답 수신
        response = client_socket.recv(4096)
        response_data = json.loads(response.decode('utf-8'))
        
        print(f"서버 응답: {response_data}")
        
        client_socket.close()
        
        return response_data
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print("BIXOLON 라벨 프린터 테스트 클라이언트")
    print("=" * 50)
    
    # 인쇄 요청 전송
    result = send_print_request()
    
    if result and result.get('status') == 'success':
        print("\n✓ 인쇄 요청이 성공적으로 처리되었습니다!")
    else:
        print("\n✗ 인쇄 요청 처리에 실패했습니다.")