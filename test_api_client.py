"""
Script test các API endpoints
Usage:  python test_api_client.py
"""

import requests
import time
import json
from colorama import Fore, Style, init

# Khởi tạo colorama
init(autoreset=True)

BASE_URL = "http://localhost:5000"

def print_response(title, response):
    """In response một cách đẹp"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.YELLOW}{title}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)
    print(f"Status Code: {response.status_code}")

def test_health_check():
    """Test health check"""
    print(f"\n{Fore.GREEN}[1] Testing Health Check...{Style.RESET_ALL}")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print_response("Health Check Response", response)
        return response.status_code == 200
    except Exception as e:
        print(f"{Fore.RED}Lỗi: {e}{Style.RESET_ALL}")
        return False

def test_search_affiliate(keyword, sub_id1=None, sub_id2=None, sub_id3=None):
    """Test search affiliate với support cho sub_id parameters"""
    print(f"\n{Fore.GREEN}[2] Testing Search Affiliate{Style.RESET_ALL}")
    print(f"   Keyword: '{keyword}'")
    if sub_id1:
        print(f"   Sub_id1: '{sub_id1}'")
    if sub_id2:
        print(f"   Sub_id2: '{sub_id2}'")
    if sub_id3:
        print(f"   Sub_id3: '{sub_id3}'")
    
    try:
        payload = {"keyword": keyword}
        
        # Thêm sub_id vào payload nếu có
        if sub_id1:
            payload["sub_id1"] = sub_id1
        if sub_id2:
            payload["sub_id2"] = sub_id2
        if sub_id3:
            payload["sub_id3"] = sub_id3
        
        response = requests.post(
            f"{BASE_URL}/search_affiliate",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print_response("Search Affiliate Response", response)
        
        if response.status_code == 202:
            return response.json().get('job_id')
        return None
    except Exception as e:  
        print(f"{Fore.RED}Lỗi: {e}{Style.RESET_ALL}")
        return None

def test_polling(job_id, max_attempts=30):
    """Test polling"""
    print(f"\n{Fore.GREEN}[3] Testing Polling (job_id:  '{job_id}'){Style.RESET_ALL}")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"{BASE_URL}/polling",
                params={"job_id": job_id}
            )
            data = response.json()
            print_response(f"Polling Response (Attempt {attempt + 1}/{max_attempts})", response)
            
            if data.get('job_status') == 'completed':
                print(f"\n{Fore.GREEN}✓ Tìm kiếm hoàn thành!  {Style.RESET_ALL}")
                return True
            
            print(f"{Fore.YELLOW}Đang chờ... ({attempt + 1}/{max_attempts}){Style.RESET_ALL}")
            time.sleep(5)  # Chờ 5 giây trước khi poll lại
            
        except Exception as e:
            print(f"{Fore.RED}Lỗi: {e}{Style.RESET_ALL}")
            return False
    
    print(f"{Fore.RED}✗ Timeout:   Tìm kiếm quá lâu{Style.RESET_ALL}")
    return False

def test_results(job_id):
    """Test results"""
    print(f"\n{Fore.GREEN}[4] Testing Results (job_id: '{job_id}'){Style.RESET_ALL}")
    try:
        response = requests.get(
            f"{BASE_URL}/results",
            params={"job_id": job_id}
        )
        print_response("Results Response", response)
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', 0)
            print(f"\n{Fore.GREEN}✓ Lấy được {count} kết quả{Style.RESET_ALL}")
            
            # In 5 kết quả đầu tiên
            results = data.get('data', [])
            if results:
                print(f"\n{Fore.CYAN}Top 5 kết quả:{Style.RESET_ALL}")
                for i, item in enumerate(results[:5], 1):
                    print(f"{Fore.YELLOW}{i}. {item['title']}")
                    print(f"   {item['link']}\n")
            return True
        return False
    except Exception as e:  
        print(f"{Fore.RED}Lỗi: {e}{Style.RESET_ALL}")
        return False

def test_status():
    """Test status"""
    print(f"\n{Fore.GREEN}[5] Testing Status (All Jobs){Style.RESET_ALL}")
    try:
        response = requests.get(f"{BASE_URL}/status")
        print_response("Status Response", response)
        return response.status_code == 200
    except Exception as e:  
        print(f"{Fore.RED}Lỗi:   {e}{Style.RESET_ALL}")
        return False

def main():
    """Main test flow"""
    print(f"{Fore.MAGENTA}")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "SHOPEE AFFILIATE API TEST" + " " * 19 + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"{Style.RESET_ALL}")

    # 1.Health check
    if not test_health_check():
        print(f"{Fore.RED}Server không khả dụng. Hãy chắc chắn server đang chạy!  {Style.RESET_ALL}")
        return

    # 2.Search affiliate
    keyword = input(f"\n{Fore.CYAN}Nhập từ khóa tìm kiếm:  {Style.RESET_ALL}")
    if not keyword.strip():
        keyword = "điện thoại"  # Default
    
    sub_id1 = input(f"{Fore.CYAN}Nhập sub_id1 (hoặc nhấn Enter để bỏ qua): {Style.RESET_ALL}")
    sub_id2 = input(f"{Fore.CYAN}Nhập sub_id2 (hoặc nhấn Enter để bỏ qua): {Style.RESET_ALL}")
    sub_id3 = input(f"{Fore.CYAN}Nhập sub_id3 (hoặc nhấn Enter để bỏ qua): {Style.RESET_ALL}")
    
    job_id = test_search_affiliate(
        keyword,
        sub_id1=sub_id1.strip() if sub_id1.strip() else None,
        sub_id2=sub_id2.strip() if sub_id2.strip() else None,
        sub_id3=sub_id3.strip() if sub_id3.strip() else None
    )
    
    if not job_id:
        print(f"{Fore.RED}Không thể bắt đầu tìm kiếm{Style.RESET_ALL}")
        return

    # 3.Polling
    if not test_polling(job_id):
        print(f"{Fore.RED}Polling thất bại hoặc timeout{Style.RESET_ALL}")
        return

    # 4.Results
    test_results(job_id)

    # 5.Status
    test_status()

    print(f"\n{Fore.GREEN}{'='*60}")
    print("Test hoàn thành!")
    print(f"{'='*60}{Style.RESET_ALL}\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Đã hủy test{Style.RESET_ALL}")