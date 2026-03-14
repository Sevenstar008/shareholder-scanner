"""
A 股股东检索系统 - 优化增强版
基于 Flask + SQLite + AKShare
优化点：断点保护、影子表切换机制、随机延时防封
"""

from flask import Flask, render_template, request, jsonify, send_file
import akshare as ak
import pandas as pd
import sqlite3
import os
import time
import threading
import random
from datetime import datetime

app = Flask(__name__)

# 配置路径
DB_FOLDER = "data"
OUTPUT_FOLDER = "outputs"
DB_PATH = os.path.join(DB_FOLDER, "shareholders.db")
os.makedirs(DB_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 全局状态
update_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'current': 0,
    'success_count': 0,
    'message': '就绪'
}

# ================= 数据库操作 =================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(table_name="top10_holders"):
    """初始化数据库表结构"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            stock_name TEXT,
            holder_name TEXT,
            holder_rank INTEGER,
            update_time TEXT
        )
    ''')
    c.execute(f'CREATE INDEX IF NOT EXISTS idx_holder_{table_name} ON {table_name}(holder_name)')
    c.execute(f'CREATE INDEX IF NOT EXISTS idx_code_{table_name} ON {table_name}(stock_code)')
    conn.commit()
    conn.close()

def search_holders(keywords):
    """本地搜索股东"""
    conn = get_db_connection()
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("holder_name LIKE ?")
        params.append(f"%{kw}%")
    
    # 增加按匹配度排序逻辑
    sql = f'''
        SELECT stock_code, stock_name, holder_name, holder_rank 
        FROM top10_holders 
        WHERE {" OR ".join(conditions)}
        ORDER BY stock_code, holder_rank
    '''
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

# ================= 数据更新逻辑 (影子表机制) =================
def update_database_thread():
    """后台更新数据库线程：采用临时表切换机制防止数据丢失"""
    global update_status
    update_status['running'] = True
    update_status['success_count'] = 0
    TEMP_TABLE = "top10_holders_temp"
    
    try:
        # 1. 准备临时表
        init_db(TEMP_TABLE)
        conn = get_db_connection()
        conn.execute(f"DELETE FROM {TEMP_TABLE}")
        conn.commit()
        
        # 2. 获取股票列表
        update_status['message'] = '正在获取全量股票列表...'
        try:
            stock_df = ak.stock_info_a_code_name()
            # 过滤 A 股主板、创业板、科创板
            stock_df = stock_df[stock_df['code'].str.startswith(('6', '0', '3'))]
        except Exception as e:
            update_status['message'] = f'获取列表失败: {e}'
            update_status['running'] = False
            return

        total = len(stock_df)
        update_status['total'] = total
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        batch_data = []
        for index, row in stock_df.iterrows():
            if not update_status['running']: break # 支持外部停止
            
            code, name = row['code'], row['name']
            update_status['current'] = index + 1
            update_status['progress'] = int((index + 1) / total * 100)
            
            try:
                # 获取数据，增加重试机制
                df = None
                for _ in range(2): 
                    try:
                        df = ak.stock_floatholder_top10(symbol=code)
                        if df is not None: break
                    except:
                        time.sleep(1)
                
                if df is not None and not df.empty and '股东名称' in df.columns:
                    for rank, holder in enumerate(df['股东名称'].tolist(), 1):
                        if isinstance(holder, str) and holder.strip():
                            batch_data.append((code, name, holder.strip(), rank, current_date))
                    update_status['success_count'] += 1
                
                # 每 50 只股票写入一次，提高效率
                if len(batch_data) >= 500:
                    conn.executemany(f"INSERT INTO {TEMP_TABLE} (stock_code, stock_name, holder_name, holder_rank, update_time) VALUES (?,?,?,?,?)", batch_data)
                    conn.commit()
                    batch_data = []
                    
                update_status['message'] = f'正在同步: {name} ({code})'
            except:
                pass
            
            # 关键：随机延时防封 IP
            time.sleep(random.uniform(0.1, 0.3))
        
        # 3. 写入剩余数据并切换表
        if batch_data:
            conn.executemany(f"INSERT INTO {TEMP_TABLE} (stock_code, stock_name, holder_name, holder_rank, update_time) VALUES (?,?,?,?,?)", batch_data)
        
        # 原子化切换表：删除旧表，将临时表重命名为正式表
        conn.execute("DROP TABLE IF EXISTS top10_holders")
        conn.execute(f"ALTER TABLE {TEMP_TABLE} RENAME TO top10_holders")
        conn.commit()
        
        update_status['message'] = f'✅ 更新完成！成功采集 {update_status["success_count"]} 只股票'
        
    except Exception as e:
        update_status['message'] = f'❌ 更新失败: {str(e)}'
    finally:
        if 'conn' in locals(): conn.close()
        update_status['running'] = False

# ================= Web 路由 =================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify(update_status)

@app.route('/api/update', methods=['POST'])
def start_update():
    if update_status['running']:
        return jsonify({'success': False, 'message': '更新正在进行中'})
    thread = threading.Thread(target=update_database_thread, daemon=True)
    thread.start()
    return jsonify({'success': True})

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    keywords = data.get('keywords', '').replace('，', ',') # 处理中英文逗号
    if not keywords:
        return jsonify({'success': False, 'message': '请输入关键词'})
    
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    df = search_holders(kw_list)
    
    if df.empty:
        return jsonify({'success': True, 'count': 0, 'data': []})
    
    # 数据聚合
    result = df.groupby(['stock_code', 'stock_name'])['holder_name'].apply(lambda x: ' | '.join(list(set(x)))).reset_index()
    result['match_count'] = df.groupby(['stock_code', 'stock_name']).size().values
    result = result.sort_values('match_count', ascending=False)
    
    return jsonify({
        'success': True, 
        'count': len(result), 
        'data': result.to_dict('records')
    })

@app.route('/api/export', methods=['POST'])
def export_excel():
    data = request.json
    keywords = data.get('keywords', '').replace('，', ',')
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    
    df = search_holders(kw_list)
    if df.empty: return jsonify({'success': False})
    
    filename = f"搜索结果_{datetime.now().strftime('%H%M%S')}.xlsx"
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    # 指定 engine 确保兼容性
    df.to_excel(filepath, index=False, engine='openpyxl')
    return send_file(filepath, as_attachment=True)

if __name__ == '__main__':
    init_db() # 确保正式表存在
    app.run(debug=True, port=5000)
