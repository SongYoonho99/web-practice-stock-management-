from flask import Flask, request, jsonify
import sqlite3
import re

# DBファイルの経路
DB_PATH = '/var/www/html/data.db'
# JSON形式で出力するエラーメッセージ
error = {'message': 'ERROR'}

app = Flask(__name__)

# databaseとtable作成(なかったら)
db = sqlite3.connect(DB_PATH)
cur = db.cursor()

# productsテーブル作成 (商品在庫の管理)
cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
        name TEXT PRIMARY KEY,
        amount INTEGER NOT NULL
        )
        ''')

# sales テーブル作成 (売上の管理)
cur.execute('''
    CREATE TABLE IF NOT EXISTS sales (
    total REAL DEFAULT 0
    )
''')

# sales テーブルに初期データがなければ追加
cur.execute("INSERT INTO sales (total) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM sales)")

db.commit()
db.close()

# 在庫の更新、作成
@app.route('/stocks', methods = ['POST'])
def stock_item():
    # クライアントのJSONデータを解析
    data = request.get_json()

    # HTTPリクエストのメッセージボディのkeyの形式が正しくない場合、error出力
    if (
        'name' not in data
        or len(data) > 2
        or (len(data) == 2 and 'amount' not in data)
    ):
        return jsonify(error), 400

    # amountを省略した場合、1にする
    data.setdefault('amount', 1)

    # HTTPリクエストのメッセージボディのvalueの形式が正しくない場合、error出力
    if (
        len(data['name']) > 8                           # nameは8文字以内
        or not re.fullmatch(r'[A-Za-z]+', data['name']) # nameはアルファベットの大文字、小文字のみ
        or not isinstance(data['amount'], int)          # amountは整数
        or data['amount'] <= 0                          # amountは自然数
    ):
        return jsonify(error), 400

    # 在庫の更新、作成
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("SELECT amount FROM products WHERE name = ?", (data['name'],))
    row = cur.fetchone()
    if row: # テーブルにnameが存在する場合は更新
        cur.execute("UPDATE products SET amount = ? WHERE name = ?", (row[0] + data['amount'], data['name']))
    else:   # テーブルにnameが存在しない場合は作成
        cur.execute("INSERT INTO products (name, amount) VALUES (?, ?)", (data["name"], data["amount"]))
    db.commit()
    db.close()

    # HTTP レスポンス設定
    response = jsonify(data)
    response.headers['Location'] = '{}:80/stocks/{}'.format(request.host, data['name'])

    return response

# 在庫チェック(全て)
@app.route('/stocks', methods = ['GET'])
def check_all():
    # 全ての商品の在庫数を確認
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("SELECT name, amount FROM products")
    rows = cur.fetchall()
    data = {name: amount for name, amount in rows}  # dataに全ての商品とその在庫数をdict型で保存
    db.close()

    # amountが0の商品は削除
    data = {k: v for k, v in data.items() if v != 0}

    # HTTP レスポンス設定
    response = jsonify(data)

    return response

# 在庫チェック(指定)
@app.route('/stocks/<item>', methods = ['GET'])
def check_item(item):
    # <item>の商品の在庫数を確認
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("SELECT name, amount FROM products WHERE name = ?", (item,))
    row = cur.fetchone()
    if row: # itemという名前の商品が存在する場合
        data = {row[0]: row[1]}
        db.close()
    else:   # itemという名前の商品が存在しない場合
        db.close()
        return jsonify(error), 400

    # HTTP レスポンス設定
    response = jsonify(data)

    return response

# 販売
@app.route('/sales', methods = ['POST'])
def sale_item():
    data = request.get_json()

    # HTTPリクエストのメッセージボディのkeyの形式が正しくない場合、error出力
    if (
        'name' not in data
        or len(data) > 3
        or (len(data) == 2 and 'amount' not in data and 'price' not in data)    # パラメータが2つの場合amountやpriceの中で1つは必要
        or (len(data) == 3 and ('amount' not in data or 'price' not in data))   # パラメータが3つの場合amountとpriceが全部必要
    ):
        return jsonify(error), 400

    # amountを省略した場合、1にする
    data.setdefault('amount', 1)

    # databaseで在庫数確認及び更新
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("SELECT name, amount FROM products WHERE name = ?", (data['name'],))
    row = cur.fetchone()
    if row: # 商品が存在する場合
        amount_current = row[1] # 現在の在庫数

        if amount_current >= data["amount"]:    # 在庫に余裕がある場合
            cur.execute("UPDATE products SET amount = ? WHERE name = ?", (amount_current - data["amount"], data["name"]))
            
            # priceの入力があった場合、売上計算
            if 'price' in data:
                cur.execute("UPDATE sales SET total = total + ?", (data['amount'] * data['price'],))

            db.commit()
            db.close()
        
        else:   # 在庫不足、error出力
            db.close()
            return jsonify(error), 400
    else:   # 商品が存在しない場合、error出力
        db.close()
        return jsonify(error), 400

    # HTTP レスポンス設定
    response = jsonify(data)
    response.headers['Location'] = '{}:80/sales/{}'.format(request.host, data['name'])

    return response

# 売上チェック
@app.route('/sales', methods = ['GET'])
def sales_money():
    # salesテーブルを参照
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("SELECT total FROM sales")
    row = cur.fetchone()
    db.close()

    # HTTP レスポンス設定
    response = jsonify({"sales": row[0]})

    return response

# 全削除
@app.route('/stocks', methods = ['DELETE'])
def dellete_all():
    # テーブルの形式は維持する
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("DELETE FROM products")
    cur.execute("UPDATE sales SET total = 0")
    db.commit()
    db.close()

    return '', 200

if __name__ == "__main__":
    app.run()