// /include/utils/Bspline.h

#ifndef BSPLINE_H
#define BSPLINE_H

#include "MathTypes.h" // 假设 MathTypes.h 在同一目录下或在include路径中
#include <vector>
#include <stdexcept> // For std::invalid_argument

namespace tp {

class Bspline {
public:
    /**
     * @brief 默认构造函数，创建一个3阶B样条。
     */
    Bspline();

    // --- 设置器 (Setters) ---
    /**
     * @brief 设置B样条的阶数 (degree)。
     * @param p 阶数，必须为非负数。
     */
    void setDegree(int p);

    /**
     * @brief 设置B样条的节点向量。
     * @param U 节点向量。
     */
    void setKnots(const std::vector<double>& U);

    /**
     * @brief 设置B样条的控制点。
     * @param P 控制点向量。
     */
    void setControlPoints(const std::vector<Point>& P);

    // --- 访问器 (Getters) ---
    int degree() const;
    const std::vector<double>& knots() const;
    const std::vector<Point>& controlPoints() const;

    // --- 核心求值函数 ---
    /**
     * @brief 计算B样条在参数u处的值或其指定阶导数。
     *
     * @param u 参数值，通常在 [0, 1] 范围内。
     * @param derivative_order 导数的阶数。0表示计算位置，1表示速度，2表示加速度等。
     * @return Point 返回计算出的点（位置）或向量（速度、加速度）。
     */
    Point evaluate(double u, int derivative_order = 0) const;

    /**
     * @brief 一次性计算从0阶到max_derivative阶的所有导数。
     *
     * 这是一个方便的函数，当需要同时获取位置、速度和加速度时，它比多次调用evaluate()更高效。
     *
     * @param u 参数值。
     * @param max_derivative 最高导数阶数。
     * @return std::vector<Point> 一个向量，其索引k处存储了k阶导数值。
     */
    std::vector<Point> evaluateAllDerivatives(double u, int max_derivative) const;

private:
    int p_;                        // B样条次数 (degree)
    std::vector<double> U_;        // 节点向量 (knots)
    std::vector<Point> P_;         // 控制点 (control points)

    /**
     * @brief [核心辅助函数] 计算当前B样条的导数样条。
     *
     * 一条p阶B样条的导数是另一条(p-1)阶的B样条。此函数计算并返回那条新的B样条。
     * 这是实现递归求导的关键。
     *
     * @return Bspline 代表导数的新B样条对象。
     */
    Bspline derivativeSpline() const;

    /**
     * @brief 使用高效的二分查找算法找到参数u所在的节点区间索引。
     * @param u 参数值。
     * @return int 节点区间的起始索引 (span)。
     */
    int findKnotSpan(double u) const;
};

} // namespace tp

#endif // BSPLINE_H