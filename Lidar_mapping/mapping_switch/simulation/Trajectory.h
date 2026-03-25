#ifndef TRAJECTORY_H
#define TRAJECTORY_H

#include <vector>
#include "simulation/PlanningPoint.h" // 包含新的数据结构

namespace tp {

    /**
     * @class Trajectory
     * @brief 一个用于存储和管理 PlanningPoint 序列的容器。
     *
     * 这是 LocalPlanner 的标准输出格式。
     */
    class Trajectory {
    public:
        Trajectory() = default;

        // --- 修改器 ---
        void setPoints(const std::vector<PlanningPoint>& points);
        void addPoint(const PlanningPoint& point);
        void clear();

        // --- 访问器 ---
        const std::vector<PlanningPoint>& getPoints() const;
        // 提供一个非const版本，便于在规划器内部进行后处理
        std::vector<PlanningPoint>& getPoints_non_const();

        bool isEmpty() const;
        size_t getPointCount() const;

        // --- 便捷的索引操作符 ---
        const PlanningPoint& operator[](size_t index) const;
        PlanningPoint& operator[](size_t index);

        // --- 便捷的访问函数 ---
        const PlanningPoint& back() const;
        PlanningPoint& back();
        const PlanningPoint& front() const;
        PlanningPoint& front();


    private:
        std::vector<PlanningPoint> points_;
    };

} // namespace tp

#endif // TRAJECTORY_H