# ==============================================================================
# 文件名: external_simulator.py (V7 - 增加单次发送的第二辆车)
# 描述:   一个纯粹的数据模拟器。
#         - 修正了轨迹回放结束后车辆跳回起点的问题。
#         - 模拟器现在会在到达终点后，持续发送最后一个点的数据，模拟“停车”。
#         - 新增功能：程序启动时发送一次另一辆车的位置数据
#
# 运行方法: python external_simulator.py
# ==============================================================================
import asyncio
import csv
import random
import time
import json
import httpx

# --- 配置 ---
SERVER_PUSH_URL = "http://127.0.0.1:8000/api/push_data"
VEHICLE_LOG_CSV_PATH = 'vehicles.csv'
ALARMS_CSV_PATH = 'alarms.csv'
REPLAY_SPEED_MULTIPLIER = 70.0

# 第二辆车的配置 (只发送一次)
SECOND_VEHICLE_CONFIG = {
    "trainDeviceCode": "SECOND-001",  # 第二辆车的唯一标识
    "lat": 39.951505281,  # 第二辆车的纬度
    "lon": 116.333452856,  # 第二辆车的经度
    "speed": 0  # 第二辆车的速度
}

# --- 全局变量 ---
VEHICLE_LOG_DATA = []
ALARM_DEFINITIONS = []
ACTIVE_ALARM_INFO = None
SECOND_VEHICLE_SENT = False  # 标记第二辆车是否已发送


# --- 辅助函数 ---
def load_data_sources():
    global VEHICLE_LOG_DATA, ALARM_DEFINITIONS
    try:
        with open(VEHICLE_LOG_CSV_PATH, mode='r', encoding='utf-8-sig') as infile:
            VEHICLE_LOG_DATA = list(csv.DictReader(infile))
        print(f"✅ [模拟器] 成功加载 {len(VEHICLE_LOG_DATA)} 条车辆行驶日志。")
    except Exception as e:
        print(f"❌ [模拟器] 加载车辆日志CSV文件失败: {e}");
        VEHICLE_LOG_DATA = []
    try:
        with open(ALARMS_CSV_PATH, mode='r', encoding='utf-8-sig') as infile:
            ALARM_DEFINITIONS = list(csv.DictReader(infile))
        print(f"✅ [模拟器] 成功加载 {len(ALARM_DEFINITIONS)} 个告警定义。")
    except Exception as e:
        print(f"❌ [模拟器] 加载告警CSV定义文件失败: {e}");
        ALARM_DEFINITIONS = []


async def send_data_to_server(payload: dict):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(SERVER_PUSH_URL, json=payload, timeout=5.0)
    except httpx.RequestError:
        print(f"🟠 [模拟器] 无法连接到主服务器 at {SERVER_PUSH_URL}。")
    except Exception as e:
        print(f"❌ [模拟器] 发送数据时发生未知错误: {e}")


# 新增函数：发送第二辆车的数据（只发送一次）
async def send_second_vehicle_once():
    global SECOND_VEHICLE_SENT
    if not SECOND_VEHICLE_SENT:
        vehicle_payload = {
            "messageType": "vehicle_position",
            "data": SECOND_VEHICLE_CONFIG
        }
        await send_data_to_server(vehicle_payload)
        SECOND_VEHICLE_SENT = True
        print(f"🚗 [模拟器] 已发送第二辆车数据: {SECOND_VEHICLE_CONFIG['trainDeviceCode']}")


# --- 模拟器核心逻辑 ---
async def run_pure_simulation():
    global ACTIVE_ALARM_INFO

    # 先发送一次第二辆车的数据
    await send_second_vehicle_once()

    if not VEHICLE_LOG_DATA:
        print("❌ [模拟器] 无行驶日志，模拟器已停止。")
        return

    pos_idx = 0
    print("--- ▶️ 纯数据源模拟已启动 (终点停止模式)... ---")
    log_length = len(VEHICLE_LOG_DATA)

    while True:
        # --- 1. 发送第一辆车位置 ---
        current_log_entry = VEHICLE_LOG_DATA[pos_idx]
        vehicle_payload = {"messageType": "vehicle_position", "data": {
            "trainDeviceCode": "RAW-LOG-001",
            "lat": float(current_log_entry['Latitude']),
            "lon": float(current_log_entry['Longitude']),
            "speed": round(float(current_log_entry['Speed_kmh'])),
        }}

        await send_data_to_server(vehicle_payload)
        await send_second_vehicle_once()
        # --- 2. 告警生命周期管理 ---
        if ACTIVE_ALARM_INFO and time.time() > ACTIVE_ALARM_INFO["end_time"]:
            print(f"✅ [模拟器] 解除告警: {ACTIVE_ALARM_INFO['payload']['data']['alarmType']}")
            clear_payload = ACTIVE_ALARM_INFO["payload"].copy()
            clear_payload["data"]["alarmState"] = 3
            await send_data_to_server(clear_payload)
            ACTIVE_ALARM_INFO = None

        if not ACTIVE_ALARM_INFO and ALARM_DEFINITIONS and random.random() < 0.02:
            alarm_def = random.choice(ALARM_DEFINITIONS)
            alarm_point_entry = random.choice(VEHICLE_LOG_DATA)
            alarm_id = f"alarm-{int(time.time())}"
            alarm_payload = {"messageType": "alarm_event", "data": {
                "alarmId": alarm_id, "alarmEventId": f"event-{int(time.time())}", "alarmState": 1,
                "lat": float(alarm_point_entry['Latitude']), "lon": float(alarm_point_entry['Longitude']),
                "alarmLevel": int(alarm_def['alarm_level']), "alarmType": alarm_def['alarm_type'],
            }}
            print(f"🔥 [模拟器] 发送新告警: {alarm_def['alarm_type']} (持续 {alarm_def['duration_seconds']}s)")
            await send_data_to_server(alarm_payload)
            duration = int(alarm_def['duration_seconds'])
            end_time = time.time() + duration
            ACTIVE_ALARM_INFO = {"payload": alarm_payload, "end_time": end_time}

        # 更新索引
        if pos_idx < log_length - 1:
            pos_idx += 1

        await asyncio.sleep(0.5 / REPLAY_SPEED_MULTIPLIER)


async def main():
    load_data_sources()
    await run_pure_simulation()


if __name__ == "__main__":
    asyncio.run(main())