from pymongo import MongoClient
import time

# Kết nối Database
client = MongoClient("mongodb://localhost:27017/")
db = client["SmartHome_DB"]

def check_automation():
    print("\n--- Đang kiểm tra hệ thống tự động ---")
    
    # 1. Lấy dữ liệu cảm biến mới nhất (Ví dụ lấy từ phòng bếp R02)
    # Ở đây mình giả sử lấy bản ghi mới nhất trong collection sensor_data
    latest_temp = db["sensor_data"].find_one({"type": "Temperature"}, sort=[("timestamp", -1)])
    latest_humi = db["sensor_data"].find_one({"type": "Humidity"}, sort=[("timestamp", -1)])

    if not latest_temp or not latest_humi:
        print("Chưa có đủ dữ liệu cảm biến để kiểm tra.")
        return

    t_val = latest_temp["value"]
    h_val = latest_humi["value"]
    print(f"Dữ liệu hiện tại: Temp={t_val}°C, Humi={h_val}%")

    # 2. Lấy tất cả các Rule đang hoạt động (is_active: true)
    rules = db["automation_rules"].find({"is_active": True})

    for rule in rules:
        logic = rule["logic_operator"] # "AND" hoặc "OR"
        conditions_met = []

        # Kiểm tra từng điều kiện trong mảng conditions
        for cond in rule["conditions"]:
            is_met = False
            current_val = t_val if cond["sensor_type"] == "Temperature" else h_val
            
            # So sánh dựa trên operator (>, <, ==)
            if cond["operator"] == ">" and current_val > cond["threshold_value"]:
                is_met = True
            elif cond["operator"] == "<" and current_val < cond["threshold_value"]:
                is_met = True
            
            conditions_met.append(is_met)

        # 3. Quyết định hành động dựa trên Logic Operator
        should_activate = False
        if logic == "AND":
            should_activate = all(conditions_met)
        elif logic == "OR":
            should_activate = any(conditions_met)

        if should_activate:
            for action in rule["actions"]:
                device_id = action["device_id"]
                command = "ON" if "TURN_ON" in action["action_command"] else "OFF"
                
                # Cập nhật trạng thái thiết bị trong collection 'devices'
                db["devices"].update_one(
                    {"device_id": device_id},
                    {"$set": {"status": command}}
                )
                print(f"✅ Đã kích hoạt '{rule['rule_name']}': Bật {device_id}")
        else:
            print(f"⚪ Rule '{rule['rule_name']}' chưa đủ điều kiện kích hoạt.")

# Chạy kiểm tra mỗi 10 giây
try:
    while True:
        check_automation()
        time.sleep(10)
except KeyboardInterrupt:
    print("Dừng hệ thống.")