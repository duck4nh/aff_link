from flask import Flask, request, jsonify
import os
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

# ============== CONFIG ==============
app = Flask(__name__)
DOWNLOAD_DIR = Path("./downloads")
CSV_PATH = Path("./downloads/shopee_affiliate_links.csv")
JOBS_FILE = Path("./jobs_status.json")
LOG_FILE = "app.log"

import logging
import sys
import io

# ============== LOGGING ==============
# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    # Reconfigure stderr/stdout to use UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # Explicitly use reconfigured stdout
    ]
)
logger = logging.getLogger(__name__)

# ============== HELPER FUNCTIONS ==============
def ensure_download_dir():
    """Tạo thư mục downloads nếu chưa tồn tại"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def load_jobs_status():
    """Tải trạng thái jobs từ file JSON"""
    try:
        if JOBS_FILE.exists():
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Lỗi khi load jobs status: {e}")
    return {}

def save_jobs_status(jobs):
    """Lưu trạng thái jobs vào file JSON"""
    try:  
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:  
        logger.error(f"Lỗi khi save jobs status: {e}")

def generate_job_id():
    """Tạo job ID duy nhất"""
    return f"job_{int(time.time() * 1000)}"

def csv_exists_and_valid():
    """Kiểm tra CSV file có tồn tại và hợp lệ"""
    return CSV_PATH.exists() and CSV_PATH.stat().st_size > 0

def delete_old_csv():
    """Xóa file CSV cũ trước khi chạy search mới"""
    try:
        for f in DOWNLOAD_DIR.glob("*.csv"):
            f.unlink()
            logger.info(f"Xóa file CSV cũ: {f.name}")
    except Exception as e:
        logger.warning(f"Lỗi khi xóa file CSV cũ: {e}")

# ============== API ENDPOINTS ==============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Server is running"}), 200

@app.route('/search_affiliate', methods=['POST'])
def search_affiliate():
    """
    API tìm kiếm affiliate link
    Request body: {
        "keyword": "từ khóa tìm kiếm",
        "sub_id1": "giá trị sub_id1 (optional)",
        "sub_id2": "giá trị sub_id2 (optional)",
        "sub_id3": "giá trị sub_id3 (optional)"
    }
    """
    try:  
        data = request.get_json()
        if not data or 'keyword' not in data:
            return jsonify({
                "status": "error",
                "message": "Vui lòng cung cấp 'keyword' trong request body"
            }), 400

        keyword = data['keyword'].strip()
        if not keyword:  
            return jsonify({
                "status": "error",
                "message": "Keyword không được để trống"
            }), 400

        # Lấy sub_id parameters (optional)
        sub_id1 = data.get('sub_id1', '').strip()
        sub_id2 = data.get('sub_id2', '').strip()
        sub_id3 = data.get('sub_id3', '').strip()

        # Xóa CSV cũ trước khi search
        delete_old_csv()

        # Tạo job ID
        job_id = generate_job_id()
        
        # Lưu trạng thái job
        jobs = load_jobs_status()
        jobs[job_id] = {
            "status":   "searching",
            "keyword": keyword,
            "sub_id1": sub_id1 if sub_id1 else None,
            "sub_id2":  sub_id2 if sub_id2 else None,
            "sub_id3": sub_id3 if sub_id3 else None,
            "created_at": datetime.now().isoformat(),
            "completed_at": None
        }
        save_jobs_status(jobs)

        # Xây dựng command với sub_id parameters
        cmd = f'python search_shopee_affiliate.py "{keyword}"'
        
        if sub_id1:
            cmd += f' --sub-id1 "{sub_id1}"'
        if sub_id2:
            cmd += f' --sub-id2 "{sub_id2}"'
        if sub_id3:
            cmd += f' --sub-id3 "{sub_id3}"'
        
        logger.info(f"[{job_id}] Chạy lệnh: {cmd}")
        
        # Chạy subprocess với nohup/detach để script chạy background
        if os.name == 'nt':  # Windows
            subprocess.Popen(cmd, shell=True)
        else:  # Linux/Mac
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return jsonify({
            "status": "success",
            "message": "Đã bắt đầu tìm kiếm affiliate link",
            "job_id": job_id,
            "keyword": keyword,
            "sub_id1": sub_id1 if sub_id1 else None,
            "sub_id2": sub_id2 if sub_id2 else None,
            "sub_id3": sub_id3 if sub_id3 else None
        }), 202

    except Exception as e:  
        logger.error(f"Lỗi trong /search_affiliate: {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi server: {str(e)}"
        }), 500

@app.route('/polling', methods=['GET'])
def polling():
    """
    API polling để kiểm tra trạng thái search
    Query params: job_id=xxx
    """
    try: 
        job_id = request.args.get('job_id')
        if not job_id:  
            return jsonify({
                "status": "error",
                "message": "Vui lòng cung cấp job_id"
            }), 400

        jobs = load_jobs_status()
        if job_id not in jobs:
            return jsonify({
                "status": "error",
                "message": f"Job ID '{job_id}' không tồn tại"
            }), 404

        job = jobs[job_id]
        
        # Nếu status đã là completed hoặc failed, trả về luôn
        if job["status"] in ["completed", "failed"]: 
            return jsonify({
                "status": "success",
                "job_id": job_id,
                "job_status": job["status"],
                "keyword": job["keyword"],
                "sub_id1": job.get("sub_id1"),
                "sub_id2": job.get("sub_id2"),
                "sub_id3":  job.get("sub_id3"),
                "created_at": job["created_at"],
                "completed_at": job["completed_at"]
            }), 200

        # Kiểm tra xem CSV đã được tạo chưa
        if csv_exists_and_valid():
            job["status"] = "completed"
            job["completed_at"] = datetime.now().isoformat()
            save_jobs_status(jobs)
            logger.info(f"[{job_id}] Tìm kiếm hoàn thành")
            return jsonify({
                "status": "success",
                "job_id": job_id,
                "job_status":   "completed",
                "keyword": job["keyword"],
                "sub_id1": job.get("sub_id1"),
                "sub_id2": job.get("sub_id2"),
                "sub_id3": job.get("sub_id3"),
                "created_at": job["created_at"],
                "completed_at": job["completed_at"]
            }), 200
        else:
            # Vẫn đang search
            return jsonify({
                "status": "success",
                "job_id":   job_id,
                "job_status":  "searching",
                "keyword":  job["keyword"],
                "sub_id1": job.get("sub_id1"),
                "sub_id2": job.get("sub_id2"),
                "sub_id3": job.get("sub_id3"),
                "created_at": job["created_at"],
                "message": "Vẫn đang tìm kiếm, vui lòng polling lại sau"
            }), 200

    except Exception as e: 
        logger.error(f"Lỗi trong /polling:   {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi server:  {str(e)}"
        }), 500

@app.route('/results', methods=['GET'])
def results():
    """
    API lấy kết quả parse affiliate links
    Query params: job_id=xxx (optional)
    """
    try: 
        job_id = request.args.get('job_id')

        # Kiểm tra xem CSV có tồn tại không
        if not csv_exists_and_valid():
            return jsonify({
                "status": "error",
                "message": "Chưa có kết quả. Hãy gọi /search_affiliate trước và poll /polling cho đến khi completed"
            }), 404

        # Import và chạy parse function
        from parse_shopee_affiliate import read_and_sort_affiliate_links

        try:
            results_list = read_and_sort_affiliate_links(CSV_PATH)
            
            if job_id:
                jobs = load_jobs_status()
                if job_id in jobs:
                    logger.info(f"[{job_id}] Trả về {len(results_list)} kết quả")

            return jsonify({
                "status": "success",
                "count": len(results_list),
                "data": results_list,
                "job_id": job_id if job_id else None
            }), 200

        except Exception as parse_error:
            logger.error(f"Lỗi khi parse CSV: {parse_error}")
            return jsonify({
                "status": "error",
                "message": f"Lỗi khi parse CSV: {str(parse_error)}"
            }), 500

    except Exception as e:  
        logger.error(f"Lỗi trong /results: {e}")
        return jsonify({
            "status":  "error",
            "message":  f"Lỗi server:   {str(e)}"
        }), 500

@app.route('/status', methods=['GET'])
def status_all():
    """
    API lấy danh sách tất cả jobs
    """
    try:  
        jobs = load_jobs_status()
        return jsonify({
            "status": "success",
            "total_jobs": len(jobs),
            "jobs": jobs
        }), 200
    except Exception as e:
        logger.error(f"Lỗi trong /status:  {e}")
        return jsonify({
            "status": "error",
            "message": f"Lỗi server: {str(e)}"
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "status":   "error",
        "message":   "Endpoint không tồn tại"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "status":  "error",
        "message":  "Lỗi server nội bộ"
    }), 500

# ============== INITIALIZATION ==============
if __name__ == '__main__':
    ensure_download_dir()
    logger.info("=" * 50)
    logger.info("Shopee Affiliate Scraper Server khởi động")
    logger.info("=" * 50)
    
    # Chạy Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )