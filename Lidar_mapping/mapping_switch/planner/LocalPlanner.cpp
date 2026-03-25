#include "planner/LocalPlanner.h"
#include <limits>
#include <cmath>
#include <iostream>
#include <algorithm>

#define _USE_MATH_DEFINES
#include <math.h>

namespace tp {

// --- 构造函数 ---
LocalPlanner::LocalPlanner(
    double lookahead_distance, int local_path_points,
    double on_track_cte_threshold, double off_track_cte_threshold,
    double on_track_heading_threshold_deg, double off_track_heading_threshold_deg,
    double max_allowed_speed, double max_allowed_accel, double max_allowed_curvature
) : lookahead_distance_(lookahead_distance),
    local_path_points_(local_path_points),
    on_track_cte_threshold_(on_track_cte_threshold),
    off_track_cte_threshold_(off_track_cte_threshold),
    on_track_heading_threshold_rad_(on_track_heading_threshold_deg * M_PI / 180.0),
    off_track_heading_threshold_rad_(off_track_heading_threshold_deg * M_PI / 180.0),
    max_allowed_speed_(max_allowed_speed),
    max_allowed_accel_(max_allowed_accel),
    max_allowed_curvature_(max_allowed_curvature)
{
    is_on_track_mode_ = false;
    force_global_search_ = true; // 构造时置true，保证第一次生成路径一定是全局搜索
}

// --- 地图管理 ---
void LocalPlanner::importTrajectoryLibrary(const std::vector<TrajectoryData>& data) {
    if (data.empty()) return;
    for (const auto& traj : data) {
        if (!traj.id.empty()) trajectory_library_[traj.id] = traj;
    }
    if (global_spline_ptr_ == nullptr && !data.empty()) {
        switchMap(data[0].id);
    }
}

bool LocalPlanner::switchMap(const std::string& map_id) {
    auto it = trajectory_library_.find(map_id);
    if (it == trajectory_library_.end()) {
        std::cerr << "[LocalPlanner] Error: Map ID '" << map_id << "' not found." << std::endl;
        return false;
    }
    current_map_id_ = map_id;
    global_spline_ptr_ = &(it->second.spline);
    resetPlanningState(); // 切换地图时，内部强制重置
    return true;
}

std::string LocalPlanner::getCurrentMapId() const { return current_map_id_; }

const TrajectoryData* LocalPlanner::getCurrentTrajectoryData() const {
    auto it = trajectory_library_.find(current_map_id_);
    return (it != trajectory_library_.end()) ? &(it->second) : nullptr;
}

// 仅用于内部 switchMap 调用
void LocalPlanner::resetPlanningState() {
    last_projection_u_ = 0.0;
    last_lookahead_u_ = 0.0;
    last_projection_point_ = Point::Zero();
    last_projection_tangent_ = Vector::Zero();
    force_global_search_ = true; // 强制置位
    is_on_track_mode_ = false;
}

// --- 核心业务 ---
Trajectory LocalPlanner::generateLocalPath(const Vehicle& vehicle) {
    if (!global_spline_ptr_) return Trajectory();

    Trajectory geometric_path = generate_geometric_path(vehicle);
    if (geometric_path.isEmpty()) return geometric_path;

    return geometric_path;
}

// --- 投影点搜索 (包含自动防御逻辑) ---
void LocalPlanner::findProjectionPoint(const Vehicle& vehicle) {
    if (!global_spline_ptr_) return;

    // 1. [自动防御逻辑]：检查位置突变
    // 如果当前还没有被强制全局搜索，我们检查一下车辆是否跳变了
    if (!force_global_search_) {
        // 使用 squaredNorm 避免开方，提高效率
        double dist_sq = (vehicle.position - last_projection_point_).squaredNorm();
        double thresh_sq = search_reset_dist_threshold_ * search_reset_dist_threshold_;

        if (dist_sq > thresh_sq) {
            std::cout << "[LocalPlanner] Auto-Reset: Large position jump detected ("
                      << std::sqrt(dist_sq) << "m). Switching to GLOBAL search." << std::endl;
            force_global_search_ = true;
            // 注意：这里不需要重置 is_on_track_mode_，
            // 因为接下来的 CTE 计算和 generate_geometric_path 里的状态机会自动处理模式切换
        }
    }

    double best_u = last_projection_u_;
    double min_dist_sq = std::numeric_limits<double>::max();
    double start_u = 0.0;
    double end_u = 1.0;

    // 2. 根据标志位设定搜索范围
    if (!force_global_search_) {
        // 局部搜索
        start_u = std::max(0.0, last_projection_u_ - search_window_u_);
        end_u   = std::min(1.0, last_projection_u_ + search_window_u_);
    } else {
        // 全局搜索
        start_u = 0.0;
        end_u = 1.0;
    }

    // 3. 执行搜索
    for (double u = start_u; u <= end_u; u += projection_search_step_) {
        Point p = global_spline_ptr_->evaluate(u, 0);
        double dist_sq = (p - vehicle.position).squaredNorm();
        if (dist_sq < min_dist_sq) {
            min_dist_sq = dist_sq;
            best_u = u;
        }
    }

    // 4. 更新结果
    last_projection_u_ = best_u;
    last_projection_point_ = global_spline_ptr_->evaluate(best_u, 0);
    last_projection_tangent_ = global_spline_ptr_->evaluate(best_u, 1).normalized();

    // 5. 搜索完成，重置标志位，下一次默认尝试局部搜索
    force_global_search_ = false;
}

Trajectory LocalPlanner::generate_geometric_path(const Vehicle& vehicle) {
    findProjectionPoint(vehicle);

    // 计算误差
    double cos_theta = vehicle.forward_vec.dot(last_projection_tangent_);
    double heading_error_rad = std::acos(std::clamp(cos_theta, -1.0, 1.0));

    Vector error_vec = vehicle.position - last_projection_point_;
    Vector normal_vec(-last_projection_tangent_.y(), last_projection_tangent_.x(), 0);
    double cte = std::abs(error_vec.dot(normal_vec));

    // 状态机逻辑
    if (is_on_track_mode_) {
        if (cte > off_track_cte_threshold_ || heading_error_rad > off_track_heading_threshold_rad_) {
            is_on_track_mode_ = false;
            // std::cout << "Switched to OffTrack" << std::endl;
        }
    } else {
        if (cte < on_track_cte_threshold_ && heading_error_rad < on_track_heading_threshold_rad_) {
            is_on_track_mode_ = true;
             std::cout << "online" << std::endl;
        }
    }

    findLookAheadPoint();

    if (is_on_track_mode_) return generateOnTrackPath(vehicle);
    else return generateOffTrackPath(vehicle);
}

void LocalPlanner::findLookAheadPoint() {
    if (!global_spline_ptr_) return;

    double accumulated_distance = 0.0;
    Point current_p = last_projection_point_;
    double u = last_projection_u_;

    while (accumulated_distance < lookahead_distance_ && u < 1.0) {
        u += projection_search_step_;
        if (u > 1.0) u = 1.0;
        Point next_p = global_spline_ptr_->evaluate(u, 0);
        accumulated_distance += (next_p - current_p).norm();
        current_p = next_p;
    }
    last_lookahead_u_ = u;
    last_lookahead_point_ = current_p;
}

// --- Getter ---
double LocalPlanner::getProjectedU() const { return last_projection_u_; }
Point LocalPlanner::getProjectionPoint() const { return last_projection_point_; }
Vector LocalPlanner::getProjectionTangent() const { return last_projection_tangent_; }
Point LocalPlanner::getLookAheadPoint() const { return last_lookahead_point_; }

// --- 占位实现 ---
// --- [临时过渡版 v2] 匀速等时采样 (高精度/保量) ---
Trajectory LocalPlanner::generateOnTrackPath(const Vehicle& vehicle) const {
    Trajectory trajectory;
    // 即使没有地图，也尽量返回空对象而不是崩溃，但按逻辑这里应该已有地图
    if (!global_spline_ptr_) return trajectory;

    // 1. 设置采样参数
    const double dt = 0.1;                 // 时间间隔 0.1s
    const int num_points = 50;             // 强制采样 50 个点

    // 规划速度：如果车速小于 0.5，强制按 0.5 计算，防止点距过密重叠
    double plan_speed = std::max(vehicle.speed, 0.5);

    // 单步目标距离 (匀速假设)
    double target_step_dist = plan_speed * dt;

    // 2. 初始化变量
    double current_u = last_projection_u_; // 起点为当前投影位置
    Point prev_pos = global_spline_ptr_->evaluate(current_u, 0);
    double accumulated_s = 0.0;            // 累计路程缓存

    // 高精度搜索步长 (1e-5)，保证积分准确
    const double search_step = 0.00001;

    // 3. 严格循环生成 num_points 个点
    for (int i = 0; i < num_points; ++i) {
        PlanningPoint pt;

        // --- A. 积分寻找下一个点 (第0个点不需要移动) ---
        if (i > 0 && current_u < 1.0) {
            double current_segment_dist = 0.0;

            // 积分循环：微步进向前，直到凑够 target_step_dist
            while (current_segment_dist < target_step_dist) {
                // 尝试向前一步
                double next_u = current_u + search_step;

                // 边界保护：到达地图终点
                if (next_u >= 1.0) {
                    current_u = 1.0;
                    // 在这里不 break，是为了更新 prev_pos 最后的距离
                    // 但由于 u 不再增加，pos 不变，dist 也不变，循环会自然退出或死循环
                    // 所以必须 break
                    break;
                }

                Point next_p = global_spline_ptr_->evaluate(next_u, 0);
                double ds = (next_p - prev_pos).norm();

                current_segment_dist += ds;
                prev_pos = next_p;
                current_u = next_u;
            }
            // 累加总里程
            accumulated_s += current_segment_dist;
        }

        // --- B. 计算几何属性 (Geometry) ---
        // 此时 current_u 已经更新到了正确位置 (或停留在 1.0)
        pt.position = global_spline_ptr_->evaluate(current_u, 0);

        Vector d1 = global_spline_ptr_->evaluate(current_u, 1);
        Vector d2 = global_spline_ptr_->evaluate(current_u, 2);

        // Heading
        pt.heading = std::atan2(d1.y(), d1.x());

        // Curvature
        double cross_prod = d1.x() * d2.y() - d1.y() * d2.x();
        double norm_sq = d1.squaredNorm();
        // 加上极小值防止除以零
        pt.curvature = (norm_sq > 1e-8) ? (cross_prod / std::pow(norm_sq, 1.5)) : 0.0;

        // --- C. 填充物理属性 (Physics) ---
        pt.speed = vehicle.speed;         // 保持当前车速 (匀速假设)
        pt.acceleration = 0.0;            // 匀速加速度为 0
        pt.relative_time = i * dt;        // 时间严格递增：0.0, 0.1, 0.2 ...
        pt.arc_length = accumulated_s;    // 沿轨迹的累计距离
        pt.d_curvature = 0.0;             // 暂时忽略

        // --- D. 加入容器 ---
        trajectory.addPoint(pt);
    }

    return trajectory;
}
Trajectory LocalPlanner::generateOffTrackPath(const Vehicle& vehicle) {
    Trajectory trajectory;
    // 即使没有地图，也尽量返回空对象而不是崩溃，但按逻辑这里应该已有地图
    if (!global_spline_ptr_) return trajectory;

    // 1. 设置采样参数
    const double dt = 0.1;                 // 时间间隔 0.1s
    const int num_points = 50;             // 强制采样 50 个点

    // 规划速度：如果车速小于 0.5，强制按 0.5 计算，防止点距过密重叠
    double plan_speed = std::max(vehicle.speed, 0.5);

    // 单步目标距离 (匀速假设)
    double target_step_dist = plan_speed * dt;

    // 2. 初始化变量
    double current_u = last_projection_u_; // 起点为当前投影位置
    Point prev_pos = global_spline_ptr_->evaluate(current_u, 0);
    double accumulated_s = 0.0;            // 累计路程缓存

    // 高精度搜索步长 (1e-5)，保证积分准确
    const double search_step = 0.00001;

    // 3. 严格循环生成 num_points 个点
    for (int i = 0; i < num_points; ++i) {
        PlanningPoint pt;

        // --- A. 积分寻找下一个点 (第0个点不需要移动) ---
        if (i > 0 && current_u < 1.0) {
            double current_segment_dist = 0.0;

            // 积分循环：微步进向前，直到凑够 target_step_dist
            while (current_segment_dist < target_step_dist) {
                // 尝试向前一步
                double next_u = current_u + search_step;

                // 边界保护：到达地图终点
                if (next_u >= 1.0) {
                    current_u = 1.0;
                    // 在这里不 break，是为了更新 prev_pos 最后的距离
                    // 但由于 u 不再增加，pos 不变，dist 也不变，循环会自然退出或死循环
                    // 所以必须 break
                    break;
                }

                Point next_p = global_spline_ptr_->evaluate(next_u, 0);
                double ds = (next_p - prev_pos).norm();

                current_segment_dist += ds;
                prev_pos = next_p;
                current_u = next_u;
            }
            // 累加总里程
            accumulated_s += current_segment_dist;
        }

        // --- B. 计算几何属性 (Geometry) ---
        // 此时 current_u 已经更新到了正确位置 (或停留在 1.0)
        pt.position = global_spline_ptr_->evaluate(current_u, 0);

        Vector d1 = global_spline_ptr_->evaluate(current_u, 1);
        Vector d2 = global_spline_ptr_->evaluate(current_u, 2);

        // Heading
        pt.heading = std::atan2(d1.y(), d1.x());

        // Curvature
        double cross_prod = d1.x() * d2.y() - d1.y() * d2.x();
        double norm_sq = d1.squaredNorm();
        // 加上极小值防止除以零
        pt.curvature = (norm_sq > 1e-8) ? (cross_prod / std::pow(norm_sq, 1.5)) : 0.0;

        // --- C. 填充物理属性 (Physics) ---
        pt.speed = vehicle.speed;         // 保持当前车速 (匀速假设)
        pt.acceleration = 0.0;            // 匀速加速度为 0
        pt.relative_time = i * dt;        // 时间严格递增：0.0, 0.1, 0.2 ...
        pt.arc_length = accumulated_s;    // 沿轨迹的累计距离
        pt.d_curvature = 0.0;             // 暂时忽略

        // --- D. 加入容器 ---
        trajectory.addPoint(pt);
    }

    return trajectory;
}

} // namespace tp