#ifndef LOCALPLANNER_H
#define LOCALPLANNER_H

#include "simulation/Vehicle.h"
#include "simulation/Trajectory.h"
#include "Bspline.h"
#include "JsonParser.h"

#include <map>
#include <string>
#include <vector>

namespace tp {

class LocalPlanner {
public:
    explicit LocalPlanner(
        double lookahead_distance = 10.0,
        int local_path_points = 50,
        double on_track_cte_threshold = 0.1,
        double off_track_cte_threshold = 0.4,
        double on_track_heading_threshold_deg = 10.0,
        double off_track_heading_threshold_deg = 45.0,
        double max_allowed_speed = 5.0,
        double max_allowed_accel = 1.0,
        double max_allowed_curvature = 0.2
    );

    // 地图管理
    void importTrajectoryLibrary(const std::vector<TrajectoryData>& data);
    bool switchMap(const std::string& map_id);
    std::string getCurrentMapId() const;
    const TrajectoryData* getCurrentTrajectoryData() const;

    // 核心接口
    Trajectory generateLocalPath(const Vehicle& vehicle);

    // 状态查询
    double getProjectedU() const;
    Point getProjectionPoint() const;
    Vector getProjectionTangent() const;
    Point getLookAheadPoint() const;
    bool isOnTrackMode() const { return is_on_track_mode_; }

private:
    Trajectory generate_geometric_path(const Vehicle& vehicle);
    void findProjectionPoint(const Vehicle& vehicle);
    void findLookAheadPoint();

    Trajectory generateOnTrackPath(const Vehicle& vehicle) const;
    Trajectory generateOffTrackPath(const Vehicle& vehicle);

    // 内部私有重置（仅供 switchMap 使用）
    void resetPlanningState();

    // --- 成员变量 ---
    std::map<std::string, TrajectoryData> trajectory_library_;
    std::string current_map_id_;
    const Bspline* global_spline_ptr_ = nullptr;

    double last_projection_u_ = 0.0;
    Point last_projection_point_ = Point::Zero();
    Vector last_projection_tangent_ = Vector::UnitX();
    Point last_lookahead_point_ = Point::Zero();
    double last_lookahead_u_ = 0.0;

    bool is_on_track_mode_ = false;
    bool force_global_search_ = true; // 依然保留这个标志位，用于内部逻辑

    double lookahead_distance_;
    int    local_path_points_;
    double on_track_cte_threshold_;
    double off_track_cte_threshold_;
    double on_track_heading_threshold_rad_;
    double off_track_heading_threshold_rad_;
    double max_allowed_speed_;
    double max_allowed_accel_;
    double max_allowed_curvature_;

    double projection_search_step_ = 0.001;
    double search_window_u_ = 0.05;

    // [关键]：自动触发全局搜索的距离阈值 (单位: 米)
    double search_reset_dist_threshold_ = 5.0;
};

} // namespace tp

#endif // LOCALPLANNER_H
