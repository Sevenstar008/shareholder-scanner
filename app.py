"""
A 股股东检索系统 - 本地数据库版
基于 Flask + SQLite + AKShare
"""

from flask import Flask, render_template, request, jsonify, send_file
import akshare as ak
import pandas as pd
import sqlite3
import os
import time
import threading
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
    'message': '就绪'
}

# ================= 数据库操作 =================
def init_db():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS top10_holders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            stock_name TEXT,
            holder_name TEXT,
            holder_rank INTEGER,
            update_time TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_holder ON top10_holders(holder_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_code ON top10_holders(stock_code)')
    conn.commit()
    conn.close()

def clear_db():
    """清空旧数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM top10_holders')
    conn.commit()
    conn.close()

def insert_holders(data_list):
    """批量插入数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany('''
        INSERT INTO top10_holders (stock_code, stock_name, holder_name, holder_rank, update_time)
        VALUES (?, ?, ?, ?, ?)
    ''', data_list)
    conn.commit()
    conn.close()

def search_holders(keywords):
    """本地搜索股东"""
    conn = sqlite3.connect(DB_PATH)
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("holder_name LIKE ?")
        params.append(f"%{kw}%")
    
    sql = f'''
        SELECT stock_code, stock_name, holder_name, holder_rank 
        FROM top10_holders 
        WHERE {" OR ".join(conditions)}
        ORDER BY stock_code, holder_rank
    '''
    
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

# ================= 数据更新逻辑 =================
def get_all_a_stock_codes():
    """获取所有 A 股股票代码和名称"""
    try:
        df = ak.stock_info_a_code_name()
        df = df[df['code'].str.startswith(('6', '0', '3'))]
        return df
    except Exception as e:
        print(f"获取股票列表失败：{e}")
        return pd.DataFrame()

def update_database_thread():
    """后台更新数据库线程"""
    global update_status
    update_status['running'] = True
    update_status['message'] = '正在获取股票列表...'
    
    try:
        # 清空旧数据
        clear_db()
        
        # 获取股票列表
        stock_df = get_all_a_stock_codes()
        if stock_df.empty:
            update_status['message'] = '获取股票列表失败'
            update_status['running'] = False
            return

        total = len(stock_df)
        update_status['total'] = total
        update_status['message'] = f'开始更新 {total} 只股票...'
        
        batch_data = []
        BATCH_SIZE = 100
        current_time = datetime.now().strftime('%Y-%m-%d')
        
        for index, row in stock_df.iterrows():
            if not update_status['running']:
                break
            
            code = row['code']
            name = row['name']
            
            update_status['current'] = index + 1
            update_status['progress'] = int((index + 1) / total * 100)
            
            try:
                # 获取十大流通股东
                df = ak.stock_floatholder_top10(symbol=code)
                if df is not None and not df.empty and '股东名称' in df.columns:
                    for rank, holder in enumerate(df['股东名称'].tolist(), 1):
                        if isinstance(holder, str):
                            batch_data.append((code, name, holder, rank, current_time))
                
                # 批量写入
                if len(batch_data) >= BATCH_SIZE:
                    insert_holders(batch_data)
                    batch_data = []
                    
            except Exception as e:
                pass
            
            # 延时避免请求过快
            time.sleep(0.15)
        
        # 写入剩余数据
        if batch_data:
            insert_holders(batch_data)
            
        update_status['message'] = f'✅ 更新完成！共收录 {update_status["current"]} 只股票'
        
    except Exception as e:
        update_status['message'] = f'❌ 更新出错：{str(e)}'
    finally:
        update_status['running'] = False

# ================= Web 路由 =================
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/api/update', methods=['POST'])
def start_update():
    """开始更新数据"""
    global update_status
    if update_status['running']:
        return jsonify({'success': False, 'message': '更新正在进行中'})
    
    update_status = {'running': False, 'progress': 0, 'total': 0, 'current': 0, 'message': '准备启动...'}
    
    thread = threading.Thread(target=update_database_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '数据更新已启动'})

@app.route('/api/status')
def get_status():
    """获取更新状态"""
    return jsonify(update_status)

@app.route('/api/search', methods=['POST'])
def search():
    """搜索股东"""
    data = request.json
    keywords = data.get('keywords', '')
    if not keywords:
        return jsonify({'success': False, 'message': '请输入股东名字'})
    
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    df = search_holders(kw_list)
    
    if df.empty:
        return jsonify({'success': True, 'count': 0, 'data': []})
    
    # 聚合：同一只股票匹配多个股东，合并显示
    result = df.groupby(['stock_code', 'stock_name'])['holder_name'].apply(lambda x: ' | '.join(x)).reset_index()
    result['match_count'] = df.groupby(['stock_code', 'stock_name']).size().values
    result = result.sort_values('match_count', ascending=False)
    
    return jsonify({
        'success': True, 
        'count': len(result), 
        'data': result.to_dict('records')
    })

@app.route('/api/export', methods=['POST'])
def export_excel():
    """导出搜索结果"""
    data = request.json
    keywords = data.get('keywords', '')
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    
    df = search_holders(kw_list)
    if df.empty:
        return jsonify({'success': False, 'message': '无数据可导出'})
    
    filename = f"股东明细_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    df.to_excel(filepath, index=False)
    
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/api/export_all', methods=['GET'])
def export_all_db():
    """导出全量数据库"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM top10_holders", conn)
    conn.close()
    
    if df.empty:
        return jsonify({'success': False, 'message': '数据库为空，请先更新'})
    
    filename = f"全量十大流通股东_{datetime.now().strftime('%Y%m%d')}.xlsx"
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    df.to_excel(filepath, index=False)
    
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 A 股股东检索系统 - 本地库版")
    print("=" * 60)
    print("📌 请在浏览器中访问：http://127.0.0.1:5000")
    print("⚠️  按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(debug=True, port=5000, host='127.0.0.1')
