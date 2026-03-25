# ==============================================================================
# 文件名: app_main.py
# 版本:   17.4 (最终稳定版 - 窗口搜索)
# 更新:
# - [核心] 恢复使用“窗口搜索 + 单调递增”算法来计算进度，
#           从根本上解决了因GPS抖动导致的进度回退和前端动画卡顿问题。
# - 包含了所有高级功能：智能基准线选择、精确的站点/车辆对齐、
#           别名系统以及所有已知的Bug修复。
# - 这是功能和稳定性的最佳平衡点。
# ==============================================================================
import asyncio
import json
import csv
import os
import time
import uvicorn
import webbrowser
import threading
from contextlib import asynccontextmanager

import numpy as np
from scipy.interpolate import splev
from pyproj import Transformer, Geod
from shapely.geometry import LineString, Point
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- 配置 ---
SEARCH_WINDOW_FORWARD = 150
SEARCH_WINDOW_BACKWARD = 20
STATION_CLUSTER_DISTANCE_METERS = 20
OVERLAP_THRESHOLD_DEGREES = 0.00005


# --- 模块1: 数据加载与预处理 ---
def load_aliases():
    try:
        with open('aliases.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("⚠️ 警告: aliases.json 文件格式错误，已忽略。"); return {}


ALIASES = load_aliases()


def get_alias(traj_id): return ALIASES.get(traj_id, traj_id)


def reconstruct_single_path(spline_data_dict, num_points=1001):
    try:
        knots, cp, deg = spline_data_dict['knots'], np.array(spline_data_dict['control_points']).T, spline_data_dict[
            'degree']
        origin, epsg = np.array(spline_data_dict['origin']), spline_data_dict['epsg_code']
        tck = (knots, cp, deg);
        u_fine = np.linspace(0, 1, num=num_points)
        norm_pts = np.array(splev(u_fine, tck)).T;
        abs_utm_pts = norm_pts + origin
        utm_line = LineString(abs_utm_pts[:, :2]);
        length_in_meters = utm_line.length
        transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
        lons, lats = transformer.transform(abs_utm_pts[:, 0], abs_utm_pts[:, 1])
        start_coords = (lats[0], lons[0]);
        end_coords = (lats[-1], lons[-1])
        wgs84_line = LineString(zip(lons, lats));
        points = [[lat, lon] for lat, lon in zip(lats, lons)]
        return wgs84_line, points, start_coords, end_coords, length_in_meters
    except Exception as e:
        print(f"❌ 处理轨迹 '{get_alias(spline_data_dict.get('id', 'N/A'))}' 失败: {e}");
        return None, None, None, None, 0


def cluster_stations(all_stations):
    geod = Geod(ellps="WGS84");
    station_nodes = [dict(s, visited=False) for s in all_stations]
    shared_id_counter = 1
    for i, station1 in enumerate(station_nodes):
        if station1['visited']: continue
        station1['visited'] = True;
        cluster = [station1]
        for j, station2 in enumerate(station_nodes):
            if i == j or station2['visited']: continue
            _, _, dist = geod.inv(station1['lon'], station1['lat'], station2['lon'], station2['lat'])
            if dist <= STATION_CLUSTER_DISTANCE_METERS: station2['visited'] = True; cluster.append(station2)
        if len(cluster) > 1:
            for station_in_cluster in cluster: station_in_cluster['shared_id'] = shared_id_counter
            shared_id_counter += 1
    return station_nodes


def get_progress_mapping(traj_layouts, master_traj_id):
    mapping = {};
    master_layout = traj_layouts[master_traj_id]
    for traj_id, layout in traj_layouts.items():
        if traj_id == master_traj_id:
            mapping[traj_id] = sorted([(s['progress'], s['progress']) for s in layout['stations']]);
            continue
        master_anchors = {s['shared_id']: s['progress'] for s in master_layout['stations'] if s['shared_id']}
        anchor_map = [(0.0, 0.0)]
        for s in layout['stations']:
            if s['shared_id'] in master_anchors: anchor_map.append((s['progress'], master_anchors[s['shared_id']]))
        anchor_map.append((1.0, 1.0))
        mapping[traj_id] = sorted(list(set(anchor_map)))
    return mapping


def interpolate_progress(original_progress, mapping_anchors):
    if not mapping_anchors: return original_progress
    start_anchor, end_anchor = None, None
    for i in range(len(mapping_anchors) - 1):
        if mapping_anchors[i][0] <= original_progress <= mapping_anchors[i + 1][0]:
            start_anchor, end_anchor = mapping_anchors[i], mapping_anchors[i + 1];
            break
    if start_anchor and end_anchor and start_anchor[0] != end_anchor[0]:
        relative_pos = (original_progress - start_anchor[0]) / (end_anchor[0] - start_anchor[0])
        return start_anchor[1] + relative_pos * (end_anchor[1] - start_anchor[1])
    return original_progress


# --- 模块 2: 全局数据 ---
TRAJECTORIES_DATA = {}
STATIONS_DATA_SATELLITE = []
SUBWAY_LAYOUT_DATA = {}
PROGRESS_MAPPING = {}
MASTER_TRAJ_ID = None
VEHICLE_STATES = {}  # <--- 回归：我们需要历史状态来实现稳定进度


class ConnectionManager:
    def __init__(self): self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket): await ws.accept(); self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket): self.active_connections.remove(ws)

    async def broadcast(self, message: str):
        for connection in self.active_connections: await connection.send_text(message)


