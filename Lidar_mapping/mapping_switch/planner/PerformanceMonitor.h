#ifndef PERFORMANCEMONITOR_H
#define PERFORMANCEMONITOR_H

#include "simulation/Vehicle.h"
#include "Bspline.h"

namespace tp {

    /**
     * @class PerformanceMonitor
     * @brief 一个用于计算和提供车辆跟踪性能指标的分析类。
     *
     * 它像一个“裁判”，观察车辆的实际运动和理想路径，并量化其表现，
     * 如横向误差、朝向误差等。
     */
    class PerformanceMonitor {
    public:
        PerformanceMonitor();

        /**
         * @brief 更新监控器的核心函数。
         *
         * 在每个模拟循环中调用此函数，传入所有最新的状态信息，
         * 以便进行全面的性能计算。
         * @param vehicle 车辆的当前状态。
         * @param global_spline 全局B样条轨迹。
         * @param projection_point 车辆在全局轨迹上的投影点。
         * @param projection_tangent 全局轨迹在投影点处的切线。
         */
        void update(const Vehicle& vehicle,
                    const Bspline& global_spline,
                    const Point& projection_point,
                    const Vector& projection_tangent);

        // --- 性能指标获取接口 ---
        /**
         * @brief 获取横向误差 (Cross-Track Error, CTE)。
         * 即车辆当前位置到其在全局轨迹上投影点的距离。
         * @return 横向误差 (米)。
         */
        double getCrossTrackError() const;

        /**
         * @brief 获取朝向误差。
         * 即车辆当前朝向与其理想朝向（轨迹切线方向）之间的夹角。
         * @return 朝向误差 (弧度)。
         */
        double getHeadingError() const;

        /**
         * @brief 获取速度误差。
         * @param target_speed 期望的行驶速度。
         * @return 速度误差 (m/s)，即 实际速度 - 目标速度。
         */
        double getSpeedError(double target_speed) const;

        // 更多指标可以未来在这里添加...

    private:
        // --- 内部存储的计算结果 ---
        double cross_track_error_ = 0.0;
        double heading_error_ = 0.0;
        // ... 更多私有成员用于存储其他计算出的指标
    };

} // namespace tp

#endif // PERFORMANCEMONITOR_H
