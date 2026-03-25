#include "planner/PerformanceMonitor.h"
#include <cmath>     // For std::acos, std::abs
#include <algorithm> // For std::clamp

namespace tp {

    PerformanceMonitor::PerformanceMonitor() {
        // 构造函数，所有成员变量都被默认初始化为0.0
    }

    void PerformanceMonitor::update(const Vehicle& vehicle,
                                    const Bspline& global_spline,
                                    const Point& projection_point,
                                    const Vector& projection_tangent) {
        // --- 1. 计算横向误差 (Cross-Track Error, CTE) ---
        // 这是车辆当前位置到其在全局轨迹上投影点的欧氏距离。
        cross_track_error_ = (vehicle.position - projection_point).norm();

        // --- 2. 计算朝向误差 (Heading Error) ---
        // 这是车辆当前朝向向量与理想朝向（轨迹切线）之间的夹角。
        // a · b = |a|*|b|*cos(theta)
        // 因为 forward_vec 和 projection_tangent 都是单位向量, |a|=|b|=1
        // 所以 a · b = cos(theta)
        double cos_theta = vehicle.forward_vec.dot(projection_tangent);

        // 使用 std::clamp 防止由于浮点数误差导致cos_theta略微超出[-1, 1]范围
        // 这可以避免 std::acos 抛出域错误 (domain error)
        cos_theta = std::clamp(cos_theta, -1.0, 1.0);

        heading_error_ = std::acos(cos_theta); // 结果是弧度
    }

    // --- 性能指标获取接口 ---

    double PerformanceMonitor::getCrossTrackError() const {
        return cross_track_error_;
    }

    double PerformanceMonitor::getHeadingError() const {
        return heading_error_;
    }

    double PerformanceMonitor::getSpeedError(double target_speed) const {
        // 这个函数是独立的，因为它需要一个外部输入 target_speed
        // 在我们的模型中，车辆的实际速度是在 vehicle.speed 中
        // 注意：这里的实现需要 Vehicle 类中有 speed 成员
        // return vehicle_speed_ - target_speed; // 这需要在update中传入vehicle.speed
        // 为保持接口简洁，我们假设调用者可以自行计算：
        // double speed_error = vehicle.speed - target_speed;
        // 这里我们先返回一个占位符
        return 0.0; // 暂时不实现，因为它依赖于一个动态的目标速度
    }

} // namespace tp