manager = ConnectionManager()


# --- 模块 3: FastAPI 服务器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global TRAJECTORIES_DATA, STATIONS_DATA_SATELLITE, SUBWAY_LAYOUT_DATA, PROGRESS_MAPPING, MASTER_TRAJ_ID
    # ... (lifespan 函数与 V19.3 完全相同)
    print("--- 服务器正在启动 (窗口搜索稳定版)... ---")
    try:
        with open('trajectories_master.json', 'r', encoding='utf-8') as f:
            all_spline_data = json.load(f)
        for traj_data in all_spline_data.get("trajectories", []):
            line, points, start_coords, end_coords, length = reconstruct_single_path(traj_data)
            if line and points:
                traj_id = traj_data['id']
                TRAJECTORIES_DATA[traj_id] = {"line": line, "points": points, "length": length,
                                              "start_coords": start_coords, "end_coords": end_coords}
    except Exception as e:
        print(f"❌ 关键错误: 处理主轨迹文件失败: {e}")
    all_stations_to_cluster = []
    try:
        with open('planned_stations_with_u.csv', mode='r', encoding='utf-8-sig') as infile:
            all_stations_to_cluster.extend([{'station_id': s['station_id'], 'trajectory_id': s['trajectory_id'],
                                             'name': s['name'], 'lat': float(s['latitude']),
                                             'lon': float(s['longitude']), 'u': float(s['u_parameter']),
                                             'shared_id': None} for s in csv.DictReader(infile)])
        for traj_id, traj_data in TRAJECTORIES_DATA.items():
            user_stations_on_traj = [s for s in all_stations_to_cluster if s['trajectory_id'] == traj_id]
            if not any(s['u'] == 0.0 for s in user_stations_on_traj):
                all_stations_to_cluster.append(
                    {'station_id': f"start_{traj_id}", 'trajectory_id': traj_id, 'name': "起点",
                     'lat': traj_data['start_coords'][0], 'lon': traj_data['start_coords'][1], 'u': 0.0,
                     'shared_id': None})
            if not any(s['u'] == 1.0 for s in user_stations_on_traj):
                all_stations_to_cluster.append(
                    {'station_id': f"end_{traj_id}", 'trajectory_id': traj_id, 'name': "终点",
                     'lat': traj_data['end_coords'][0], 'lon': traj_data['end_coords'][1], 'u': 1.0, 'shared_id': None})
        clustered_stations = cluster_stations(all_stations_to_cluster)
        STATIONS_DATA_SATELLITE = clustered_stations
        if len(TRAJECTORIES_DATA) > 1:
            shared_station_counts = {traj_id: 0 for traj_id in TRAJECTORIES_DATA}
            for station in clustered_stations:
                if station['shared_id'] and station['trajectory_id'] in shared_station_counts: shared_station_counts[
                    station['trajectory_id']] += 1
            sorted_trajectories = sorted(TRAJECTORIES_DATA.keys(),
                                         key=lambda tid: (shared_station_counts[tid], TRAJECTORIES_DATA[tid]['length']),
                                         reverse=True)
            MASTER_TRAJ_ID = sorted_trajectories[0]
            print(
                f"  - ℹ️ 智能选择 '{get_alias(MASTER_TRAJ_ID)}' 作为基准轨迹 (共线站: {shared_station_counts[MASTER_TRAJ_ID]}个)。")
        elif len(TRAJECTORIES_DATA) == 1:
            MASTER_TRAJ_ID = list(TRAJECTORIES_DATA.keys())[0]
        initial_layouts = {}
        for traj_id in TRAJECTORIES_DATA:
            stations_for_this_traj = [{"name": s['name'], "progress": s['u'], "shared_id": s['shared_id']} for s in
                                      clustered_stations if s['trajectory_id'] == traj_id]
            initial_layouts[traj_id] = {"stations": sorted(stations_for_this_traj, key=lambda s: s['progress'])}
        if MASTER_TRAJ_ID and len(initial_layouts) > 1:
            PROGRESS_MAPPING = get_progress_mapping(initial_layouts, MASTER_TRAJ_ID)
            for traj_id, layout in initial_layouts.items():
                layout['length'] = TRAJECTORIES_DATA[traj_id]['length'];
                layout['is_master'] = (traj_id == MASTER_TRAJ_ID)
                for station in layout['stations']: station['display_progress'] = interpolate_progress(
                    station['progress'], PROGRESS_MAPPING.get(traj_id, []))
            SUBWAY_LAYOUT_DATA = initial_layouts
        else:
            for traj_id, layout in initial_layouts.items():
                layout['length'] = TRAJECTORIES_DATA[traj_id]['length'];
                layout['is_master'] = True
                for station in layout['stations']: station['display_progress'] = station['progress']
            SUBWAY_LAYOUT_DATA = initial_layouts
    except Exception as e:
        print(f"❌ 处理站点文件时发生错误: {e}")
    print("✅ 静态数据加载完毕。")
    yield


