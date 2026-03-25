// D:/project_Management/localwork/C++/curve/src/utils/Bspline.cpp
// (版本与您当前的 Bspline.h 匹配)

#include "Bspline.h"
#include <stdexcept>
#include <algorithm> // For std::max and std::upper_bound
#include <vector>
#include <iterator>  // For std::distance

namespace tp {

Bspline::Bspline() : p_(3) {}

void Bspline::setDegree(int p) {
    if (p < 0) throw std::invalid_argument("Degree must be non-negative.");
    p_ = p;
}

void Bspline::setKnots(const std::vector<double>& U) {
    U_ = U;
}

void Bspline::setControlPoints(const std::vector<Point>& P) {
    P_ = P;
}

int Bspline::degree() const { return p_; }
const std::vector<double>& Bspline::knots() const { return U_; }
const std::vector<Point>& Bspline::controlPoints() const { return P_; }

int Bspline::findKnotSpan(double u) const {
    if (U_.empty()) {
        throw std::runtime_error("Knot vector is empty.");
    }

    // The number of control points defines n. n = P_.size() - 1.
    // The last valid knot index is m = n + p + 1.
    // The valid domain for u is [U_[p_], U_[n+1]].
    int n = static_cast<int>(P_.size()) - 1;
    if (u >= U_[n + 1]) {
        return n;
    }

    // Use std::upper_bound for an efficient binary search.
    // It finds the first element in the range that is greater than u.
    auto it = std::upper_bound(U_.begin() + p_, U_.end(), u);

    // The span is the index of the element just before the one found by upper_bound.
    return static_cast<int>(std::distance(U_.begin(), it) - 1);
}

Bspline Bspline::derivativeSpline() const {
    if (p_ == 0) {
        // The derivative of a 0-degree spline is a zero-vector spline of degree -1,
        // which we can represent with an empty Bspline object.
        return Bspline();
    }

    std::vector<Point> derivative_cp;
    derivative_cp.reserve(P_.size() - 1);

    for (size_t i = 0; i < P_.size() - 1; ++i) {
        double den = U_[i + p_ + 1] - U_[i + 1];
        if (std::abs(den) < 1e-9) {
            // This case should ideally not be hit in a well-formed clamped B-spline,
            // but as a safeguard, we output a zero vector.
            derivative_cp.push_back(Point::Zero());
        } else {
            Point num = P_[i + 1] - P_[i];
            derivative_cp.push_back(num * p_ / den);
        }
    }

    // The knot vector of the derivative spline has its first and last elements removed.
    std::vector<double> derivative_knots(U_.begin() + 1, U_.end() - 1);

    Bspline deriv;
    deriv.setDegree(p_ - 1);
    deriv.setKnots(derivative_knots);
    deriv.setControlPoints(derivative_cp);
    return deriv;
}

Point Bspline::evaluate(double u, int derivative_order) const {
    if (derivative_order < 0) throw std::invalid_argument("Derivative order must be non-negative.");
    if (P_.empty()) return Point::Zero();

    if (derivative_order == 0) {
        // Base case: Evaluate the point using De Boor's algorithm.
        int span = findKnotSpan(u);
        std::vector<Point> temp_points;
        temp_points.reserve(p_ + 1);
        for (int i = 0; i <= p_; ++i) {
            temp_points.push_back(P_[span - p_ + i]);
        }

        for (int j = 1; j <= p_; ++j) {
            for (int i = p_; i >= j; --i) {
                // Ensure the denominator is not zero before division.
                double den = U_[i + span - j + 1] - U_[i + span - p_];
                double alpha = (den == 0.0) ? 0.0 : (u - U_[i + span - p_]) / den;
                temp_points[i] = (1.0 - alpha) * temp_points[i - 1] + alpha * temp_points[i];
            }
        }
        return temp_points[p_];
    } else {
        // Recursive step: Evaluate the derivative by evaluating the derivative spline.
        if (p_ < derivative_order) {
            return Point::Zero();
        }
        Bspline deriv = this->derivativeSpline();
        return deriv.evaluate(u, derivative_order - 1);
    }
}

std::vector<Point> Bspline::evaluateAllDerivatives(double u, int max_derivative) const {
    if (max_derivative < 0) throw std::invalid_argument("Max derivative order must be non-negative.");

    std::vector<Point> derivatives(max_derivative + 1);
    if (P_.empty()) {
        // If there are no control points, all derivatives are zero.
        for(int i=0; i<=max_derivative; ++i) derivatives[i] = Point::Zero();
        return derivatives;
    }

    // Use an iterative approach for better performance than full recursion.
    std::vector<Bspline> derivative_splines(max_derivative + 1);
    derivative_splines[0] = *this;

    for (int i = 1; i <= max_derivative; ++i) {
        derivative_splines[i] = derivative_splines[i-1].derivativeSpline();
    }

    for (int i = 0; i <= max_derivative; ++i) {
        derivatives[i] = derivative_splines[i].evaluate(u, 0);
    }

    return derivatives;
}

} // namespace tp