app = FastAPI(lifespan=lifespan)
# ... (@app.get 和 @app.websocket 接口与之前相同)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/", response_class=HTMLResponse)
async def get_frontend(): return HTMLResponse(content=open("safety_map_viewer.html", "r", encoding="utf-8").read())


@app.get("/trajectory_points.json")
async def get_trajectory(): return JSONResponse(
    content={get_alias(traj_id): data["points"] for traj_id, data in TRAJECTORIES_DATA.items()})


@app.get("/stations.json")
async def get_stations_for_satellite():
    stations_grouped = {};
    for s in STATIONS_DATA_SATELLITE:
        key = s['shared_id'] if s['shared_id'] is not None else f"unique_{s['station_id']}"
        if key not in stations_grouped: stations_grouped[key] = {"location": {"lat": s['lat'], "lon": s['lon']},
                                                                 "is_shared": bool(s['shared_id']), "stations": []}
        stations_grouped[key]['stations'].append({"name": s['name'], "trajectory_alias": get_alias(s['trajectory_id'])})
    return JSONResponse(content=list(stations_grouped.values()))


@app.get("/subway_layout.json")
async def get_subway_layout():
    aliased_layout = {};
    for traj_id, data in SUBWAY_LAYOUT_DATA.items(): aliased_layout[get_alias(traj_id)] = data
    return JSONResponse(content=aliased_layout)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/push_data")
async def process_and_push_data(request: Request):
    try:
        payload = await request.json()
        data = payload.get("data")
        if not (payload.get("messageType") == "vehicle_position" and data):
            return JSONResponse(status_code=400, content={"detail": "Invalid or missing data"})

        vehicle_id = data.get("trainDeviceCode")
        if not vehicle_id or not TRAJECTORIES_DATA:
            return JSONResponse(status_code=400, content={"detail": "Missing vehicle_id or no trajectories loaded"})

        actual_point = Point(float(data["lon"]), float(data["lat"]))
        actual_point_coords = np.array([float(data["lat"]), float(data["lon"])])

        # --- 步骤1: 轨迹匹配 (保持“基准优先”逻辑) ---
        distances_to_lines = {traj_id: traj_data["line"].distance(actual_point) for traj_id, traj_data in
                              TRAJECTORIES_DATA.items()}
        best_trajectory_id = min(distances_to_lines, key=distances_to_lines.get)
        min_dist = distances_to_lines[best_trajectory_id]
        dist_to_master = distances_to_lines.get(MASTER_TRAJ_ID)

        if MASTER_TRAJ_ID and dist_to_master is not None and dist_to_master < OVERLAP_THRESHOLD_DEGREES and min_dist < OVERLAP_THRESHOLD_DEGREES:
            best_trajectory_id = MASTER_TRAJ_ID

        # --- 步骤2: 回归“窗口搜索”和“单调递增”算法 ---
        matched_trajectory = TRAJECTORIES_DATA[best_trajectory_id]
        num_points = len(matched_trajectory["points"])

        # 获取车辆历史状态
        state = VEHICLE_STATES.setdefault(vehicle_id, {"last_progress": 0.0})
        last_progress = state["last_progress"]

        # 定义搜索窗口
        last_idx = int(last_progress * (num_points - 1))
        start_idx = max(0, last_idx - SEARCH_WINDOW_BACKWARD)
        end_idx = min(num_points, last_idx + SEARCH_WINDOW_FORWARD)

        # 在窗口内搜索最近点
        points_in_window = np.array(matched_trajectory["points"][start_idx:end_idx])
        distances_to_points = np.linalg.norm(points_in_window - actual_point_coords, axis=1)

        # 计算新进度
        best_idx_in_window = np.argmin(distances_to_points)
        best_idx_global = start_idx + best_idx_in_window
        new_progress = best_idx_global / (num_points - 1)

        # 确保单调递增
        final_progress = max(last_progress, new_progress)

        # --- 步骤3: 计算显示进度 ---
        display_progress = interpolate_progress(final_progress, PROGRESS_MAPPING.get(best_trajectory_id, []))

        # --- 步骤4: 更新状态并广播 ---
        VEHICLE_STATES[vehicle_id]["last_progress"] = final_progress  # 更新历史状态

        payload["data"]["progress"] = final_progress
        payload["data"]["display_progress"] = display_progress
        payload["data"]["matched_trajectory_alias"] = get_alias(best_trajectory_id)

        await manager.broadcast(json.dumps(payload))
        return JSONResponse(content={"status": "success"}, status_code=200)

    except Exception as e:
        print(f"❌ [服务器] 严重错误: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


if __name__ == "__main__":
    host, port = "127.0.0.1", 8000
    print("--- 启动 Uvicorn Web 服务器 (窗口搜索稳定版) ---")
    uvicorn.run(app, host=host, port=port)